---
type: testing
title: Tests and verification
description: How the Worker and frontend are verified without touching the physical frame. Node's built-in test runner exercises worker/*.test.js with mocked fetch, KV and Durable Objects, while frontend changes are checked in a headless 1280×720 browser using demo mode and the ?diag overlay.
tags: [testing, node-test, mocks, fixtures, verification, headless-browser, demo-mode]
verified:
  - by: openwiki/0.7.2
    at: 2026-10-13T17:09:19.129Z
sources:
  - id: openwiki-source-1749acaa35a5ed1522bc474a
    resource: repo://dashboard/index.html
  - id: openwiki-source-51dca17ef0b6465be67eaf89
    resource: repo://dashboard/package.json
  - id: openwiki-source-514f617424296bf803eef9f3
    resource: repo://dashboard/src/diag.js
  - id: openwiki-source-0fdf6b0286494d706603818c
    resource: repo://dashboard/src/lib/demo.js
  - id: openwiki-source-3a4039a222339b2ae26827c1
    resource: repo://dashboard/src/lib/state.svelte.js
  - id: openwiki-source-47e567cb98956edcb53bcbd3
    resource: repo://dashboard/worker/api.test.js
  - id: openwiki-source-7fc4ec3787abf1e07adb8d8f
    resource: repo://dashboard/worker/calendar.test.js
  - id: openwiki-source-e0922edba974cd178a66bf62
    resource: repo://dashboard/worker/fixtures/google.ics
  - id: openwiki-source-fab37fe2bf7e0b41e1a37929
    resource: repo://dashboard/worker/fixtures/icloud.ics
generated: { by: "openwiki/0.7.2", at: "2026-10-13T17:09:19.129Z" }
---

# Tests and verification

The project keeps verification away from the family frame as much as possible. Automated tests cover the Worker, and frontend changes are checked in a headless browser at the frame's exact CSS size before any deploy.

## Running the Worker tests

From `dashboard/`:

```bash
npm test
```

`npm test` runs `node --test worker/*.test.js` (`package.json` scripts). There is no test framework, no Worker runtime and no network: the Worker's `fetch` and `scheduled` handlers are imported directly and called with fake bindings. Everything in `worker/` is written to run under plain Node — for example `calendar.js` is pure functions, and `MessageRoom` only touches Durable Object APIs through its injected `ctx`.

