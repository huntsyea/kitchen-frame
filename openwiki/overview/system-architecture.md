---
type: architecture
title: System architecture
description: End-to-end view of the family photo-frame dashboard - an Android kiosk WebView on the frame, a Svelte app and API served by one Cloudflare Worker that proxies calendars, weather, Todoist, iCloud photos and TheMealDB and hosts the agent message room, plus a direct LAN link to Home Assistant.
tags: [architecture, overview, cloudflare-workers, svelte, android, kiosk]
verified:
  - by: openwiki/0.7.2
    at: 2026-10-13T17:09:19.129Z
sources:
  - id: openwiki-source-a2371d6362e5db4bc834ad03
    resource: repo://CLAUDE.md
  - id: openwiki-source-262fee19998c22821ad4184a
    resource: repo://dashboard/src/App.svelte
  - id: openwiki-source-81909880e1b8359442697bb1
    resource: repo://dashboard/src/lib/ha.svelte.js
  - id: openwiki-source-e445b2c9ec766aa6a4917d15
    resource: repo://dashboard/vite.config.js
  - id: openwiki-source-47e567cb98956edcb53bcbd3
    resource: repo://dashboard/worker/api.test.js
  - id: openwiki-source-761c8b9c5f5e1234a74d94a4
    resource: repo://dashboard/worker/index.js
  - id: openwiki-source-8db6682af62a097684283c37
    resource: repo://dashboard/worker/messages.js
  - id: openwiki-source-272749880eb665924bb98bdd
    resource: repo://dashboard/worker/photos.js
  - id: openwiki-source-fd5601bf85cef5c591f92e95
    resource: repo://dashboard/worker/todoist.js
  - id: openwiki-source-0d4db84e2b7fee7556be759e
    resource: repo://dashboard/wrangler.jsonc
  - id: openwiki-source-28fc9369ef5fcb7aea5d2dcd
    resource: repo://docs/frame.md
  - id: openwiki-source-d704bf92ab046c61656748c7
    resource: repo://kiosk/AndroidManifest.xml
  - id: openwiki-source-b73a7f32e78736cbd3e31ddc
    resource: repo://kiosk/src/com/huntsyea/frame/MainActivity.java
  - id: openwiki-source-3a44815832a872f4778f822b
    resource: repo://SECURITY.md
generated: { by: "openwiki/0.7.2", at: "2026-10-13T17:09:19.129Z" }
---

# System architecture

The project turns a rooted Android photo frame into a kitchen wall dashboard: clock, weather, the merged family calendar, Todoist tasks and groceries, recipes, music controls, agent messages, and a family photo slideshow when idle. The runtime has three trust boundaries: the Android kiosk WebView, the Svelte app running inside it, and the Cloudflare Worker plus its Durable Object. The Svelte app and API are served by the same Worker; Home Assistant is the only integration the frame talks to directly.

## The pieces

```text
┌──────────── Frame (Android 8.1, WebView 106) ────────────┐
│ kiosk app com.huntsyea.frame (HOME launcher, WebView)    │
│   └─ Svelte app (dashboard/src) ───────────────┐          │
│        │ https + key            │ ws:// on LAN  │          │
└────────┼─────────────────────────┼─────────────────┘          
         ▼                       ▼
  Cloudflare Worker            Home Assistant (+ Music Assistant, Piper TTS)
  (dashboard/worker)
    ├─ static assets (the Svelte build)
    ├─ /api/calendar  ── iCal feeds (iCloud, Google, holidays)
    ├─ /api/weather   ── Open-Meteo
    ├─ /api/lists     ── Todoist API v1
    ├─ /api/photos    ── iCloud shared album (CloudKit)
    ├─ /api/recipes   ── TheMealDB + saved recipes
    └─ /api/messages  ── MessageRoom Durable Object ◄── AI agents (AGENT_TOKEN)
```

| Part | Where | Page |
| --- | --- | --- |
| Kiosk app and device | `kiosk/`, `docs/frame.md` | [Kiosk app and the frame](../device/kiosk-app-and-frame.md) |
| Worker entry, auth, caching | `dashboard/worker/index.js` | [Routing, auth and caching](../worker/routing-auth-and-caching.md) |
| Feeds | `dashboard/worker/*.js` | [Calendar](../feeds/calendar.md), [weather](../feeds/weather-and-theme.md), [Todoist](../feeds/todoist-lists.md), [photos](../feeds/photos-and-slideshow.md) |
| Features | | [Agent messages](../features/agent-messages.md), [recipes](../features/recipes.md) |
| Frontend | `dashboard/src/` | [App shell and polling](../frontend/app-shell-state-and-polling.md), [views and design system](../frontend/views-components-and-design-system.md) |
| Home Assistant | `dashboard/src/lib/ha.svelte.js` | [Music and speech](../integrations/home-assistant-music-and-speech.md) |
| Build and deploy | `dashboard/wrangler.jsonc`, `package.json` | [Build, deploy and configuration](../operations/build-deploy-and-configuration.md) |
| Tests | `dashboard/worker/*.test.js` | [Tests and verification](../testing/tests-and-verification.md) |

