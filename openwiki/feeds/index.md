# Files

- [Calendar feed](calendar.md) - How multiple iCal feeds are fetched, prefiltered, expanded with ical.js, merged and stored in KV by the Worker cron, how failures are isolated per feed, and how the frame indexes the result by day for its Home, Week, Month and clock screens.
- [Photos and idle slideshow](photos-and-slideshow.md) - How photos from an iCloud shared album reach the frame's idle clock screen - anonymous CloudKit listing, a KV-cached album list and image cache proxied through the Worker, one-time resizing, and the frame's preloaded, paired slideshow.
- [Todoist lists (Tasks and Groceries)](todoist-lists.md) - How the Worker proxies two Todoist projects (named by TODOIST_TODO_PROJECT / TODOIST_GROCERY_PROJECT) into Tasks and Groceries lists, with sections, assignees and description notes; how the frame polls, renders and optimistically edits them; and the bulk-add path used by recipes.
- [Weather and day/night theme](weather-and-theme.md) - The Open-Meteo weather proxy and its compact response, and how the frame uses sunrise and sunset (or a pinned preference) to switch between the light and dark palettes and dim the clock screen at night.
