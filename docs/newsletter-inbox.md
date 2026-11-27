# Store newsletters in the promo strip

Owner, 2026-11-27. Some stores we can't scrape (Jenson USA, Dan's Comp and
Competitive Cyclist all have bot walls) email their sales and codes. Their mail
goes to a ShredDeals inbox. The promo strip then shows those codes and links
to the store's homepage. Their items aren't listed.

## How it works
1. **Cloudflare Email Routing** sends mail for `NEWSLETTER_INBOX` (e.g.
   `deals@shreddeals.com`) to the alerts Worker's `email` handler
   (`worker/src/newsletters.js`).
2. **The Worker keeps a mail only when all of these hold:**
   - it's addressed to that inbox;
   - its From domain belongs to a store in `SENDERS`;
   - Cloudflare's own Authentication-Results says **DMARC passed** for that domain.

   So forged or unrelated mail is dropped. The store name comes from
   `SENDERS`, never from the mail. Only the subject and up to 20,000
   characters of text are kept, for 45 days.
3. **The promo check** (`promo-check.yml`, twice a day) gets the stored
   mail through a separate `newsletters` job. That job holds the alerts secret,
   makes the signed `GET /v1/internal/newsletters` and reads no store pages.
   The promo job, which reads untrusted store pages, gets the mail as a file
   and holds no secret. It finds codes with the
   same rules it uses on store pages (`promos.newsletter_promos`). Sign-up,
   text-club and first-order codes are left out, judged by the code's own
   sentence and the one before it. A code shows until its end date; with no
   end date, for 7 days after the mail; "ends tonight" means the day it was
   sent.

Mail text is untrusted data. Only the code, the discount, the end date and
conditions ("sale items", "full price") are taken from it, each checked
against a strict pattern.

## Setup (owner)
1. **Cloudflare dashboard** → shreddeals.com → **Email** → **Email Routing**:
   enable it. Cloudflare adds the MX and SPF records. Then **Routing rules** →
   **Create address**: `deals@shreddeals.com`, action **Send to a Worker**,
   Worker `skatedeals-alerts`.
2. **Worker settings:** in your private `worker/wrangler.toml`, under `[vars]`,
   set `NEWSLETTER_INBOX = "deals@shreddeals.com"`. `HMAC_SECRET` must
   already be set (`wrangler secret put HMAC_SECRET`, the same value as the
   GitHub secret `ALERTS_HMAC_SECRET`).
3. **Database:** `wrangler d1 migrations apply skatedeals-alerts --remote`
   adds the `newsletters` table.
4. **Deploy:** `./worker/deploy.sh`.
5. **GitHub** → Settings → Secrets and variables → Actions:
   - variable `NEWSLETTERS_ENABLED` = `1`
   - variable `ALERTS_API_URL` = the Worker's URL (it may already be set)
   - secret `ALERTS_HMAC_SECRET` (it may already be set)
6. **Sign `deals@shreddeals.com` up** for the newsletters of Jenson USA, Dan's
   Comp and Competitive Cyclist. Owner-approved subscriptions only
   (CLAUDE.md). Confirm each sign-up email: open the link from your normal
   mail by forwarding a copy, or temporarily add a second routing rule to
   your own address.

## Adding a store
Add its sending domain to `SENDERS` in `worker/src/newsletters.js` (redeploy),
and its name, homepage and sports to `NEWSLETTER_STORES` in `promos.py`, with
the owner's OK for the subscription.

## Checking it
The promo check's log says "Newsletters: N mails, M current offers". The
store monitor lists new email offers on the "Store monitor" issue for the
first weeks, so wrong matches can be tuned.
