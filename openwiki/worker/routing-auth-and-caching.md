---
type: component
title: Worker routing, auth and caching
description: How the Cloudflare Worker entry point serves the page and assets, authenticates the frame and AI agents, dispatches every /api route, sets cache headers, uses KV, and runs the calendar cron.
tags: [cloudflare-workers, routing, auth, caching, api]
verified:
  - by: openwiki/0.7.2
    at: 2026-10-13T17:09:19.129Z
sources:
  - id: openwiki-source-a735d7910a81a35570838e4c
    resource: repo://dashboard/public/_headers
  - id: openwiki-source-47e567cb98956edcb53bcbd3
    resource: repo://dashboard/worker/api.test.js
  - id: openwiki-source-761c8b9c5f5e1234a74d94a4
    resource: repo://dashboard/worker/index.js
  - id: openwiki-source-272749880eb665924bb98bdd
    resource: repo://dashboard/worker/photos.js
  - id: openwiki-source-3d87a5bdd7a2737ed75505a1
    resource: repo://dashboard/worker/recipes.js
  - id: openwiki-source-0d4db84e2b7fee7556be759e
    resource: repo://dashboard/wrangler.jsonc
generated: { by: "openwiki/0.7.2", at: "2026-10-13T17:09:19.129Z" }
---

# Worker routing, auth and caching

`dashboard/worker/index.js` is the single entry point of the deployed Worker. It exports the
`fetch` handler (page, assets and API), the `scheduled` handler (calendar cron) and re-exports the
`MessageRoom` Durable Object class. Feature logic lives in sibling modules; `index.js` only
authenticates, dispatches and wraps responses.

## Page and assets

Requests outside `/api/` go to the static asset binding (`ASSETS`, the Vite build). `wrangler.jsonc`
sets `run_worker_first` for `/` and `/index.html` so the Worker sees the page request: any HTML
response is re-sent with `Cache-Control: no-store`, so the frame always gets the latest page
(and therefore the latest hashed bundle) on its next load. Hashed files under `/assets/*` are
cached for a year as immutable by `public/_headers`. See
[build and deploy](../operations/build-deploy-and-configuration.md).

## Credentials

| Credential | Who holds it | Accepted |
| --- | --- | --- |
| `DASHBOARD_KEY` | the frame (localStorage) | `Authorization: Bearer` on any `/api` route; or `?key=` on GET for routes an `<img>` or WebSocket must reach: `/api/photos/:id`, `/api/recipes/:id/image`, `/api/messages/live` |
| `AGENT_TOKEN` | AI agents (the kitchen-frame skills) | only `POST /api/messages` and `POST /api/recipes`; it can read nothing |
| none | | static assets |

The agent routes are checked before the frame key: `POST /api/messages` requires the agent token
(the frame key is rejected there), and `POST /api/recipes` with the agent token saves directly;
everything else falls through to `authorized()`, which returns 401 JSON on failure. If
`DASHBOARD_KEY` is unset (local development), the check is skipped.

## Route map

| Method | Route | Caller | Implements | Module |
| --- | --- | --- | --- | --- |
| `GET` | `/api/calendar` (`?refresh`) | frame | Merged iCal feeds; cron refreshes them in KV every 10 min | `calendar.js` |
| `GET` | `/api/weather` | frame | Open-Meteo current + 5-day | `weather.js` |
| `GET` | `/api/lists/:list` | frame | Todoist project tasks (`groceries` or `todo`) | `todoist.js` |
| `POST` | `/api/lists/:list` | frame | Add one item, or `items: [...]` for up to 40 | `todoist.js` |
| `POST` | `/api/lists/:list/:id/done` | frame | Complete an item | `todoist.js` |
| `GET` | `/api/photos` | frame | iCloud shared album photo list | `photos.js` |
| `GET` | `/api/photos/:id` | frame (as `<img src>`) | One photo, resized and proxied | `photos.js` |
| `GET` | `/api/messages` | frame | Pending messages, oldest first | `messages.js` (`MessageRoom`) |
| `GET` | `/api/messages/live` | frame (as WebSocket) | Live push of the message list | `messages.js` (`MessageRoom`) |
| `POST` | `/api/messages` | AI agent | Post a full-screen message | `messages.js` (`MessageRoom`) |
| `POST` | `/api/messages/:id/dismiss` | frame | Remove a message | `messages.js` (`MessageRoom`) |
| `GET` | `/api/recipes/explore` | frame | Browse or random TheMealDB recipes | `recipes.js` |
| `GET` | `/api/recipes` | frame | Saved recipes | `recipes.js` |
| `POST` | `/api/recipes` | frame or agent | Save a recipe | `recipes.js` |
| `DELETE` | `/api/recipes/:id` | frame | Remove a saved recipe | `recipes.js` |
| `GET` | `/api/recipes/:id/image` | frame (as `<img src>`) | Stored saved-recipe photo | `recipes.js` |