## Design principles

**The Worker owns every third-party secret and call.** Calendar links, the Todoist token, the iCloud album link and API quirks stay server-side; the frame only knows its own `DASHBOARD_KEY`. Agents get a separate `AGENT_TOKEN` that can post messages and save recipes but cannot read any feed. Home Assistant is the single exception: it lives on the home network, so the frame talks to it directly and credentials are kept only in the frame's localStorage.

**Work around the device instead of fighting it.** The deployed frame is a Pastigio FRAME156 (Android 8.1, WebView 106, Rockchip RK3326, ~1 GB RAM, Mali GPU, 1920×1080 shown as 1280×720 CSS px at DPR 1.5, Wi-Fi around 1 Mbit/s, no battery-backed clock). The code also still respects the older upstream floor (Android 6, Mali-400, 1280×800 at DPR 1). Because of those limits:

- The UI is a small Svelte 5 bundle with flat CSS, built for Chrome 106, laid out at 1280 CSS px, mounting only the visible view.
- Photos are proxied, cached in KV and resized once for the screen; the next slide is decoded ahead of time.
- The kiosk keeps retrying through the 2008 boot clock and the page reloads itself if it fails to start.
- Every feed is polled only while visible, one request at a time, and unchanged data does not re-render; messages are pushed over a WebSocket instead of polled.

`CLAUDE.md` carries the actual numbers and performance rules; the full device record and undo commands are in `docs/frame.md`.

**Keep showing something.** Each feed's last good copy is kept in KV on the Worker and in localStorage on the frame. A failing calendar feed falls back to its previous events; the photo list falls back to the last listing. The wall display should never go blank because one upstream blipped.

## Runtime domains and trust boundaries

### 1. Kiosk WebView (`kiosk/`)

`kiosk/src/com/huntsyea/frame/MainActivity.java` builds a full-screen WebView that loads the dashboard URL, keeps the screen on, and registers as the HOME launcher so the frame boots straight into it. Key responsibilities:

- **Boot resilience.** The frame has no battery-backed clock, so power-up starts at 2008 until Wi-Fi time sync. SSL failures therefore happen on first load; the kiosk never bypasses certificates but schedules a 10 s retry and runs a 30 s watchdog that reloads if the page never finishes.
- **URL storage.** The dashboard URL is set once over ADB (`adb shell am start -n com.huntsyea.frame/.MainActivity -d '<url with ?key=>'`) and is persisted in Android shared preferences across reboots.
- **Mixed-content bridge.** `WebSettings.setMixedContentMode(MIXED_CONTENT_ALWAYS_ALLOW)` lets the https page reach plain `http://` Home Assistant on the LAN; the JavaScript bridge `window.FrameKiosk` exposes brightness control and is only meaningful inside this WebView.
- **Escape hatch.** Holding two fingers still for 2 s opens a dialog to reload the dashboard or open Android Settings.
- **Remote debugging.** Chrome remote debugging is enabled only when the activity is launched with `--ez debug true`; normal launches disable it.

### 2. Svelte app (`dashboard/src/`)

A Svelte 5 runes app (no SvelteKit) built by Vite with `chrome106` / `chrome61` targets. It is mounted by `main.js` and bootstrapped from localStorage.

- **Authentication.** `src/lib/api.js` stores the key passed as `?key=` in `localStorage` under `frame-key`, then sends it as a bearer token. Image and WebSocket GET requests carry the key in the URL because `<img>` and `WebSocket` cannot send custom headers.
- **State and polling.** `src/lib/state.svelte.js` owns the feed `$state` objects and the pollers. `start()` kicks off the minute-aligned clock, calendar (5 min), weather (15 min), Tasks (1 min), Groceries (1 min only while its tab is open), and photos (5 min only while the clock screen is up). Messages use a WebSocket; a 1 min HTTP fallback runs only while the socket is down.
- **Idle and slideshow.** After a configurable idle timeout the app unmounts the dashboard, sets `ui.idle = true`, and renders `Ambient` with a clock, date, weather, next event, now playing and the family photo slideshow. Tapping wakes it back to Home.
- **Home Assistant.** `src/lib/ha.svelte.js` connects directly to `ws://<home-assistant>:8123/api/websocket` from the browser; the URL and long-lived token live only in `localStorage` (`frame-ha-url`, `frame-ha-token`). The Music tab only appears when a token is present.
- **Demo mode.** Settings → Demo mode swaps in invented data from `demo.js`, never writes to Todoist, never shows family photos, and suppresses agent messages.

