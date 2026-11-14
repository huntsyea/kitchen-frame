---
type: data-pipeline
title: Photos and idle slideshow
description: How the iCloud shared album behind the idle clock screen is discovered via anonymous CloudKit calls, cached and resized in the Worker, and preloaded, paired and dimmed on the frame.
tags: [photos, icloud, cloudkit, kv, slideshow, images-binding, frame, ambient]
sources:
  - id: openwiki-source-262fee19998c22821ad4184a
    resource: repo://dashboard/src/App.svelte
  - id: openwiki-source-34e00111e7d20c4cdac2b34c
    resource: repo://dashboard/src/lib/slides.js
  - id: openwiki-source-3a4039a222339b2ae26827c1
    resource: repo://dashboard/src/lib/state.svelte.js
  - id: openwiki-source-0709ad466b2ea97742fcdea4
    resource: repo://dashboard/src/views/Ambient.svelte
  - id: openwiki-source-47e567cb98956edcb53bcbd3
    resource: repo://dashboard/worker/api.test.js
  - id: openwiki-source-93f607093c26733ac1476b93
    resource: repo://dashboard/worker/images.js
  - id: openwiki-source-761c8b9c5f5e1234a74d94a4
    resource: repo://dashboard/worker/index.js
  - id: openwiki-source-272749880eb665924bb98bdd
    resource: repo://dashboard/worker/photos.js
generated: { by: "openwiki/0.7.2", at: "2026-11-14T14:55:31.391Z" }
verified:
  - by: openwiki/0.7.2
    at: 2026-11-14T14:55:31.391Z
---

# Photos and idle slideshow

After a few minutes untouched (or when the play button is tapped), the dashboard switches to a StandBy-style clock screen with the family's iCloud shared album as a slideshow behind it.

```text
frame ── GET /api/photos ──────────► Worker ─ KV "photos" (album list, signed Apple URLs)
      ── GET /api/photos/:id?key= ─► Worker ─ KV "photo:<id>" ─(miss)─► iCloud ─► resize ─► KV
```

## Why everything goes through the Worker

The frame's Android 8.1 trust store lacks DigiCert Global Root G2, so it cannot fetch from Apple's photo servers. The Worker lists the album and passes every image through, and Apple URLs never reach the frame.

The Worker also keeps full-resolution phone photos away from the frame. The [Pastigio FRAME156](../device/kiosk-app-and-frame.md) is a Rockchip RK3326 with 32-bit userspace and 951 MB RAM, and its Wi-Fi is slow; decoding multi-megapixel originals would stall the slideshow and the dashboard. Every image is resized once in the Worker before it is cached.

## Listing the album (`dashboard/worker/photos.js`)

`ALBUM_URL` (a Wrangler secret) is a `photos.icloud.com/shared/album/<token>` link with "Public Website" enabled. `fetchAlbum` reproduces the same anonymous CloudKit calls the public album web page makes:

1. POST to `ckdatabasews.icloud.com/database/1/com.apple.photos.cloud/production/public/records/resolve` with the share token. Apple returns a record containing `anonymousPublicAccess` — a short-lived `publicAccessAuthToken` and the `databasePartition` that hosts the shared zone.
2. POST to the partition's `/shared/records/query` with `recordType: 'CPLAssetAndMasterByAssetDateWithoutHiddenOrDeleted'`, `filterBy: [{ fieldName: 'direction', comparator: 'EQUALS', fieldValue: { value: 'DESCENDING', type: 'STRING' } }]`, the share's `zoneID`, and `resultsLimit: 200`. The endpoint pages through `continuationMarker`s until exhausted.
3. Records come back as interleaved `CPLAsset` and `CPLMaster` rows. `toPhotos` joins each asset to its master via `masterRef`, then picks one JPEG in priority order:
   - the asset's own `resJPEGMed` (the edited/rendered version),
   - the master's `resJPEGMed`,
   - the master's `resOriginal`, but only if it is a JPEG and its larger dimension is at most 2560 px.
   Videos and HEIC-only originals are dropped.
4. Each chosen photo gets an id of `recordName + '-' + fingerprint[0..12]`, so editing a photo changes its fingerprint and therefore its URL, making image URLs immutable. The list is capped at 500 photos.

This is not a documented Apple API and may change without notice. Dates come back from CloudKit as `assetDate` values, not as calendar/VTIMEZONE data.

## Album cache policy

