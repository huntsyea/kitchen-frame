---
type: guide
title: Quickstart
description: Entry point to the wiki for the photo-frame family dashboard - what it is, how to run, test and deploy it, and which wiki page to read for each kind of change.
tags: [quickstart, overview, routing, getting-started]
verified:
  - by: openwiki/0.7.2
    at: 2026-11-14T14:55:31.391Z
sources:
  - id: openwiki-source-8037e2358a2c4f9b2c722a11
    resource: repo://AGENTS.md
  - id: openwiki-source-a2371d6362e5db4bc834ad03
    resource: repo://CLAUDE.md
  - id: openwiki-source-ef1547a00ac663dc346d3ac5
    resource: repo://dashboard/.dev.vars.example
  - id: openwiki-source-51dca17ef0b6465be67eaf89
    resource: repo://dashboard/package.json
  - id: openwiki-source-81909880e1b8359442697bb1
    resource: repo://dashboard/src/lib/ha.svelte.js
  - id: openwiki-source-e445b2c9ec766aa6a4917d15
    resource: repo://dashboard/vite.config.js
  - id: openwiki-source-761c8b9c5f5e1234a74d94a4
    resource: repo://dashboard/worker/index.js
  - id: openwiki-source-0d4db84e2b7fee7556be759e
    resource: repo://dashboard/wrangler.jsonc
  - id: openwiki-source-28fc9369ef5fcb7aea5d2dcd
    resource: repo://docs/frame.md
  - id: openwiki-source-b2adbd28a1cedffedb38d142
    resource: repo://docs/research.md
  - id: openwiki-source-23775c3de52f3ab95a13cb8b
    resource: repo://README.md
generated: { by: "openwiki/0.7.2", at: "2026-11-14T14:55:31.391Z" }
---

# Quickstart

**What this is:** a family dashboard for a rooted Pastigio FRAME156 Android photo frame hanging in a kitchen. A tiny Android kiosk app (`kiosk/`) hosts a full-screen WebView that loads a Svelte 5 web app (`dashboard/src/`). The app is served by one Cloudflare Worker (`dashboard/worker/`) that proxies the merged family calendar, weather, Todoist lists, an iCloud shared photo album, TheMealDB recipes, and AI-agent messages. The frame talks to Home Assistant directly on the LAN for music controls, now-playing state, and text-to-speech announcements.

Read [system architecture](./overview/system-architecture.md) first, then follow the task routing table below to find the page that owns the area you need to change.

Before asking an agent to pull just-in-time context from OpenWiki, read the retrieval discipline in [`AGENTS.md`](../AGENTS.md).

## Run, test, deploy

```sh
cd dashboard
npm install
npm test            # node --test worker/*.test.js
npm run dev         # Vite dev server + Cloudflare Worker; open /?key=<DASHBOARD_KEY> once
npm run deploy      # vite build && wrangler deploy
```

After deploy, tap **Settings → Reload** on the frame (or use the kiosk escape hatch) so it picks up the new build. Cloudflare can take ~30 s to serve the new version everywhere, so a reload sooner may show the old build until the next reload.

Secrets, KV/Durable Object bindings, plan limits and full deployment steps: [build, deploy and configuration](./operations/build-deploy-and-configuration.md).

Local development needs a `dashboard/.dev.vars` file. Copy `dashboard/.dev.vars.example` and fill in at least `CALENDAR_URLS` and `DASHBOARD_KEY`.

## Rules that apply to every change

- The frame runs **WebView 106** on a slow CPU and weak Mali GPU, and the build targets are `chrome106` / `chrome61`. Do not use `oklch()`, `color-mix()`, CSS nesting, `:has()`, or 4/8-digit hex colours. Keep fills flat, avoid shadows/blurs/backdrop filters, and mount only the currently visible view (`{#if}`, not hidden stacked views). See [views and design system](./frontend/views-components-and-design-system.md) and the research notes in `docs/research.md`.
- Measure before and after any UI change with `?diag` (fps, jank, DOM count, decoded image megapixels, heap). Animate only `transform` and `opacity`.
- Feeds poll only while visible, one request at a time, and unchanged data must not re-render. Reuse the `every()`, `single()` and `changed()` primitives in `dashboard/src/lib/state.svelte.js` instead of adding ad-hoc timers. No per-second timers when a per-minute one will do. See [app shell and polling](./frontend/app-shell-state-and-polling.md).
- **Secrets stay on the Worker or in the frame's `localStorage`.** Never print or commit values from `.dev.vars`, `.prod.vars`, or `.frame.vars`. The dashboard key, Todoist token, calendar URLs, agent token and album URL are Worker secrets. The Home Assistant URL and token live only in frame `localStorage`, pushed over ADB from `.frame.vars`.
- Verify UI changes in a headless browser at 1280×720 using demo mode, not by operating the family's frame. See [tests and verification](./testing/tests-and-verification.md).

## Where to go for a task

| If you need to… | Read |
| --- | --- |
| Understand the whole system end-to-end | [System architecture](./overview/system-architecture.md) |
| Add or change an API route, auth model or caching | [Worker routing, auth and caching](./worker/routing-auth-and-caching.md) |
| Fix calendar parsing, time zones, recurring events or holidays | [Calendar feed](./feeds/calendar.md) |
| Change weather display or light/dark switching | [Weather and theme](./feeds/weather-and-theme.md) |
| Change the Groceries or Tasks lists (Todoist) | [Todoist lists](./feeds/todoist-lists.md) |
| Change the slideshow, photo caching or idle screen | [Photos and idle slideshow](./feeds/photos-and-slideshow.md) |
| Change agent messages, live push, dismissal or read-aloud | [Agent messages](./features/agent-messages.md) |
| Change Recipes (Explore, Saved, add to groceries) | [Recipes](./features/recipes.md) |
| Change boot, tabs, polling, idle, settings or demo mode | [App shell, state and polling](./frontend/app-shell-state-and-polling.md) |
| Change a screen's layout, styles, tokens or icons | [Views, components and design system](./frontend/views-components-and-design-system.md) |
| Change music controls, now playing or TTS | [Home Assistant: music and speech](./integrations/home-assistant-music-and-speech.md) |
| Change the Android kiosk or operate the device | [Kiosk app and frame](./device/kiosk-app-and-frame.md) |
| Deploy, configure secrets or check Cloudflare usage | [Build, deploy and configuration](./operations/build-deploy-and-configuration.md) |
| Add or fix tests, or verify a UI change | [Tests and verification](./testing/tests-and-verification.md) |

Human-facing docs in the repo: `README.md` (setup and overview), `AGENTS.md` (OpenWiki retrieval discipline), `CLAUDE.md` (agent rules), `PRODUCT.md` and `DESIGN.md` (briefs), `docs/frame.md` (device record and undo commands), `docs/messages.md` and `docs/recipes.md` (agent API contracts), and `docs/research.md` (upstream findings and constraints).
