---
type: data-pipeline
title: Calendar feed
description: How multiple iCal feeds are fetched, prefiltered, expanded with ical.js, merged and stored in KV by the Worker cron, how failures are isolated per feed, and how the frame indexes the result by day for its Home, Week, Month and clock screens.
tags: [calendar, ical, ical.js, kv, cron, timezones]
sources:
  - id: openwiki-source-e12fdae11ea7713285efd699
    resource: repo://dashboard/src/lib/format.js
  - id: openwiki-source-51ad52cbd5c10d5789425706
    resource: repo://dashboard/src/views/Month.svelte
  - id: openwiki-source-b1a66f44fa52ae21cd5c82ec
    resource: repo://dashboard/src/views/Week.svelte
  - id: openwiki-source-47e567cb98956edcb53bcbd3
    resource: repo://dashboard/worker/api.test.js
  - id: openwiki-source-394f238f10df4406a597a196
    resource: repo://dashboard/worker/calendar.js
  - id: openwiki-source-7fc4ec3787abf1e07adb8d8f
    resource: repo://dashboard/worker/calendar.test.js
  - id: openwiki-source-761c8b9c5f5e1234a74d94a4
    resource: repo://dashboard/worker/index.js
generated: { by: "openwiki/0.7.2", at: "2026-10-13T17:09:19.129Z" }
verified:
  - by: openwiki/0.7.2
    at: 2026-10-13T17:09:19.129Z
---

# Calendar feed

The dashboard shows one merged calendar built from any number of iCal links (for example an iCloud
family calendar and a Google holiday calendar). The Worker does all parsing; the frame receives a
small sorted JSON list.

```text
cron */10 ─► updateCalendar ─► refresh: fetch each feed ─► expand (calendar.js) ─► merge
                                   │                                              │
                                   └── on failure: that feed's last good events ──┘
             └─► KV "calendar" (written only when changed, or hourly)
GET /api/calendar ─► KV copy (refresh in background if the cron fell behind) ─► frame
```

## Configuration

`CALENDAR_URLS` (a secret) holds the links separated by spaces, commas or newlines; `webcal://`
is rewritten to `https://`. Each link's position becomes the event's `cal` index, which the frame
maps to a colour. `DISPLAY_TZ` is the fallback zone for times with no TZID and no
`X-WR-TIMEZONE` (default UTC). The window is 40 days back (so the month view can show the whole
current month) to 70 days ahead (five weeks of week view and the month view through next month).

## Parsing (`dashboard/worker/calendar.js`)

`calendar.js` is pure functions with no Worker APIs, so it runs under `node --test`.

### `prefilter(text, from, to)`

A Google feed contains every event ever created, and full ical.js parsing was too slow for a
cron run. `prefilter` first unfolds continuation lines, then does a cheap string scan over each
`VEVENT` block:

- Keeps every event that has `RRULE`, `RDATE`, `RECURRENCE-ID` or `DURATION` — recurring events
  and exceptions must survive so recurrence expansion can produce occurrences inside the window.
- Keeps one-off events whose `DTSTART`/`DTEND` overlap `[from − 2 days, to + 2 days]`. The padding
  avoids losing events that cross the window edge.
- Always keeps `VTIMEZONE` blocks and the calendar-level `X-WR-TIMEZONE`.

The output is a trimmed iCal text that ical.js can parse quickly.

### `expand(text, cal, from, to, fallbackTz)`

`expand` runs the filtered text through ical.js and emits events that overlap the window.

1. Registers every `VTIMEZONE` with ical.js's `TimezoneService`.
2. Resolves the start-time zone with `tzFor`: `DTSTART;TZID=…` first, then the feed's
   `X-WR-TIMEZONE`, then the `DISPLAY_TZ` fallback.
3. Splits components into three buckets:
   - standalone non-recurring events;
   - exception events (`RECURRENCE-ID`) — their instance key is recorded so the matching
     generated occurrence is skipped;
   - recurring masters (`RRULE`/`RDATE`), which are iterated later.
4. Emits each event through `toEvent`. Cancelled events (`STATUS:CANCELLED`) are dropped. Timed
   events become ISO instants; all-day events keep plain `YYYY-MM-DD` dates with an exclusive end
   so the frame shows them on each covered day without time-of-day ambiguity.
5. Recurring masters are expanded with `event.iterator(fastForward(...))`. The walk is capped at
   20,000 occurrences per master and stops as soon as the next occurrence is more than a day past
   the window.

`EXDATE` is honoured automatically by ical.js's iterator; `RECURRENCE-ID` exceptions replace only
the matching occurrence because `expand` tracks a per-UID set of overridden instance keys.

### Time zone resolution

`utcMs(t, tz)` converts an `ICAL.Time` to epoch milliseconds:

- All-day values map to UTC midnight of that date.
- UTC/Z values use `Date.UTC` directly.
- For IANA zone names (`America/Chicago`, `America/New_York`, …), `Intl.DateTimeFormat` is used
  with current DST rules. The code iterates the offset calculation once to converge on the right
  instant.
