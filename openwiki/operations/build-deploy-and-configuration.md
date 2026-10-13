---
type: operations
title: Build, deploy and configuration
description: How to run the dashboard locally, build and deploy it to Cloudflare Workers, what each binding, variable and secret is for, how the frame picks up a new build, expected Cloudflare usage, and how this wiki is kept up to date.
tags: [deploy, wrangler, vite, cloudflare, configuration, secrets, operations]
verified:
  - by: openwiki/0.7.2
    at: 2026-10-13T16:59:46.542Z
sources:
  - id: openwiki-source-6d4b4e707b8d60b6ccfa3425
    resource: repo://.github/workflows/openwiki-update.yml
  - id: openwiki-source-51dca17ef0b6465be67eaf89
    resource: repo://dashboard/package.json
  - id: openwiki-source-a735d7910a81a35570838e4c
    resource: repo://dashboard/public/_headers
  - id: openwiki-source-e445b2c9ec766aa6a4917d15
    resource: repo://dashboard/vite.config.js
  - id: openwiki-source-761c8b9c5f5e1234a74d94a4
    resource: repo://dashboard/worker/index.js
  - id: openwiki-source-cb5a2109e8a56015671f5cae
    resource: repo://dashboard/worker/weather.js
  - id: openwiki-source-0d4db84e2b7fee7556be759e
    resource: repo://dashboard/wrangler.jsonc
generated: { by: "claude-code", at: "2026-10-13T16:59:46.542Z" }
---

# Build, deploy and configuration

Everything deployable lives in `dashboard/`: one Cloudflare Worker that serves both the built
Svelte app (as static assets) and the `/api` routes. The Android kiosk in `kiosk/` is built and
installed separately (see [kiosk](../device/kiosk-app-and-frame.md)).

## Commands (`dashboard/package.json`)

| Command | What it does |
| --- | --- |
| `npm run dev` | Vite dev server with the Worker running locally through `@cloudflare/vite-plugin` (also reachable on the LAN; `*.getbb.app` allowed for remote port sharing). Secrets come from `.dev.vars` (template: `.dev.vars.example`). |
| `npm test` | `node --test worker/*.test.js` (see [tests](../testing/tests-and-verification.md)). |
| `npm run build` | Production build into `dist/`: JS targeted at `chrome106`, CSS at `chrome61` (see [design system](../frontend/views-components-and-design-system.md)). |
| `npm run deploy` | `vite build && wrangler deploy`. Always build before deploying, or the previous bundle ships. |

Open the app once with `?key=<DASHBOARD_KEY>`; the page remembers the key. `?diag` turns on a
perf overlay (fps, jank, DOM size, image megapixels, heap).

## Worker configuration (`dashboard/wrangler.jsonc`)

| Setting | Purpose |
| --- | --- |
| `main: worker/index.js` | Entry point; also exports the `MessageRoom` Durable Object class. |
| `assets` (`ASSETS`), `run_worker_first: ["/", "/index.html"]` | Built files are plain assets; the Worker serves the page itself so it can mark it `no-store`. `public/_headers` caches hashed `/assets/*` for a year as immutable. |
| `kv_namespaces` (`CALENDAR`) | One KV namespace for the calendar, album list, photo bytes (`photo:<id>`), saved recipes and recipe images. |
| `durable_objects` (`MESSAGES` → `MessageRoom`) + migration `v1` `new_sqlite_classes` | The hibernating message room (see [agent messages](../features/agent-messages.md)). |
| `triggers.crons: */10 * * * *` | Calendar refresh (see [calendar](../feeds/calendar.md)). |
| `images` (`IMAGES`) | One-time resizing of saved-recipe and slideshow photos. |
| `vars` | `TODOIST_GROCERY_PROJECT` = "Grocery List", `TODOIST_TODO_PROJECT` = "Household". |
| `observability` | Workers logs on. |

## Secrets

Set with `npx wrangler secret put <NAME>`; the production values are kept in the gitignored
`dashboard/.prod.vars`. Never print or commit them.

| Secret | Used for |
| --- | --- |
| `DASHBOARD_KEY` | The frame's key for every API call (unset = no check, dev only). |
| `AGENT_TOKEN` | Agents posting messages and saving recipes; reads nothing. |
| `CALENDAR_URLS` | iCal links (iCloud public `webcal://`, Google secret address/holidays). |
| `TODOIST_TOKEN` | Todoist API. |
| `ALBUM_URL` | iCloud shared album link with Public Website on. |
| `WEATHER_LAT`, `WEATHER_LON` | Weather location (optional `WEATHER_UNIT`). |
| `DISPLAY_TZ` (optional) | Fallback zone for floating calendar times. |

Home Assistant credentials are deliberately **not** Worker secrets: they live only in the frame's
localStorage, pushed from the gitignored `.frame.vars` (see
[Home Assistant](../integrations/home-assistant-music-and-speech.md)). Agent tooling on the
developer's machine uses `KITCHEN_FRAME_URL` / `KITCHEN_FRAME_TOKEN` from `~/.zshenv`.

## Getting a new build onto the frame

Because the page is served `no-store` and assets are content-hashed, the frame runs a new build on
its next page load: Settings → Reload (which also forces a calendar refresh), the kiosk's
two-finger escape → Reload, or a restart. It does not reload itself after a deploy. Cloudflare can
take around 30 s to serve a new version everywhere, so a reload right after deploying may still
get the old one. Kiosk changes need a rebuilt APK installed over USB.

## Cloudflare usage

The account is on Workers Paid. Steady use is roughly 1,500–2,000 Worker requests a day (mostly
task and calendar polls; messages are pushed), a few dozen KV writes a day (calendar only on
change or hourly, album list at most every 30 minutes, photos and recipes once each), a mostly
asleep Durable Object, and one image transformation per newly stored photo — all well inside the
plan's included usage. The Free plan's 10 ms cron CPU limit is why the calendar parser pre-filters
feeds.

## Keeping this wiki current

`AGENTS.md` carries the OpenWiki usage block. `.github/workflows/openwiki-update.yml` runs daily
(and on demand): it installs OpenWiki, runs `openwiki code --update`, removes transient run state,
and opens a "docs: update OpenWiki" pull request with the `openwiki/` changes (preserving partial
progress if the run fails). Inference runs on **Ollama Cloud** through OpenWiki's
OpenAI-compatible provider (`https://ollama.com/v1`). It needs an `OLLAMA_API_KEY` repository
secret; until that exists every step is skipped with a notice instead of failing. The model is
the `OPENWIKI_MODEL_ID` repository variable, defaulting to `kimi-k2.7-code`. Pull requests opened
by the workflow's `GITHUB_TOKEN` don't trigger CI, so the admin merges them by bypassing the
required checks (they only touch `openwiki/`).