`getAlbum` stores `{ fetched, photos }` under KV key `photos`. The copy is considered fresh for 30 minutes (`MAX_AGE_MS`). When the cached copy is older, a request receives the stale list immediately and a background relist refreshes KV via `ctx.waitUntil`, with only one relist per isolate at a time (`relisting`). When forced or when there is no cached copy and listing fails, the Worker returns the last good list with an `error` attached; if there is no cached copy at all, it throws.

## Serving images

`GET /api/photos/:id` (`photoResponse`):

1. Returns bytes from KV `photo:<id>` if present, marking the response `X-Photo-Source: kv`.
2. Otherwise looks the id up in the current album list and fetches its signed Apple URL. If that fails (expired link or a brand-new photo not yet in the cached list), it force-relists the album once and retries. Still failing → HTTP 404.
3. Resizes once through the Cloudflare Images binding (`env.IMAGES`) via `worker/images.js`'s `shrink`: the binding transforms only originals larger than 250 KB to a JPEG of quality 80, fitting within 1920 px for landscapes or 960 px for portraits (because two portraits are shown side by side). If the binding is missing, the image is already small, or resizing does not reduce the size, the original bytes are kept.
4. Stores the bytes in KV with a 30-day TTL and responds `X-Photo-Source: icloud` plus `Cache-Control: private, max-age=604800, immutable`. Because ids include the fingerprint, a given URL never changes content, so the frame can cache the image in its own HTTP cache for a week.

`<img>` cannot send Authorization headers, so image URLs carry the frame key as `?key=` via `withKey()` in `src/lib/api.js`. `authorized()` in `worker/index.js` accepts the key in the query string only for image routes. See [routing and auth](../worker/routing-auth-and-caching.md).

## On the frame

### Loading the list

`loadPhotos()` in `src/lib/state.svelte.js` runs once at startup, then every 5 minutes only while the clock screen is up and photos would be visible. It is also called when the frame enters idle (`rearmIdle`) and when the play button is tapped (`startSlideshow`). In demo mode it always sets the list to empty, so family photos are never shown. The list is polled only when `photosVisible()` is true.

### Night-photos setting

`ui.theme` is set by `applyTheme()` from the weather feed's sunrise/sunset times, or pinned to light/dark/auto via `?theme=` or Settings. `photosVisible()` returns `ui.theme !== 'dark' || ui.nightPhotos`: by default the slideshow is on during the day, and at night only when Settings → Photos at night is enabled (`ui.nightPhotos`, persisted as `frame-night-photos`). When it is false at night, `Ambient` clears the slide layers, leaving only the clock text on a black background.

### Queue and preloading (`src/lib/slides.js`)

Because the frame's Wi-Fi can take seconds per photo, the next slide is always downloaded and decoded before it is needed:

- `noteAlbum(items)` runs whenever the album list changes. New photos (ids not seen before) move to the front of the queue; photos removed from the album are dropped from the queue.
- `pick()` takes the first photo from the queue. If the queue is empty it shuffles the full album. A landscape (`h <= w`) is shown alone. A portrait is paired with the next portrait in the queue; if none is queued, it scans the full album for another portrait. If no partner exists it shows the single portrait.
- `prepare()` picks the next slide, creates `Image` elements with signed URLs, and waits for `img.decode()`. Only one preload runs at a time; a failed photo is skipped and the next call picks another.
- `takeSlide()` returns the prepared slide and immediately starts preparing the next one. If nothing is ready, it waits for `prepare()` first.

`App.svelte` keeps this pipeline warm: an effect calls `noteAlbum(photos.items)` whenever the list changes, and starts `prepare()` once 15 seconds have passed since boot, the frame is not in demo mode, and photos would be visible. This gives the first dashboard screen priority on the slow Wi-Fi while still making the slideshow appear instantly.

### The clock screen (`src/views/Ambient.svelte`)

When `ui.idle` is set, `App.svelte` unmounts the dashboard views and renders `Ambient`: clock and date in the Settings clock colour, weather, the next event, and now playing. Slides advance every 30 seconds with a 1.2-second cross-fade, keeping at most two layers in the DOM. The slide layer holds one landscape image or two portrait images with a small gap.

`showPhotos` is true only when there are photos, `photosVisible()` is true, and no agent message is covering the screen (`covered`). At night (`ui.theme === 'dark'`) the clock-screen text is dimmed to 70 % opacity and the photo layer to 45 %, so the kitchen is not lit up. Any tap calls `exitIdle()`.

## Tests

`worker/api.test.js` covers anonymous album resolution, preferring edited versions, skipping videos, proxying and KV caching of images, and the rules for small JPEG versus large or HEIC originals. See [Tests](../testing/tests-and-verification.md).
