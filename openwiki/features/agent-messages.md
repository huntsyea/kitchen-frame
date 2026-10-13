---
type: feature
title: Agent messages (live push)
description: How AI agents post full-screen messages to the frame and how they arrive in about 0.1 s through a hibernating Cloudflare Durable Object (MessageRoom) and a WebSocket, including dismissal, expiry, fallback polling and read-aloud through Home Assistant.
tags: [messages, durable-objects, websocket, hibernation, agents, tts]
verified:
  - by: openwiki/0.7.2
    at: 2026-10-13T17:09:19.129Z
sources:
  - id: openwiki-source-262fee19998c22821ad4184a
    resource: repo://dashboard/src/App.svelte
  - id: openwiki-source-1329da1fdff8c71f63c46974
    resource: repo://dashboard/src/components/Message.svelte
  - id: openwiki-source-ca659ddfa04bafbd6bb2161a
    resource: repo://dashboard/src/components/Settings.svelte
  - id: openwiki-source-3a4039a222339b2ae26827c1
    resource: repo://dashboard/src/lib/state.svelte.js
  - id: openwiki-source-0709ad466b2ea97742fcdea4
    resource: repo://dashboard/src/views/Ambient.svelte
  - id: openwiki-source-47e567cb98956edcb53bcbd3
    resource: repo://dashboard/worker/api.test.js
  - id: openwiki-source-761c8b9c5f5e1234a74d94a4
    resource: repo://dashboard/worker/index.js
  - id: openwiki-source-8db6682af62a097684283c37
    resource: repo://dashboard/worker/messages.js
  - id: openwiki-source-0d4db84e2b7fee7556be759e
    resource: repo://dashboard/wrangler.jsonc
generated: { by: "claude-code", at: "2026-10-13T14:37:10.456Z" }
---

# Agent messages (live push)

Any AI agent or script holding `AGENT_TOKEN` can put a message on the kitchen frame. It covers the
whole screen (dashboard or slideshow) until someone taps its X, and is normally read aloud on the
Kitchen Mini. Delivery is push-based: a message reaches the screen about 0.1 s after the POST.

```text
agent ──POST /api/messages (AGENT_TOKEN)──► Worker ──► MessageRoom (Durable Object "frame")
                                                          │ store list, push to every socket
frame ◄──────── WebSocket /api/messages/live?key= ◄──────┘
frame ──POST /api/messages/:id/dismiss (frame key)──► Worker ──► MessageRoom (push again)
```

## Server: the MessageRoom Durable Object

`dashboard/worker/messages.js` defines `MessageRoom`, bound as `MESSAGES` with a SQLite-backed
migration in `wrangler.jsonc` (see [build and configuration](../operations/build-deploy-and-configuration.md)).
There is exactly one instance, named `frame`, obtained through `room(env)`; because every request
goes through that instance, the list is strongly consistent (KV, used before, cached reads for
30–60 s, which made fast polling pointless).

The Worker (`worker/index.js`) only authenticates and forwards; the room speaks a tiny internal
HTTP protocol:

