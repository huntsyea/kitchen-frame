---
type: data-pipeline
title: Weather and day/night theme
description: The Open-Meteo weather proxy and its compact response, and how the frame uses sunrise and sunset (or a pinned preference) to switch between the light and dark palettes and dim the clock screen at night.
tags: [weather, open-meteo, theme, dark-mode, sunrise, sunset]
verified:
  - by: openwiki/0.7.2
    at: 2026-10-13T17:09:19.129Z
sources:
  - id: openwiki-source-136e4998beec00d02c60296f
    resource: repo://dashboard/src/lib/api.js
  - id: openwiki-source-e12fdae11ea7713285efd699
    resource: repo://dashboard/src/lib/format.js
  - id: openwiki-source-3a4039a222339b2ae26827c1
    resource: repo://dashboard/src/lib/state.svelte.js
  - id: openwiki-source-708fd2723f1c868a90846112
    resource: repo://dashboard/src/style.css
  - id: openwiki-source-0709ad466b2ea97742fcdea4
    resource: repo://dashboard/src/views/Ambient.svelte
  - id: openwiki-source-47e567cb98956edcb53bcbd3
    resource: repo://dashboard/worker/api.test.js
  - id: openwiki-source-cb5a2109e8a56015671f5cae
    resource: repo://dashboard/worker/weather.js
generated: { by: "openwiki/0.7.2", at: "2026-10-13T17:09:19.129Z" }
---

# Weather and day/night theme

Weather appears in the top bar, on Home and on the idle clock screen. Its sunrise and sunset times also drive the dashboard's light/dark theme.

## Worker (`dashboard/worker/weather.js`)

`GET /api/weather` calls [Open-Meteo](https://open-meteo.com) (free, no key) for the configured location: `WEATHER_LAT`, `WEATHER_LON` (secrets in this deployment; rounded coordinates) and optional `WEATHER_UNIT` (`fahrenheit` by default, or `celsius`). Without coordinates it returns `{error: 'Set WEATHER_LAT and WEATHER_LON'}`.

The upstream request asks for:

- current: `temperature_2m`, `apparent_temperature`, `weather_code`, `is_day`;
- daily: `temperature_2m_max`, `temperature_2m_min`, `precipitation_probability_max`, `weather_code`, `sunrise`, `sunset`;
- five forecast days with `timezone: auto` and the chosen temperature unit.

It is edge-cached for 10 minutes (`cf: { cacheTtl: 600, cacheEverything: true }`) so every frame poll does not hit Open-Meteo.

`shape()` reduces the response to what the screen shows:

```json
{ "unit": "F", "temp": 66, "feels": 65, "code": 0, "day": false,
  "days": [{ "date": "2026-10-12", "hi": 88, "lo": 55, "rain": 0, "code": 1,
             "sunrise": "2026-10-12T07:03", "sunset": "2026-10-12T18:24" }, …],
  "updated": "…" }
```

Dates and sunrise/sunset are local wall-clock strings (`YYYY-MM-DDTHH:MM`). The daily precipitation probability defaults to `0` when Open-Meteo does not provide it.

## Rendering weather

`weatherInfo(code, day)` in `src/lib/format.js` maps WMO weather codes to a label, a Lucide icon name and a tint (`sun` yellow or `rain` blue), with night variants for clear and partly cloudy. The top bar (`App.svelte`), Home and the Ambient clock screen all call it with the current `day` flag from `weather.data`; the four-day forecast strip on Home omits the `day` argument and therefore defaults to daytime icons.

Home shows the current temperature and condition, today's high/low, and the next four days with rain probability and highs/lows. Ambient and the top bar show only the current temperature and icon.

## Polling and caching (`src/lib/state.svelte.js`)

`loadWeather()` runs every 15 minutes, deduplicates concurrent requests through `single('weather', …)`, and only updates `weather.data` (and re-applies the theme) when `changed('weather', w)` reports a difference. `changed()` also writes the last good response to localStorage as `frame-weather`, so the frame boots with data even when offline. See [app shell](../frontend/app-shell-state-and-polling.md).

## Theme switching

`ui.themePref` is `auto`, `light` or `dark` (Settings → Appearance, stored as `frame-theme`). A `?theme=light|dark|auto` URL parameter also sets and persists it, which is useful for setup over ADB.

`applyTheme()`:

- with `light` or `dark`, uses that;
- with `auto`, is dark before today's sunrise or from sunset on, using the forecast day whose `date` matches the local date, falling back to 7:00 and 19:00 until weather has loaded.

It writes `ui.theme` and sets the `data-theme` attribute on the root element. The minute-aligned clock tick calls it every minute; it also runs when the weather response changes and when the preference changes.

`src/style.css` defines the two palettes under `:root, [data-theme="light"]` and `[data-theme="dark"]`, using iOS system colours. Switching theme is therefore a single attribute repaint with no component re-render (see [design system](../frontend/views-components-and-design-system.md)).

## Night on the clock screen

`Ambient.svelte` treats `ui.theme === 'dark'` as night: the clock text drops to 70% opacity and the photo slideshow to 45%, so the kitchen is not lit up after sunset. Photos are only shown at night when Settings → Photos at night is set to Dimmed (`ui.nightPhotos`), as decided by `photosVisible()`. See [photos and slideshow](./photos-and-slideshow.md).

## Tests

`worker/api.test.js` checks that `shape()` reduces an Open-Meteo response to the fields the screen uses. See [tests](../testing/tests-and-verification.md).
