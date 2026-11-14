# Files

- [Calendar feed](calendar.md) - How the Worker merges multiple iCal feeds into a single agenda, including the prefilter, recurrence expansion, timezone handling, fast-forward optimization, and the cron/KV refresh strategy.
- [Photos and idle slideshow](photos-and-slideshow.md) - How the iCloud shared album behind the idle clock screen is discovered via anonymous CloudKit calls, cached and resized in the Worker, and preloaded, paired and dimmed on the frame.
- [Todoist lists (Tasks and Groceries)](todoist-lists.md) - How the Worker proxies two Todoist projects into Tasks and Groceries lists with sections, assignees and description notes; how the Svelte frame polls, persists, renders and optimistically edits them; and the bulk-add path used by recipes.
- [Weather and day/night theme](weather-and-theme.md) - The Open-Meteo weather proxy and its compact response, how WMO weather codes become icons and labels, and how sunrise/sunset (or a pinned preference) switches the light/dark palette and dims the idle clock screen.