- For non-IANA zone names, it falls back to the feed's `VTIMEZONE` via `t.toUnixTime()`.
- Floating times (no TZID and no ical.js zone) are interpreted in `tz`, which is the DTID parameter,
  `X-WR-TIMEZONE`, or `DISPLAY_TZ` / UTC.

This is the piece most validated by the test fixtures: a weekly practice in CDT, a daily event
since 1995, a floating farmers market in the calendar's default zone, and a DST change where the
same wall-clock time shifts from 12:00Z to 13:00Z.

### `fastForward(event, from)`

ical.js walks recurrences from `DTSTART`. A daily event from 1995 would require thousands of
steps, so `fastForward` computes the last whole interval before the window and starts the iterator
there instead:

- `DAILY` and `WEEKLY` advance by whole days (`interval × 1` or `interval × 7`).
- `MONTHLY` and `YEARLY` advance by whole months (`interval` or `12 × interval`).
- Skipped when `COUNT` is present, when there is more than one `RRULE`, or when the start day is
  above 28 (to avoid month-length edge cases).

The test suite compares fast-forwarded results against the same rule with a huge `COUNT` and
verifies they match.

### `merge(lists)`

`merge` flattens all feed arrays, drops duplicates that share the same `uid` and `start` (the same
invite appearing on two calendars), sorts by `startMs`, then calendar index, then title, and strips
the internal `startMs`/`endMs` sort keys before returning the list.

The output shape is `{uid, cal, allDay, title, start, end, location?, holiday?}`.

## Refresh, storage and failure (`dashboard/worker/index.js`)

`refresh(env, previous)` fetches all feeds in parallel and returns a single object:

```js
{ updated, calendars: urls.length, errors, events }
```

- `webcal://` is rewritten to `https://` and the request asks for `text/calendar`.
- A feed whose URL contains "holiday" has its events marked `holiday: true` after expansion, so
  the frame can exclude holidays from counts.
- **Per-calendar failure handling:** if a feed throws or returns a non-iCal body, the error is
  logged, an entry `{cal, error}` is added to `errors`, and that feed's last good events from the
  previous KV copy are reused. Other feeds are unaffected, so a transient blip never blanks the
  wall display. The error list is returned to the frame so the UI can show that something is stale.

`updateCalendar` writes the result to KV key `calendar` only when the events or errors changed,
or when the stored copy is over an hour old (`HEARTBEAT_MS`, keeping `updated` meaningful). The
cron runs it every 10 minutes, so typical KV writes drop from 144 a day to about 24.

`GET /api/calendar` answers from KV. With no copy, or with `?refresh` (used by Settings →
Reload), it refreshes synchronously. If the copy is older than 75 minutes (`STALE_MS`, i.e. the
cron fell behind) it answers with the copy and refreshes in the background via `waitUntil`.

See [Worker routing, auth and caching](../worker/routing-auth-and-caching.md) for how the route is
authenticated and how the cron is wired.

## On the frame

`loadCalendar()` polls every 5 minutes and only replaces state when the response changed (see
[App shell, state and polling](../frontend/app-shell-state-and-polling.md)); the last copy is kept
in `localStorage` so the frame boots with a calendar when offline, and Week/Month show
"Offline · <time>" in that case.

`eventsOn(events, day)` in `dashboard/src/lib/format.js` is the single way views ask for a day's
events. It builds a per-feed index (a `WeakMap` keyed by the events array) once per calendar copy:
timed events live under their local start day, all-day events under every day from start to
exclusive end. Home, Week, Month and the idle clock screen call it for many days each minute, so
this replaced repeated full scans.

The Week view uses the `holiday` flag to leave holidays out of the "more events ahead" badge count
(`calendar.data.events.filter((e) => !e.holiday && Date.parse(e.start) >= from).length`).

The Month view derives a day key from the minute clock so its month grid rebuilds only when the
date changes, not every minute.

## Tests as the specification

`worker/calendar.test.js` is the spec for parser edge cases. It uses `fixtures/google.ics` and
`fixtures/icloud.ics` to cover:

- weekly recurrence with `EXDATE`, moved (`RECURRENCE-ID`) and cancelled instances;
- a daily event since 1995 expanding only inside the window;
- multi-day all-day events with exclusive end dates;
- one-off events outside the window dropped by `prefilter` before parsing;
- iCloud specifics: folded lines, `TZID`, floating times, all-day events;
- merging two calendars, sorting, and dropping the shared-invite duplicate;
- a DST change keeping wall-clock time;
- fast-forwarded `MONTHLY` and `YEARLY` rules matching a full ical.js walk.

`worker/api.test.js` covers the stale-copy background refresh, holiday-feed marking, per-calendar
failure reuse, and the cron writing KV only on change or hourly. See
[Tests and verification](../testing/tests-and-verification.md).
