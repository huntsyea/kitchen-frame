---
type: design-system
title: Views, components and design system
description: The dashboard's screens and shared components, its flat iOS-widget design tokens with light and dark palettes, the generated Lucide icon set, and the WebView 106 and low-power GPU rules every style must follow.
tags: [svelte, views, components, css, design-tokens, webview-106, icons]
verified:
  - by: openwiki/0.7.2
    at: 2026-10-13T17:09:19.129Z
sources:
  - id: openwiki-source-a49bc3873fe9977f6676320a
    resource: repo://dashboard/scripts/icons.mjs
  - id: openwiki-source-262fee19998c22821ad4184a
    resource: repo://dashboard/src/App.svelte
  - id: openwiki-source-cb58fcd546033995bfd576fe
    resource: repo://dashboard/src/components/Avatar.svelte
  - id: openwiki-source-f1dd99229f424fd284a9fc46
    resource: repo://dashboard/src/components/Icon.svelte
  - id: openwiki-source-c4b38680680ad780caf9b87f
    resource: repo://dashboard/src/components/TaskRow.svelte
  - id: openwiki-source-e12fdae11ea7713285efd699
    resource: repo://dashboard/src/lib/format.js
  - id: openwiki-source-708fd2723f1c868a90846112
    resource: repo://dashboard/src/style.css
  - id: openwiki-source-0709ad466b2ea97742fcdea4
    resource: repo://dashboard/src/views/Ambient.svelte
  - id: openwiki-source-2dc3fe6d8316a9b6f04164fb
    resource: repo://dashboard/src/views/Home.svelte
  - id: openwiki-source-51ad52cbd5c10d5789425706
    resource: repo://dashboard/src/views/Month.svelte
  - id: openwiki-source-b71f48d25054178a3449df1f
    resource: repo://dashboard/src/views/Recipes.svelte
  - id: openwiki-source-b1a66f44fa52ae21cd5c82ec
    resource: repo://dashboard/src/views/Week.svelte
  - id: openwiki-source-e445b2c9ec766aa6a4917d15
    resource: repo://dashboard/vite.config.js
generated: { by: "openwiki/0.7.2", at: "2026-10-13T17:09:19.129Z" }
---

# Views, components and design system

The dashboard looks like "calm, flat iOS widgets": large type readable from across a kitchen, one accent per widget, and no decoration the frame's low-power GPU would have to paint. `DESIGN.md` and `.impeccable/design.json` are the full design record; this page covers how the code realises them.

## Hard platform rules

The frame runs Android WebView 106 on an RK3326 with a Mali GPU (see [kiosk and device](../device/kiosk-app-and-frame.md)). Styles must:

- avoid `oklch()`, `color-mix()`, CSS nesting, `:has()` and 4/8-digit hex colours (use `rgba()` for tints);
- use flat fills only: no shadows, blurs or filters;
- lay out for a 1280 CSS px viewport (1280×720 on the frame at 1.5×).

The build enforces part of this: `vite.config.js` targets `chrome106` for JS and `chrome61` for CSS, deliberately lower so the minifier never rewrites `rgba()` into 8-digit hex, which that WebView rejects.

## Tokens (`src/style.css`)

All colours are CSS custom properties defined twice, under `:root, [data-theme="light"]` and `[data-theme="dark"]`, using the iOS system palette: ground, sheet, track and thumb surfaces; label/secondary/tertiary text; separators; blue/orange/red/yellow accents with separate `-text` variants that meet 4.5:1 on sheets; and four calendar colours (`--cal0`…`--cal3`, each with a `-tint`). `calVars(e)` in `src/lib/format.js` maps an event's feed index to those variables. Switching theme is one attribute change on `<html>` (see [weather and theme](../feeds/weather-and-theme.md)).

Global rules: `box-sizing: border-box`, system font stack at 18px, no text selection or tap highlight, unstyled buttons, tabular numerals via `.num`, a visible focus outline, and `.sheet` — the widget primitive (white/dark card, 28px radius, 24×26px padding).

**The text-accent rule.** Use the `-text` accent tokens for coloured text (e.g. links, overdue labels); use the plain accents for fills, rings and icons.

## Icons

`scripts/icons.mjs` generates `src/lib/icons.js` from `lucide-static` for a fixed list of names (UI glyphs and weather states); run `node scripts/icons.mjs` after adding one. `Icon.svelte` renders them as 24px-grid SVGs with 2px round strokes using `currentColor`. Icons are never drawn by hand.