| Public route | Auth | Room path |
| --- | --- | --- |
| `POST /api/messages` | `Authorization: Bearer <AGENT_TOKEN>` | `/post` |
| `GET /api/messages` | frame key | `/list` |
| `GET /api/messages/live` | frame key in `?key=` (WebSockets can't send headers) | `/live` (upgrade) |
| `POST /api/messages/:id/dismiss` | frame key | `/dismiss/:id` |

The agent token opens only the POST route (and recipe saving); it cannot read anything. See
[routing and auth](../worker/routing-auth-and-caching.md).

### Posting and limits

`post()` validates the JSON body: `title` ≤120 chars and/or `body` ≤2,000 (line breaks normalised
and kept), optional `from` ≤60, `ttl_minutes` (capped at 7 days), and `speak: false` to stay
silent. At most 20 undismissed messages may wait (`429` beyond that). Responses: `201 {id}`,
`400` for empty/invalid input, `401` for a wrong token.

### Storage, push and expiry

`save(list)` is the single write path: it stores the list in Durable Object storage, sends the
whole list as `{"messages":[…]}` to every hibernated socket from `ctx.getWebSockets()`, and sets
an alarm for the earliest `expires` (or deletes the alarm when none expire). `alarm()` simply
re-saves the list without expired entries, which also pushes the removal. `load()` filters
expired messages on every read, so an expired message never shows even if an alarm is late.

### Hibernation

The room is designed to stay asleep:

- Sockets are accepted with `ctx.acceptWebSocket(server)` (hibernatable), not `server.accept()`.
- The constructor registers `setWebSocketAutoResponse('ping' → 'pong')`, so the frame's keep-alive
  is answered by the runtime without waking the object or billing duration.
- There are no in-memory timers; time-based work uses storage alarms. `webSocketMessage`,
  `webSocketClose` and `webSocketError` are no-ops (the compatibility date auto-replies to close
  frames).

It wakes only to accept a connection, store a post or dismissal, or run an expiry alarm.

## Frame: socket client, fallback and display

In `dashboard/src/lib/state.svelte.js`:

- `connectMessages()` opens `wss://…/api/messages/live?key=…`. On open it resets the backoff and
  sends `ping` every 30 s; if no frame (including `pong`) arrived since the last ping, it closes
  the socket as dead. Any non-`pong` frame is a full list passed to `showMessages()`.
- On close it reconnects with exponential backoff (1 s doubling to 60 s) and, if the socket had
  been up, does one HTTP `loadMessages()` to catch anything sent while it was closing.
- `start()` also schedules `loadMessages()` every minute, but only while the socket is down, so a
  connected frame makes no message requests at all (see the scheduler in
  [app shell](../frontend/app-shell-state-and-polling.md)).
- `showMessages()` drops ids dismissed locally (so a message doesn't flash back if a list arrives
  just before the server processes the dismissal) and only replaces state when the list changed.

`components/Message.svelte` renders the oldest message as a full-screen `alertdialog` with sender,
time, "1 of N", title and body; its X calls `dismissMessage()`, which hides it locally at once and
POSTs the dismissal (the room then pushes the shorter list to every screen). `App.svelte` holds
messages back entirely in demo mode, and `Ambient.svelte` pauses the slideshow while a message
covers it.

## Read-aloud

`announceNew()` speaks each new message once through Home Assistant (`announce()` →
`tts.speak`, Piper preferred; see [Home Assistant](../integrations/home-assistant-music-and-speech.md)):
"Message from <from>. <title>. <body>", truncated to 400 characters. It is skipped in demo mode,
when Settings → Read messages aloud is off, when Home Assistant isn't connected, during quiet
hours (22:00–07:00 frame time), for `speak: false`, and for messages older than 10 minutes (so a
reconnect doesn't read old news). Announced ids are claimed before speaking, released if the call
fails, and persisted in localStorage (`frame-announced`, last 100). On the very first run, messages
already present are treated as announced.

The speaker comes from `announceTarget()`: the one chosen in Settings (initially
`media_player.kitchen_mini`, this household's speaker) if Home Assistant has it, otherwise the
first Music Assistant speaker, so read-aloud works on any setup without configuration.

## Agent skill

`~/.agents/skills/kitchen-frame-message` (outside this repo) asks the user for title, message,
sender, read-aloud and expiry, previews, then POSTs with `$KITCHEN_FRAME_URL` and
`$KITCHEN_FRAME_TOKEN`. `docs/messages.md` is the in-repo contract for agents.

## Tests

`worker/api.test.js` runs the real `MessageRoom` behind a fake namespace and state (`fakeRoom()`):
token boundaries, validation and limits, dismissal, the 20-message cap, and a test that posting
and dismissing push to a connected socket, that a ttl sets an alarm, and that `/live` rejects a
wrong key (401) and non-upgrade requests (426). See [tests](../testing/tests-and-verification.md).
