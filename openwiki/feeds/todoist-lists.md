---
type: data-pipeline
title: Todoist lists (Tasks and Groceries)
description: How the Worker proxies two Todoist projects into Tasks and Groceries lists with sections, assignees and description notes; how the Svelte frame polls, persists, renders and optimistically edits them; and the bulk-add path used by recipes.
tags: [todoist, tasks, groceries, worker, svelte, polling]
sources:
  - id: openwiki-source-262fee19998c22821ad4184a
    resource: repo://dashboard/src/App.svelte
  - id: openwiki-source-c4b38680680ad780caf9b87f
    resource: repo://dashboard/src/components/TaskRow.svelte
  - id: openwiki-source-136e4998beec00d02c60296f
    resource: repo://dashboard/src/lib/api.js
  - id: openwiki-source-3a4039a222339b2ae26827c1
    resource: repo://dashboard/src/lib/state.svelte.js
  - id: openwiki-source-8bce032e91b723abad8258ba
    resource: repo://dashboard/src/views/List.svelte
  - id: openwiki-source-47e567cb98956edcb53bcbd3
    resource: repo://dashboard/worker/api.test.js
  - id: openwiki-source-761c8b9c5f5e1234a74d94a4
    resource: repo://dashboard/worker/index.js
  - id: openwiki-source-fd5601bf85cef5c591f92e95
    resource: repo://dashboard/worker/todoist.js
verified:
  - by: openwiki/0.7.2
    at: 2026-11-14T14:55:31.391Z
generated: { by: "openwiki/0.7.2", at: "2026-11-14T14:55:31.391Z" }
---

# Todoist lists (Tasks and Groceries)

Two dashboard tabs come from Todoist: **Tasks** and **Groceries**. The Todoist token never reaches the frame; the Worker proxies them through `/api/lists/:list`. The Home tab also renders the same Tasks widget using the same shared state and completion handler, so a task completed on Home is immediately reflected in the Tasks tab.

## Configuration

The Worker reads a secret and two variables to know which Todoist projects to use:

| Name | Kind | Purpose |
| --- | --- | --- |
| `TODOIST_TOKEN` | secret | Todoist API token. Without it, list routes return `503` with `"Add TODOIST_TOKEN to connect Todoist"`. The frame detects this message and shows "Todoist isn’t connected yet." |
| `TODOIST_TODO_PROJECT` | var | Project name for the `todo` list (default `"To-do"`). In `wrangler.jsonc` this household uses `"Household"`. |
| `TODOIST_GROCERY_PROJECT` | var | Project name for the `groceries` list (default `"Groceries"`). In `wrangler.jsonc` this household uses `"Grocery List"`. |

These vars are defined in `dashboard/wrangler.jsonc`:

```jsonc
"vars": { "TODOIST_GROCERY_PROJECT": "Grocery List", "TODOIST_TODO_PROJECT": "Household" }
```

## Worker (`dashboard/worker/todoist.js`)

- **Project lookup:** `projectId()` matches the configured project name case-insensitively against Todoist `/projects` (paged, 200 per page, up to 1,000). The name→id map is cached per isolate, and concurrent callers share one in-flight `/projects` request (`listing`), so a 40-item bulk add on a cold isolate only lists projects once.
- **`getList`** fetches the project's tasks on every request, in parallel with the project's metadata, and returns `{project, items, sections, people, updated}`.
- **Metadata cache:** sections (sorted by `section_order`) and collaborators (id → name; only shared projects have any) change rarely, so `projectMeta` caches them per isolate for 10 minutes.
- **`sortTasks`** drops subtasks and completed tasks. Groceries keep Todoist's own `child_order`; Tasks put dated items first (earliest date, so overdue, at the top), then fall back to `child_order`. Each item is `{id, content, due?, section?, assignee?, note?}`, where `note` is the first non-empty line of the task description, trimmed and cut to 120 characters (for example "For: Beef Mandi" from a recipe).
- **Writes:** `addItem` creates a task in the project with an optional description; `completeItem` closes a task by id.

Routes in `dashboard/worker/index.js`:

| Route | Body | Result |
| --- | --- | --- |
| `GET /api/lists/todo` or `/groceries` | | the list |
| `POST /api/lists/:list` | `{content, description?}` | the new item |
| `POST /api/lists/:list` | `{items:[{content, description?}, …]}` | `{items:[…]}`, added in parallel, at most 40 |
| `POST /api/lists/:list/:id/done` | | `{ok:true}` |

Content and descriptions are trimmed to 500 characters. The bulk-add route exists for [recipes](../features/recipes.md) ("Add N to Groceries").

## Frame

### Offline-first state and polling (`dashboard/src/lib/state.svelte.js`)

`lists.todo` and `lists.groceries` hold `items`, `sections`, `people`, `project` and `error`. They are seeded from `localStorage` at boot (`cached('todo')`, `cached('groceries')`, plus metadata caches) so the saved list remains visible even when the frame is offline. `loadList(name)` goes through the shared `single()` in-flight guard and only replaces `items` or metadata when `changed()` reports a difference, so unchanged polls skip both the state update and the `localStorage` write.

Polling follows what's on screen:

- **Tasks** are polled every minute while the dashboard is showing and not idle (`!ui.idle`), because Home and the Tasks tab both display them.
- **Groceries** are polled every minute only while its own tab is open and the dashboard is not idle.
- A list is loaded immediately when its tab opens (`App.svelte` effect on `ui.tab`).
- Waking from the clock screen (`exitIdle()`) reloads Tasks, since the Home tab shows them.

See [app shell](../frontend/app-shell-state-and-polling.md) for the `every()`, `single()`, `changed()` and `remember()` primitives.

### Optimistic edits

Edits are optimistic so the UI feels instant:

- `completeItem` removes the row at once and restores it with an error message if Todoist refuses.
- `addItem` appends the returned item to the list and persists it.
- `addToGroceries` (used by [recipes](../features/recipes.md)) sends missing ingredients in one bulk `POST`, each with a description naming the recipe, and appends the returned items to `lists.groceries` immediately with their notes.

In demo mode lists come from `dashboard/src/lib/demo.js` and edits never reach Todoist; `setSetting('demo', …)` rebuilds the demo lists and calls `forget()` so real data redraws.

### Rendering (`dashboard/src/views/List.svelte`, `dashboard/src/components/TaskRow.svelte`)

- **Tasks without a section** (or with an unknown section) come first, unlabelled, like Todoist's list view. In Tasks they appear in a full-width card above the board; in Groceries they form the first group before any section headings.
- **Tasks** (`board=true`) shows one card per section in Todoist order, **including empty sections**, so it mirrors Todoist.
- **Groceries** shows one card with items flowing in columns under section headings (aisles), **skipping empty sections**. Sections are bucketed in one pass.
- `List.svelte` resolves each item's assignee name with `who(item) = list.people[item.assignee]` and passes it to `TaskRow`.
- `TaskRow` shows a ring that fills before the row disappears (350 ms, so a tap feels confirmed), the assignee's avatar when a name is provided, and a small grey line with the due label ("Overdue" in red), the section name and the note.
- The Add button opens an inline field that stays open for several additions in a row.

The Home tab reuses the same `TaskRow` and `completeItem('todo', i)` handler for its Tasks widget, so completing a task there also updates the shared list.

## Tests

`dashboard/worker/api.test.js` (with a fake Todoist API) covers project lookup across pages, Todoist order for groceries, hiding subtasks, dated-first ordering for to-dos, add and complete, unknown list and missing token, the bulk add with descriptions, and the description `note`. See [tests](../testing/tests-and-verification.md).