## App shell (`src/App.svelte`)

The shell layers the screen:

- A top bar with a segmented tab control starting at the left edge: Home, Calendar, Groceries, Tasks, Recipes, and Music only when the frame has a Home Assistant URL and token.
- On the right: the current time (except on Home), weather icon and temperature, a play button that starts the slideshow immediately, and the Settings gear.
- Only the active view is mounted in `<main>`, and no dashboard view exists in the DOM while the clock screen is up. Hidden screens therefore do no per-minute work and keep memory small.
- Overlays are layered above the view in this order: Settings (hidden while idle), the idle `Ambient` clock screen, and agent messages over everything (held back in demo mode).

See [app shell, state and polling](./app-shell-state-and-polling.md) for boot, polling and state details.

## Screens (`src/views/`)

| View | What it shows |
| --- | --- |
| `Home` | Date and large clock; Today's events (finished ones drop off) and Upcoming for the rest of the week; weather with forecast; Tasks; now playing when music is on. |
| `Week` / `Month` | Calendar tab with a Week/Month switch (remembered). Week pages through five weeks with tap-to-expand events and a "more ahead" count that ignores holidays; Month is an iPhone-style grid of dots beside the selected day's events, for this month and next. |
| `List` | Groceries (one card, items in columns under aisle headings) and Tasks (a board of section cards). See [Todoist lists](../feeds/todoist-lists.md). |
| `Recipes` / `RecipePage` | Explore and Saved grids and the recipe page. See [recipes](../features/recipes.md). |
| `Music` | Speaker picker, artwork, transport, progress and volume. See [Home Assistant](../integrations/home-assistant-music-and-speech.md). |
| `Ambient` | The idle clock screen and slideshow. See [photos](../feeds/photos-and-slideshow.md). |

All calendar views ask for a day's events through `eventsOn()`, which uses a per-feed day index.

### Layout and scroll behaviour

- **Home** is a 3-column grid (`412px 1fr 1fr`, 20px gap). The first column holds the date, 156px clock, optional now-playing card, and the weather sheet at the foot. The other two columns are scrollable sheets: calendar (Today + Upcoming) and Tasks. Footer actions stay visible while content scrolls inside the sheet.
- **Week** fills the remaining height with a single sheet divided into seven equal day columns (`repeat(7, 1fr)`). Each column has its own scrollable event list, a weekday label and a date disc (the current day is a red disc). Events are source-tinted rounded blocks; past events lose the tint and become secondary text.
- **Month** (`Month.svelte`) is a 2-column layout: a 7×n dot grid on the left and a selected-day event list on the right. The selected day defaults to today in the current month, otherwise the 1st; the grid is rebuilt only when the date changes.
- **List** has a header bar and either a single multi-column flow card (Groceries) or a board of section cards (Tasks). Task boards keep empty section cards so they mirror Todoist, and unsectioned tasks float above in a full-width card that flows into up to three columns.
- **Recipes** uses a 5-column photo grid, with category chips stretched across the top. Explore/Saved panes are hidden with `visibility: hidden` while a recipe page is open so scroll position and decoded images are preserved.
- **Music** is a top area (`calc(100vh - 224px)` square artwork on the left, now-playing details on the right) above a horizontally scrollable speaker row.
- **Ambient** is a full-screen black stage. With photos it shows them filling the screen, the clock aligned to the bottom over a gradient scrim, and a 1.2-second cross-fade between slides. Without photos it shows a large centered clock and a side column.

## Components (`src/components/`)

- `TaskRow` — check ring, text, small grey line (due, section, note) and `Avatar` (initials on a colour derived from the assignee id).
- `EventRow` — calendar-coloured event with time range (optionally its day).
- `NowPlaying` — compact now-playing card for Home and the clock screen.
- `Message` — full-screen agent message (see [agent messages](../features/agent-messages.md)).
- `Settings` — the settings sheet (see [app shell](./app-shell-state-and-polling.md)).
- `Icon` — Lucide glyphs.

## Performance habits in views

- Only the active view is mounted; hidden panes inside Recipes use `visibility: hidden` rather than being rebuilt.
- Long grids use lazy images with async decoding and `content-visibility: auto`.
- Views derive from the minute clock sparingly (the Month grid rebuilds only when the date changes).
- All clocks, temperatures, dates, times and counts use tabular numerals via `.num`.