### 3. Cloudflare Worker (`dashboard/worker/`)

One Worker serves both the built app and the API. `wrangler.jsonc` wires:

- `ASSETS` for the Vite-built static files;
- `CALENDAR` KV for calendar, photo list, photo bytes, saved recipes and recipe images;
- `MESSAGES` Durable Object binding to the `MessageRoom` class;
- `IMAGES` for one-time image resizing;
- a `*/10 * * * *` cron to refresh the calendar.

`worker/index.js` routes:

| Route | What it does |
| --- | --- |
| `GET /` / `GET /index.html` | Serves the page with `Cache-Control: no-store` so the frame never runs a stale build after deploy. Hashed assets are served from `ASSETS` as-is. |
| `GET /api/calendar` | Returns merged iCal feeds from KV; refreshes in the background if stale. |
| `GET /api/weather` | Current + 5-day from Open-Meteo. |
| `GET /api/lists/:list` | Todoist project tasks, sections and collaborators. |
| `POST /api/lists/:list` | Adds one or many items. |
| `POST /api/lists/:list/:id/done` | Completes an item. |
| `GET /api/photos` | Album listing (ids and sizes only, no Apple URLs). |
| `GET /api/photos/:id` | Proxies, resizes and caches a single photo. |
| `GET /api/recipes/explore` | TheMealDB search/random/lookup. |
| `GET /api/recipes` | Saved recipes. |
| `POST /api/recipes` | Saves a recipe (frame key or `AGENT_TOKEN`). |
| `DELETE /api/recipes/:id` | Removes a saved recipe. |
| `GET /api/recipes/:id/image` | Saved recipe photo. |
| `POST /api/messages` | Agents post a message (`AGENT_TOKEN`). |
| `GET /api/messages` | Pending messages. |
| `GET /api/messages/live` | WebSocket pushed on every change. |
| `POST /api/messages/:id/dismiss` | Dismisses a message. |

`authorized()` checks `Authorization: Bearer <DASHBOARD_KEY>` for most routes and allows the key in the query string only for photo, recipe image and WebSocket routes.

## Data flow at a glance

1. The kiosk loads `https://<subdomain>.workers.dev/?key=<DASHBOARD_KEY>`; the Worker serves the page `no-store` and the hashed assets from the asset store.
2. The app boots from localStorage, then `start()` begins the pollers and opens the message WebSocket; `connectHA()` connects to Home Assistant if a token is configured.
3. The cron refreshes the calendar into KV every 10 minutes, writing only when events/errors changed or hourly as a heartbeat. Other feeds are fetched on request and cached at the edge or in KV.
4. Taps write back through the Worker (complete/add Todoist items, save/remove recipes, dismiss messages) or straight to Home Assistant (music controls).
5. After the idle timeout the app unmounts the dashboard and shows the clock screen and slideshow; agent messages overlay everything.

## Where secrets live

| Secret | Location | Reaches frame? |
| --- | --- | --- |
| `DASHBOARD_KEY` | Worker secret; also stored once via `?key=` in frame localStorage | yes, as bearer token |
| `AGENT_TOKEN` | Worker secret only | no |
| `CALENDAR_URLS` | Worker secret | no |
| `TODOIST_TOKEN` | Worker secret | no |
| `ALBUM_URL` | Worker secret | no |
| `WEATHER_LAT`, `WEATHER_LON`, `DISPLAY_TZ` | Worker vars/secrets | no |
| `TODOIST_GROCERY_PROJECT`, `TODOIST_TODO_PROJECT` | Worker vars in `wrangler.jsonc` | no |
| Home Assistant URL + token | frame localStorage only (`frame-ha-url`, `frame-ha-token`) | yes |

## Extension points

- New feeds usually belong as a Worker module under `dashboard/worker/` plus a poller/state entry in `src/lib/state.svelte.js`. Avoid adding ad-hoc `setInterval` calls; reuse `every()`, `single()` and `changed()`.
- New tabs need a view under `src/views/`, an entry in `App.svelte`'s `TABS` array, and lazy mounting inside the existing `{#if ui.tab === '...'}` block.
- Agent-facing features can reuse the split-token pattern: an `AGENT_TOKEN`-only POST route that writes data, plus the frame key for reads.
- Kiosk-only behaviors (brightness, boot URL, mixed-content allowance) are gated by `window.FrameKiosk`; keep graceful degradation for browser dev.

## Tests that matter

`dashboard/worker/api.test.js` exercises the end-to-end flow: auth separation between `DASHBOARD_KEY` and `AGENT_TOKEN`, Todoist list ordering and bulk add, weather shaping, stale-calendar background refresh, iCloud album resolution and image caching, message push via the Durable Object, and recipe save/deduplication/image storage. It is the best place to verify changes that touch routing, auth, caching or any feed integration.