Optional features degrade gracefully when not configured: photos return an empty list with
"Add ALBUM_URL to show photos", lists return 503 "Add TODOIST_TOKEN to connect Todoist", weather
returns an error object without coordinates.

## KV caching and per-feed refresh

`CALENDAR` is the single KV namespace used for durable cache across features:

| Key | Feature | TTL / refresh rule |
| --- | --- | --- |
| `calendar` | Calendar | Cron every 10 min; writes only if events/errors changed or hourly heartbeat |
| `photos` | Photo album list | 30 min; stale copy served immediately, re-listed in background via `ctx.waitUntil` |
| `photo:<id>` | Photo bytes | 30 days; sized once with the `IMAGES` binding and stored |
| `recipes` | Saved recipes | No explicit TTL; updated on save/delete |
| `recipe-image:<id>` | Saved recipe photos | No explicit TTL; stored when recipe saved, deleted when recipe removed |

### Calendar

`refresh()` fetches every `CALENDAR_URLS` feed, expands occurrences across a window of 40 days
back and 70 days ahead, and merges them into one sorted event list. If a feed fails, its last good
events from KV are kept so a transient outage doesn't blank the wall display. Holiday feeds (URLs
matching `/holiday/i`) get `holiday: true` on every event.

The cron calls `updateCalendar`, which writes KV only when the merged events/errors changed or the
stored copy is over an hour old. `GET /api/calendar` returns the stored copy immediately; if it is
older than 75 minutes (`STALE_MS`) the request serves the stale copy and uses `ctx.waitUntil` to
refresh KV in the background. `?refresh` bypasses the cache entirely.

### Photos

`listPhotos` returns ids and sizes, never Apple URLs. The album list is cached for 30 minutes; when
stale, the cached list is answered immediately and `getAlbum` re-fetches iCloud in the background.
`photoResponse` serves each image from KV (`photo:<id>`) after the first fetch, re-listing the
album once if a link expired. Both album-list and individual-image responses carry
`private, max-age=604800, immutable` because the id embeds the image fingerprint and the content
can't change.

### Recipes

Saved recipes are one KV value (`recipes`). A saved recipe's photo is copied and resized into KV at
save time (`recipe-image:<id>`), so the frame never has to trust or fetch an external site. Recipe
images are also served with `private, max-age=604800, immutable`. TheMealDB upstream responses are
cached on the edge for a day via `cf: { cacheTtl: 86400, cacheEverything: true }`; random explore
results are `no-store`.

## Responses, caching and errors

`json(body, status, cache)` is the one JSON response helper in `index.js` and defaults to
`Cache-Control: no-store`, because most data changes and the frame manages its own freshness.
Exceptions are deliberate and local to their route:

- `GET /api/recipes/explore` without `?random` is `private, max-age=86400`.
- `GET /api/photos/:id` and `GET /api/recipes/:id/image` are `private, max-age=604800, immutable`.
- Message routes are answered by the Durable Object with `Cache-Control: no-store`.

Weather fetches Open-Meteo through the edge cache with `cacheTtl: 600`.

Any exception inside the API block is logged with its path and returned as
`502 {"error": "<message>"}`; unknown routes return `404 {"error": "not found"}`.

## Cron

`scheduled()` runs every 10 minutes (`triggers.crons`) and calls `updateCalendar`, which writes KV
only when the merged calendar changed or the stored copy is over an hour old, and logs the event
and error counts.

## Tests

`dashboard/worker/api.test.js` exercises routing, auth, cache semantics and the cron. Key cases
include: the dashboard key protects API routes while assets are public; stale calendar data is served
immediately while the background refresh updates KV; photo album and image caching hide Apple URLs
and reuse KV bytes; agent-token posting is restricted to messages/recipes and cannot read; recipe
saving stores images and de-duplicates by `ref`; and message posts/dismissals push live to
connected WebSocket frames.
