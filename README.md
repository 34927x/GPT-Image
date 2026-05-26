# Bulk-GPT

Premium bulk image generator powered by ChatGPT. Customers paste prompts on the website and get back generated images. The actual generation happens in your own Chrome browser via the Bulk-GPT extension running in **Worker Mode**, with automatic account rotation.

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Customer (anywhere)                            │
│  bulk-gpt.vercel.app — login with key           │
│  Paste prompts → "Generate" → see images live   │
└────────────────────┬────────────────────────────┘
                     │ MongoDB queue
                     ▼
┌─────────────────────────────────────────────────┐
│  Your Chrome (always-on workstation)            │
│  Bulk-GPT Extension v4 (Worker Mode)            │
│  • Polls queue every few seconds                │
│  • Rotates through your ChatGPT accounts        │
│  • Pushes results back to MongoDB               │
└─────────────────────────────────────────────────┘
```

## Repository layout

```
Bulk-GPT/
├── web/          Next.js 14 app (deploys to Vercel)
├── extension/    Manifest V3 extension (Chrome + Firefox)
├── _legacy/      Backup of v3 (Python bot + old extension)
└── DEPLOY.md     Step-by-step deployment guide
```

## Quick start

See [`DEPLOY.md`](./DEPLOY.md) for the full setup. Short version:

1. Set up MongoDB Atlas (free tier).
2. Deploy `web/` to Vercel with the right env vars.
3. Load `extension/` into your Chrome (admin only).
4. Open the extension sidebar, paste your worker token, capture your ChatGPT accounts, click "Start Worker Mode".
5. Generate access keys in the admin panel and sell them.

## Features

- **Key-based access** — generate keys with plans (image quotas, expiry), revoke any time.
- **Admin panel** — manage keys, plans, view stats, monitor live worker.
- **Bulk image generation** — paste a list of prompts, get them back as a gallery.
- **Account rotation** — multiple ChatGPT accounts cycled automatically; rate-limit aware.
- **Live progress** — customer sees each prompt's status update in real time.
- **Image gallery** — every generated image saved per user; download single or as ZIP.
- **Worker Mode** — extension in your browser does the heavy lifting; no VPS, no Playwright, no Cloudflare drama.

## License

Private. © TurabCoder.
