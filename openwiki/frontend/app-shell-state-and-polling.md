---
type: architecture
title: App shell, state and polling
description: How the Svelte 5 dashboard boots on the frame, manages shared state, polls each feed only while something needs it, and handles idle, slideshow, settings, demo mode and the small DOM.
tags: [svelte, state, polling, localstorage, idle, demo-mode, boot]
verified:
  - by: openwiki/0.7.2
    at: 2026-10-13T17:09:19.129Z
sources:
  - id: openwiki-source-1749acaa35a5ed1522bc474a
    resource: repo://dashboard/index.html
  - id: openwiki-source-262fee19998c22821ad4184a
    resource: repo://dashboard/src/App.svelte
  - id: openwiki-source-ca659ddfa04bafbd6bb2161a
    resource: repo://dashboard/src/components/Settings.svelte
  - id: openwiki-source-136e4998beec00d02c60296f
    resource: repo://dashboard/src/lib/api.js
  - id: openwiki-source-3a4039a222339b2ae26827c1
    resource: repo://dashboard/src/lib/state.svelte.js
  - id: openwiki-source-74255eeb4097b4c275c2f7c4
    resource: repo://dashboard/src/main.js
generated: { by: "openwiki/0.7.2", at: "2026-10-13T17:09:19.129Z" }
---

# App shell, state and polling

The frontend in `dashboard/src/` is a single Svelte 5 app (runes, no SvelteKit) built by Vite and served by the Worker. It is designed to run unattended 24/7 on a slow Android frame: it boots even when offline, heals itself if the bundle fails, polls only what is on screen, and avoids re-rendering when nothing changed.

## Boot

- `index.html` lays out at a fixed 1280 CSS px width. The 1920×1080 FRAME156 displays it at 1.5× (1280×720); a 10" frame displays it at 1×. It deliberately omits `initial-scale`, because Android WebView would otherwise pin the scale and lay out at the full panel width. It shows a "Starting…" placeholder, prints any script error or unhandled rejection on screen so the frame can be diagnosed without a cable, and reloads the page after 10 s unless the app has set `window.__booted` or has failed visibly.
- `src/main.js` clears the placeholder, mounts `App`, starts the optional on-screen performance overlay (`src/diag.js`), and sets `window.__booted`. The diag overlay is toggled with `?diag` or `?diag=0` and remembered in localStorage.
- `src/lib/api.js` stores the frame key from `?key=` in `localStorage` on first open. Every API call then sends it as a bearer token, and `withKey()` appends it to image and WebSocket URLs because `<img>` and `WebSocket` cannot send custom headers.

The kiosk app adds its own retry and watchdog around the page load (see [kiosk](../device/kiosk-app-and-frame.md)).

## Layout (`src/App.svelte`)

- A top bar with a segmented tab control starting at the left edge: Home, Calendar, Groceries, Tasks, Recipes, and Music only when the frame has a Home Assistant URL and token.
- On the right: the current time (except on Home), weather icon and temperature, a play button that starts the slideshow immediately, and the Settings gear.
- Only the active view is mounted in `<main>`, and no dashboard view exists in the DOM while the clock screen is up. Hidden screens therefore do no per-minute work and keep memory small.
- Overlays are layered above the view in this order: Settings (hidden while idle), the idle `Ambient` clock screen, and agent messages over everything (held back in demo mode).

On mount `App.svelte` calls `start()` to begin pollers and idle handling, `connectHA()` for Home Assistant, and after 15 s enables background photo preloading. An effect immediately loads a list when its tab opens, so Groceries is fresh even though it is not polled while closed.

## Shared state (`src/lib/state.svelte.js`)

`ui` is the global UI `$state` object: `tab`, `idle`, `theme`, `settingsOpen`, and the persisted settings (`themePref`, `idleMinutes`, `nightPhotos`, `demo`, `clockColor`, `announceOn`). Each setting is stored under a `frame-*` key in `localStorage`. `setSetting(key, value)` is the single place a setting changes and persists, so theme changes, idle re-arming, and demo-mode transitions all happen there.

Feed state objects (`calendar`, `weather`, `photos`, `lists`, `recipes`, `messages`, `clock`) are also `$state`. They are seeded at boot from the last good copy in localStorage so the frame shows data while offline. The exception is demo mode: `calendar`, `lists` and `photos` are seeded with invented demo data, and no demo data is ever written to the real feed caches.

### Polling contract: `every()`, `single()`, `changed()`, `remember()`, `forget()`

