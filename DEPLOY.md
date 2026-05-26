# Bulk-GPT Deployment Guide

This guide walks you through getting Bulk-GPT live: site on Vercel, MongoDB on Atlas, extension running in your Chrome.

---

## 1. MongoDB Atlas (free tier)

1. Sign up at [mongodb.com/cloud/atlas](https://www.mongodb.com/cloud/atlas).
2. Create a free **M0** cluster (any region close to your Vercel region).
3. Database Access → Add user → save the password.
4. Network Access → Add IP → choose **Allow access from anywhere** (`0.0.0.0/0`) for Vercel. You can lock it down later if you set up Vercel static egress IPs.
5. Connect → Drivers → copy the `mongodb+srv://...` URI. Replace `<password>` and add `/bulk_gpt` before the query string.

---

## 2. Generate secrets

Run these commands once and save the output:

```bash
# SESSION_SECRET (32+ chars)
node -e "console.log(require('crypto').randomBytes(48).toString('hex'))"

# WORKER_TOKEN
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"

# ADMIN_MASTER_KEY (any unguessable string)
echo "BGT-ADMIN-$(node -e "console.log(require('crypto').randomBytes(8).toString('hex').toUpperCase())")"
```

---

## 3. Deploy to Vercel

1. Push this repo to GitHub (private).
2. Vercel → New Project → import the repo.
3. **Important**: set **Root Directory** to `web/`.
4. Framework preset: Next.js (auto-detected).
5. Add environment variables (Project Settings → Environment Variables):

   | Name | Value |
   |---|---|
   | `MONGODB_URI` | from step 1 |
   | `MONGODB_DB` | `bulk_gpt` |
   | `SESSION_SECRET` | from step 2 |
   | `WORKER_TOKEN` | from step 2 |
   | `ADMIN_MASTER_KEY` | from step 2 |
   | `NEXT_PUBLIC_SITE_URL` | `https://your-app.vercel.app` |

6. Optional, for image hosting (recommended once usage scales):
   - `CLOUDINARY_CLOUD_NAME`
   - `CLOUDINARY_API_KEY`
   - `CLOUDINARY_API_SECRET`

7. Deploy.

After first deploy:
- Open `https://your-app.vercel.app/login`
- Paste your `ADMIN_MASTER_KEY` to enter the admin panel.
- Go to **Plans** → create at least one plan (e.g., "Starter: 50 daily, 30 days").
- Go to **Access keys** → generate keys to sell.

---

## 4. Set up the worker (your Chrome browser)

This is what actually generates images. It runs on **your machine**, not Vercel.

### Build the extension

```bash
cd extension
npm install
npm run build           # Chrome (default)
# or:
npm run build:firefox
```

Output goes to `extension/dist/`.

### Load it in Chrome

1. `chrome://extensions/`
2. Enable **Developer mode** (top right).
3. **Load unpacked** → pick `extension/dist`.
4. Pin the extension. Click it to open the popup, then **Open dashboard** (sidebar).

### Configure the worker

In the sidebar:

1. **Settings** tab:
   - Server URL: `https://your-app.vercel.app`
   - Worker token: same `WORKER_TOKEN` from Vercel env.
   - (Optional) Worker label: `My Laptop`.
   - Click **Save** then **Test** to verify connection.

2. **Accounts** tab:
   - Open `chatgpt.com` in another tab and log in.
   - Come back to the sidebar → **Capture current session**.
   - Repeat for every ChatGPT account you want to rotate. The more accounts, the higher your bulk capacity.

3. **Overview** tab → click **Start**. The worker will start polling. You should see "Online" badge.

### Verify

- On the website, log in with a customer key (or `ADMIN_MASTER_KEY`).
- Go to `/dashboard/generate`, paste a prompt, hit Generate.
- Within seconds, the extension picks it up. Watch `/admin/workers` on the website to see live status.
- Image appears in the customer's gallery when done.

---

## 5. Selling keys

1. `/admin/plans` — create plans tailored to what you sell (Starter, Pro, Lifetime, etc.).
2. `/admin/keys` — generate a key for a customer. Copy it. Sell it.
3. Customer goes to `your-app.vercel.app/login`, pastes the key, generates images.

To revoke a key, hit the ban icon in `/admin/keys`. Effective immediately.

---

## 6. Operational tips

- Keep your worker Chrome window **logged in and unlocked**. The browser must be running to process jobs.
- If you hit Cloudflare on chatgpt.com, just open the tab manually and solve it once. The worker reuses the tab.
- Add 3-5 ChatGPT accounts minimum for smooth rotation.
- Check `/admin/workers` for liveness. If a worker is offline, restart Chrome / re-enable Worker Mode.
- For higher throughput, install the extension on a second machine. The MongoDB queue handles multiple workers automatically.

---

## 7. Customising

- Branding: edit `web/src/app/page.tsx` (landing) and `web/src/components/brand/logo.tsx`.
- Colors: edit `web/src/app/globals.css` (look for `--primary`, `--accent` tokens).
- Image storage: enable Cloudinary in env to offload images off MongoDB. Without it, images store as data URLs (fine for testing, costly for scale).

---

## Troubleshooting

**Worker says "Server replied 401"** → wrong `WORKER_TOKEN`. Re-copy from Vercel env.

**"No active accounts available"** → all your ChatGPT accounts are rate-limited. Wait, or capture more.

**Extension can't talk to localhost** → use `http://localhost:3000` exactly (no trailing slash). Add the address to Chrome's permissions if needed.

**MongoDB connection errors** → IP not whitelisted, password wrong, or `MONGODB_URI` malformed. Test with `mongosh "<uri>"`.
