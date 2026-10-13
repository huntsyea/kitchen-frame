---
type: integration
title: "Home Assistant: music and speech"
description: How the photo frame connects directly to Home Assistant on the LAN over its WebSocket API to list Music Assistant speakers, show now playing, control music, and read agent messages aloud with text-to-speech.
tags: [home-assistant, music-assistant, websocket, tts, music, lan]
verified:
  - by: openwiki/0.7.2
    at: 2026-10-13T17:09:19.129Z
sources:
  - id: openwiki-source-81e5843e3f05d867bcedaa39
    resource: repo://dashboard/src/components/NowPlaying.svelte
  - id: openwiki-source-81909880e1b8359442697bb1
    resource: repo://dashboard/src/lib/ha.svelte.js
  - id: openwiki-source-3d6f161fa50a397e804302b6
    resource: repo://dashboard/src/views/Music.svelte
  - id: openwiki-source-28fc9369ef5fcb7aea5d2dcd
    resource: repo://docs/frame.md
generated: { by: "openwiki/0.7.2", at: "2026-10-13T17:09:19.129Z" }
---

# Home Assistant: music and speech

The Music tab, the Home/Ambient now-playing indicator, and spoken agent messages all talk straight to Home Assistant on the home network. Unlike the rest of the dashboard, this path does not use the Cloudflare Worker; the frame opens a WebSocket to HA itself.

## Why direct, and where the credentials live

Home Assistant's REST API rejects cross-origin requests from the dashboard's https origin, but its WebSocket API accepts them, so `dashboard/src/lib/ha.svelte.js` uses only the WebSocket. The https page reaching a plain `ws://` LAN address works because the kiosk allows mixed content (see [Frameo frame notes](../../docs/frame.md)).

The HA URL and long-lived token are stored only in the frame's browser localStorage as `frame-ha-url` and `frame-ha-token`. They are pushed onto the frame over ADB or Chrome remote debugging from `dashboard/.frame.vars`, which is gitignored; they never appear in the deployed site, the repository, or Cloudflare. `haConfigured()` is false if either value is missing; `App.svelte` then omits the Music tab and nothing else breaks.

`docs/frame.md` notes that the current token belongs to an admin HA user and recommends replacing it with a non-admin "Kitchen Frame" user, because the rooted frame lets any app on it read localStorage.

## WebSocket connection (`ha.svelte.js`)

`connectHA()` opens `<ha-url>/api/websocket`. On `auth_required` it sends the stored token; on `auth_ok` it resets the retry timer, clears errors, and calls `subscribe()`. If HA answers `auth_invalid`, `ha.status` becomes `error` with the message "Home Assistant rejected the frame’s token" and the socket is closed without reconnecting, so a bad token does not hammer HA. On any other close, `connectHA()` schedules an exponential backoff retry from 1 s up to 30 s and reconnects.

`send(msg)` assigns an incrementing id, stashes a pending promise, and writes the message to the open socket; when a matching `result` arrives the promise resolves or rejects. A disconnect rejects every pending request. `callService(domain, service, data, target)` is the single helper for HA actions.

`subscribe()` does one `get_states` call, collects all `tts.*` entities into `ha.tts`, gathers the ids of every `media_player.*`, clears the local entity cache, and asks HA to `subscribe_entities` for only those media-player ids. From then on HA pushes compact diffs: `applyDiff()` treats `a` as added/full, `c` as changed (with `+` for new values and `-` listing removed attribute keys), and `r` as removed. Each update ends in `publish()`.

`publish()` builds `ha.players`: unavailable players are dropped; when at least one Music Assistant player exists, only MA speakers are kept so TVs and duplicate entities don't clutter the list. A Music Assistant player is detected by attributes starting with `mass_` or `app_id: music_assistant`. Duplicate `friendly_name` values get a room suffix derived from the entity id (`hunter_s_bedroom` → "Hunter's Bedroom"); the list is sorted so playing speakers come first, then alphabetically by label.

## Music tab (`views/Music.svelte`)

The tab resolves a `player` in this order: the previously chosen speaker stored in `frame-music-player`, otherwise the speaker that is currently playing, otherwise the first available speaker. The chosen speaker can be switched from the horizontal speaker row.

The now-playing card shows artwork (`entity_picture`, made absolute with `haUrl()` against the HA base URL), title, artist, and album. A progress bar is extrapolated from `media_position` and `media_position_updated_at`; a one-second timer advances the bar only while the selected player is `playing` and has a known position.

Transport controls are previous, play/pause, and next through the standard `media_player` services. Volume follows HA's `volume_level` unless the slider is being dragged, and while dragging `volume_set` is sent at most once every 250 ms using a small timer that also catches the final value.

When music is playing on another Music Assistant speaker, a "Play here" button appears and calls Music Assistant's `transfer_queue` service with the other speaker as `source_player`, moving the queue to the selected speaker.

## Now playing card and hold logic (`nowPlaying()`)

`nowPlaying()` returns the speaker currently playing something with a title. With `hold: true` (used on the Home screen), it keeps returning the last speaker that played after a pause — even across page reloads, because the held entity id and last-played timestamp are saved in `frame-np-held` and `frame-np-at`. The hold ends when another speaker starts playing, the held track disappears, or 30 minutes have passed since it last played. Some speakers report `idle` rather than `paused` soon after pausing, so the hold deliberately accepts both states.

The clock/Ambient screen uses `nowPlaying()` without `hold`; its music line disappears as soon as nothing is playing. `components/NowPlaying.svelte` renders the held or live card: clicking the card switches to the Music tab; the play/pause button on the right toggles the speaker without leaving Home.

## Speech (`announce()` and read-aloud)

`announce(text, entity_id)` in `ha.svelte.js` calls HA's `tts.speak` service with `cache: false`. It prefers the local Piper engine (`tts.piper`) if present; otherwise it uses the first TTS entity it found. Music Assistant speakers pause music for the announcement and resume afterwards.

The read-aloud wiring is in `dashboard/src/lib/state.svelte.js`. `announceNew()` speaks each new agent message once, building the text "Message from <from>. <title>. <body>" and truncating to 400 characters. It is skipped in demo mode, when HA is not connected, during quiet hours (22:00–07:00 frame time), when the message has `speak: false`, or when the message is older than 10 minutes so a late reconnect does not read stale news. Each message id is marked announced before the call and released only if `announce()` fails; the last 100 announced ids are persisted in `frame-announced` so a message is never read twice.

`announceTarget()` picks the speaker: if Settings → Read messages aloud is off, it returns null. Otherwise it returns the speaker chosen in Settings (default `media_player.kitchen_mini`) if HA still has it, or the first available Music Assistant speaker as a fallback. The rules that decide when a message is shown versus spoken are documented on [Agent messages](../features/agent-messages.md).