There are no automated frontend tests. UI changes are verified by building and looking in a browser (see [Verifying frontend changes](#verifying-frontend-changes)).

## `worker/calendar.test.js`

Pure parser tests at a fixed "now" (`2026-10-12T12:00:00Z`) against two real-shaped fixtures, `worker/fixtures/google.ics` and `worker/fixtures/icloud.ics`. The fixtures encode the edge cases the calendar pipeline has to get right:

| Fixture | Edge case | What the test checks |
| --- | --- | --- |
| `google.ics` | Weekly recurrence | `RRULE FREQ=WEEKLY;BYDAY=MO,WE` expands correctly. |
| `google.ics` | `EXDATE` | One soccer instance on `2026-10-14` is skipped. |
| `google.ics` | Override (`RECURRENCE-ID`) | The `2026-10-19` soccer instance is moved one hour later with a new title. |
| `google.ics` | Cancelled instance | The `2026-10-21` soccer instance is dropped via `STATUS:CANCELLED`. |
| `google.ics` | Long-running daily rule | A `FREQ=DAILY` event since 1995 expands only inside the 14-day window. |
| `google.ics` | Multi-day all-day event | `DTSTART;VALUE=DATE:20261016` keeps plain dates with an exclusive end. |
| `google.ics` | Prefilter | The ancient one-off "Old event" is dropped before parsing, while `VTIMEZONE` survives. |
| `google.ics` | DST | A daily event at 7 AM keeps wall-clock time across the CDT→CST change. |
| `google.ics` + `icloud.ics` | Shared-invite de-duplication | The same dentist event in both feeds appears once after `merge`. |
| `icloud.ics` | Folded lines | A wrapped `SUMMARY` is reassembled. |
| `icloud.ics` | `TZID` | New York time zones resolve to the right UTC instants. |
| `icloud.ics` | Floating times | An event with no `TZID` or `VALUE=DATE` uses the feed's `X-WR-TIMEZONE`. |
| `icloud.ics` | All-day | Trash pickup keeps plain start/end dates. |
| Synthetic feeds | Fast-forward equivalence | Monthly and yearly `RRULE`s using fast-forward logic produce the same occurrences as a brute-force walk with a huge `COUNT`. |

See [Calendar feed](../feeds/calendar.md) for how `prefilter`, `expand` and `merge` are used by the cron and API.

## `worker/api.test.js`

End-to-end tests call `worker.fetch(new Request(…), env, ctx)` directly. The suite sets up a fake environment before each test:

- **Fake Todoist API** installed on `globalThis.fetch`: two pages of projects, tasks with subtasks, due dates, sections and collaborators.
- **In-memory KV objects** per test supporting `get`, `put`, `getWithMetadata` and `delete`.
- **`fakeRoom()`**, which constructs the real `MessageRoom` with a stand-in `ctx` (storage map, alarm log, socket list, no-op auto-response) and wraps it in a fake Durable Object namespace.
- **Per-test `fetch` replacements** for iCal feeds, CloudKit shared-album records, TheMealDB and image hosts.

| Area | What the tests protect |
| --- | --- |
| **Auth** | API calls need the dashboard key; static assets do not. The agent token can post messages and save recipes, but cannot read anything. |
| **Todoist** | Project lookup across pagination pages; Todoist order for groceries; subtasks hidden; dated to-dos first with overdue on top; add and complete; unknown list and missing token handling; description `note`. |
| **Weather** | `shape()` keeps only the fields the screen uses. |
| **Calendar** | A stale copy is served immediately and refreshed in the background; holiday-feed events are marked; cron writes KV only on change or hourly. |
| **Photos** | Anonymous album resolution; edited version preferred over master; videos skipped; images proxied and cached; small-JPEG originals used when no medium exists, while large or HEIC originals are rejected. |
| **Messages** | Validation and limits; dismissal; 20-message cap; push to connected sockets on post/dismiss; expiry alarm; `/api/messages/live` needs the key and a WebSocket upgrade. |
| **Recipes** | TheMealDB normalisation and sized thumbnails; saving via agent and frame; image storage; `ref` de-duplication; bulk grocery add with descriptions; vegetarian/vegan exclusion. |

When behaviour changes intentionally, update the test that encodes it (for example the stale-calendar threshold) rather than deleting it.

## Verifying frontend changes

The physical frame is a family device that may be in use, so UI changes are checked away from it whenever possible.

### 1. Build and test

Run `npm test`, then `npm run build` to catch Svelte warnings and errors. Deploy if needed (see [Build, deploy and configuration](../operations/build-deploy-and-configuration.md)). After a deploy, wait until the live page references the new hashed bundle before checking.

### 2. Headless browser at the frame size

Open the deployed page (or `npm run preview`) in a headless browser at **1280×720** CSS pixels — the frame's viewport on the 1920×1080 FRAME156, which renders the 1280-wide layout at 1.5×. Use `?key=<DASHBOARD_KEY>` so the page can authenticate, and enable demo mode (`frame-demo` in `localStorage`) so the frame never touches real calendars, tasks, photos or messages.

Demo mode is toggled in Settings → Demo mode. It replaces real feeds with invented data from `src/lib/demo.js` and suppresses agent messages, Todoist writes and family photos (see [App shell, state and polling](../frontend/app-shell-state-and-polling.md)).

Screenshot the affected screens in both light and dark themes.

### 3. Performance check with `?diag`

For performance questions, throttle the CPU (for example 8×) and time interactions, or enable the on-screen diagnostics overlay with `?diag`. `?diag=0` turns it off. The state is remembered in `localStorage` on the device, so on the frame it stays on across reloads until disabled.

The overlay (from `src/diag.js`) reports:

- Chrome version, CSS viewport size and device pixel ratio.
- Current fps and long-frame count (> 50 ms).
- Total DOM node count.
- Decoded image count and total megapixels.
- Used JS heap size in MB.

This is the preferred way to understand how the frame itself is performing. The real device is slower than a development machine, so numbers that look fine headless may still need work on-device; use the overlay there rather than guesswork.

### 4. Real device only when necessary

Real-device verification should be brief and non-disruptive. Prefer the diagnostics overlay and the automated tests. Avoid scripted taps, reloads or reboots on the actual frame unless its owner agrees (see [Kiosk app and the frame device](../device/kiosk-app-and-frame.md)).