| Mechanism | Where | What it does |
| --- | --- | --- |
| `every(ms, fn, when)` | `state.svelte.js` | Runs `fn` now (if `when()` allows) and then every `ms`. The next run is scheduled only after the previous one finishes, so slow requests never stack up. Runs are skipped entirely while `when()` is false, which is how hidden tabs and the clock screen stop their feeds. |
| `single(key, fn)` | `state.svelte.js` | Guarantees one in-flight request per feed. A scheduled poll, a manual refresh and a tab-open load all share the same promise, so a slow request is never duplicated. |
| `changed(key, value)` | `api.js` | Compares the new JSON with the last copy (seeded from localStorage at first call) and returns `false` when unchanged. Unchanged polls skip both the state assignment and the localStorage write, so nothing re-renders and no flash storage is wasted. |
| `remember(key, value)` | `api.js` | Records a local edit (for example after completing a grocery item) so the next comparison treats the optimistic state as the new baseline. |
| `forget(...keys)` | `api.js` | Invalidates the stored baseline for those keys, forcing the next `changed()` to report a difference. Used when demo data must be replaced by real data. |

### What polls, and when

| Feed | Interval | Only while |
| --- | --- | --- |
| Clock + theme | every minute, aligned to the minute boundary | always |
| Calendar | 5 min | always |
| Weather | 15 min | always |
| Tasks (`todo`) | 1 min | dashboard is showing and not idle (`!ui.idle`) |
| Groceries | 1 min | Groceries tab is open and not idle |
| Photos list | 5 min (plus once at start) | clock screen is up and photos would be visible, or the one-time startup load |
| Messages | pushed over WebSocket; 1 min HTTP fallback | HTTP fallback only while the socket is down |

Saved recipes are loaded when the Recipes tab or Saved opens; details are on each feed's page:
[calendar](../feeds/calendar.md), [weather](../feeds/weather-and-theme.md),
[Todoist](../feeds/todoist-lists.md), [photos](../feeds/photos-and-slideshow.md),
[messages](../features/agent-messages.md), [recipes](../features/recipes.md).

## Idle and the clock screen

Idle is driven by a `pointerdown` listener that calls `rearmIdle()`. If `idleMinutes` is 0 the timer is disabled. Otherwise a single timeout fires after the configured delay, default 5 minutes. When it fires, or when the play button calls `startSlideshow()`:

- `ui.tab` is reset to Home,
- Settings is closed,
- `ui.idle` becomes true,
- `loadPhotos()` is called so the slideshow has current images.

The clock screen is rendered by `Ambient.svelte` while `ui.idle` is true. It shows the time in the chosen `clockColor`, date, weather, the next upcoming event, and any currently playing music. The family photo slideshow runs behind the clock when photos are available and `photosVisible()` is true. At night (`ui.theme === 'dark'`) the text is dimmed and the photos are dimmed even further; if Settings → Photos at night is off, `photosVisible()` returns false at night and the slideshow clears, leaving only the clock text on black.

Photo preloading keeps the slideshow instant on slow Wi-Fi. `App.svelte` starts calling `prepare()` 15 s after boot whenever photos would be visible and the frame is not in demo mode. `Ambient.svelte` advances slides every 30 s via `takeSlide()`, which returns an already-downloaded slide and immediately starts preparing the next one. The preloader is paused when the dashboard is in use because `prepare()` is only triggered by the warm-up effect or the idle screen.

Tapping the clock screen calls `exitIdle()`, which sets `ui.idle = false` and immediately reloads Tasks, since Home shows them.

## Demo mode

Settings → Demo mode swaps in invented data from `src/lib/demo.js`: a realistic calendar relative to today, a Tasks board with sections and assignees, and grocery aisles. Demo mode:

- never shows family photos (`photos.items = []`),
- holds agent messages back (`Message` is not rendered),
- never writes to Todoist (`completeItem`, `addItem`, `addToGroceries` all short-circuit),
- never caches demo data as real feed state.

When demo mode is toggled, `setSetting('demo', …)` clears the demo list caches, calls `forget()` for calendar, photos and both lists and their metadata, and reloads them. This forces real data to redraw even if it happens to match what demo mode had shown. Switching demo off therefore brings back the real calendar, lists and photos from the server; switching it on rebuilds fresh demo data relative to the current day.

## Settings persistence and theme

All settings live in `localStorage` as `frame-*` keys and survive reboots. The settings sheet (`components/Settings.svelte`) edits them through `setSetting()`, except brightness, which is controlled through the kiosk bridge (`window.FrameKiosk`) and is only available inside the kiosk app.

Theme can be `auto`, `light` or `dark`. In `auto`, `applyTheme()` uses the current day's sunrise and sunset from the weather feed; until weather arrives it falls back to 7 AM / 7 PM. The `?theme=` query parameter still overrides the stored preference for ADB setup. `applyTheme()` is called every minute with the clock tick and again whenever new weather data arrives.

## Reload and self-healing

Settings → Reload calls `GET /api/calendar?refresh` to force a fresh calendar fetch from upstream feeds, then reloads the page. The 10 s watchdog in `index.html` does the same if the app fails to boot, so a bad deploy or a crashed bundle recovers automatically.
