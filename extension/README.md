# Bulk-GPT Worker Extension (v4)

The browser-side engine for [Bulk-GPT](../README.md). Runs in **your** Chrome / Firefox, polls jobs from your Vercel-hosted site, runs them on chatgpt.com using your captured ChatGPT sessions, and ships results back.

## Architecture

```
Worker mode loop:
  1. POST /api/worker/claim → { job }
  2. switch to next available account (rotates cookies)
  3. content script types prompt into chatgpt.com, waits for image
  4. POST /api/worker/complete with image data URL
  5. sleep, repeat
```

## Build

```bash
npm install
npm run build           # Chrome
npm run build:firefox   # Firefox
npm run package         # zip dist/ for distribution
```

Output: `dist/`. Load it via `chrome://extensions` → "Load unpacked".

## Folder layout

```
src/
├── background/    Worker loop, account manager, runner, state
├── content/       chatgpt.com automation
├── popup/         Compact popup (action click)
├── sidebar/       Main worker dashboard
├── shared/        api shim, storage, server client, types
└── ui/            Common Preact components & hooks
```

## Settings storage

Lives in `chrome.storage.local`:

| Key | Purpose |
|---|---|
| `bgt_worker_settings` | Server URL, token, poll interval |
| `bgt_accounts` | Captured ChatGPT cookies, per-account state |
| `bgt_active_idx` | Which account's cookies are currently live |
| `bgt_worker_id` | Stable per-install ID (sent in every request) |
| `bgt_stats` | Daily/total counters |

## Multi-browser support

This is a single codebase. Build target picks the right manifest:

- `manifests/chrome.json` → MV3 with `service_worker`
- `manifests/firefox.json` → MV3 with `scripts` (Firefox doesn't support `service_worker` yet)

The runtime uses `globalThis.browser` (Firefox) when available, else `globalThis.chrome`.

## Security

- Worker token never leaves the extension. The site validates it server-side on every API hit.
- Cookies stay in `storage.local`. They never leave your machine except as live cookies via `chrome.cookies.set()`.
- Captured images are uploaded as base64 data URLs to your site, then optionally re-hosted on Cloudinary.
