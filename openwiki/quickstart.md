---
type: guide
title: Quickstart
description: Entry point to this repository's wiki - what the photo-frame family dashboard is, how to run, test and deploy it, and which page to read for each kind of change.
tags: [quickstart, overview, routing, getting-started]
sources:
  - id: openwiki-source-8037e2358a2c4f9b2c722a11
    resource: repo://AGENTS.md
  - id: openwiki-source-a2371d6362e5db4bc834ad03
    resource: repo://CLAUDE.md
  - id: openwiki-source-51dca17ef0b6465be67eaf89
    resource: repo://dashboard/package.json
  - id: openwiki-source-0d4db84e2b7fee7556be759e
    resource: repo://dashboard/wrangler.jsonc
generated: { by: "openwiki/0.7.2", at: "2026-10-13T17:09:19.129Z" }
verified:
  - by: openwiki/0.7.2
    at: 2026-10-13T17:09:19.129Z
---

# Quickstart

**What this is:** a family dashboard for a rooted Pastigio FRAME156 Android photo frame in a
kitchen. A tiny Android kiosk app (`kiosk/`) shows a Svelte 5 web app (`dashboard/src/`) served
by one Cloudflare Worker (`dashboard/worker/`). The Worker proxies the family calendar, weather,
Todoist lists, an iCloud photo album and TheMealDB, and hosts a Durable Object that pushes
messages from AI agents to the screen. The frame talks to Home Assistant directly on the LAN for
music and speech. Start with [system architecture](./overview/system-architecture.md).

Before asking an agent to pull just-in-time context from OpenWiki, read the retrieval discipline
in [AGENTS.md](../AGENTS.md).

## Run, test, deploy

```sh
cd dashboard
npm install
npm test            # node --test worker/*.test.js
npm run dev         # local app + Worker; open /?key=<DASHBOARD_KEY> once
npm run deploy      # vite build && wrangler deploy
```

Then tap Settings → Reload on the frame to load the new build. Secrets, bindings and plan usage:
[build, deploy and configuration](./operations/build-deploy-and-configuration.md).

## Rules that apply to every change

- The frame runs **WebView 106** on a slow CPU and GPU: no `oklch()`, `color-mix()`, CSS nesting,
  `:has()` or 4/8-digit hex; flat fills, no shadows/blurs; keep the `chrome106` / `chrome61`
  build targets; mount only the visible view. See
  [views and design system](./frontend/views-components-and-design-system.md).
- Feeds poll only while visible, one request at a time, and unchanged data must not re-render —
  reuse `every()`, `single()` and `changed()` rather than adding ad-hoc timers. See
  [app shell and polling](./frontend/app-shell-state-and-polling.md).
- Secrets stay on the Worker (or, for Home Assistant, only on the frame). Never print or commit
  values from `.prod.vars`, `.dev.vars` or `.frame.vars`.
- Verify UI in a headless browser at 1280×720 (demo mode), not by operating the family's frame.
  See [tests and verification](./testing/tests-and-verification.md).

## Where to go for a task

| If you need to… | Read |
| --- | --- |
| Understand the whole system | [System architecture](./overview/system-architecture.md) |
| Add or change an API route, auth or caching | [Worker routing, auth and caching](./worker/routing-auth-and-caching.md) |
| Fix calendar parsing, time zones, recurring events, holidays | [Calendar feed](./feeds/calendar.md) |
| Change weather display or light/dark switching | [Weather and day/night theme](./feeds/weather-and-theme.md) |
| Change Tasks or Groceries (Todoist) | [Todoist lists](./feeds/todoist-lists.md) |
| Change the slideshow, photo caching or idle screen | [Photos and idle slideshow](./feeds/photos-and-slideshow.md) |
| Change agent messages, live push or read-aloud | [Agent messages](./features/agent-messages.md) |
| Change Recipes (Explore, Saved, add to groceries) | [Recipes](./features/recipes.md) |
| Change boot, tabs, polling, idle, settings or demo mode | [App shell, state and polling](./frontend/app-shell-state-and-polling.md) |
| Change a screen's layout, styles, tokens or icons | [Views, components and design system](./frontend/views-components-and-design-system.md) |
| Change music controls, now playing or TTS | [Home Assistant: music and speech](./integrations/home-assistant-music-and-speech.md) |
| Change the Android kiosk or do something on the device | [Kiosk app and the frame device](./device/kiosk-app-and-frame.md) |
| Deploy, configure secrets, or check Cloudflare usage | [Build, deploy and configuration](./operations/build-deploy-and-configuration.md) |
| Add or fix tests, or verify a UI change | [Tests and verification](./testing/tests-and-verification.md) |

Human-facing docs in the repo: `README.md` (setup), `AGENTS.md` (OpenWiki retrieval discipline),
`docs/frame.md` (device record and undo commands), `docs/messages.md` and `docs/recipes.md`
(agent API contracts), `docs/research.md` (upstream findings), `DESIGN.md` / `PRODUCT.md` (design
and product briefs), `CLAUDE.md` (agent rules).
