# Alerts backend: setup, staging, delivery, and rollback

This implements Phase 2 of [notifications-architecture.md](notifications-architecture.md) (issue #58):

- a Cloudflare Worker with a D1 database for opt-in subscribers (`worker/`);
- delivery from the daily GitHub Actions scrape through the existing Python engine (`alerts_delivery.py`).

The UI contract is [alerts-api.md](alerts-api.md).

**Nothing is deployed.** The code is inert until the owner creates the accounts below, deploys, and turns it on. Every switch defaults to off. The owner's own digest (`notify.py`, `notification_engine.py`) is unchanged and does not depend on any of this.

## Prerequisites (owner's decisions and accounts)

| Need | Why | Cost (Oct 2026; confirm) |
| --- | --- | --- |
| Cloudflare account | Worker, D1, Turnstile | Free plan is enough at this size |
| A domain you control (DNS access) | Sending from your own address; SPF, DKIM, and DMARC | about $10–15 a year |
| Resend account with that domain verified | Sending | Free for 3,000 a month and 100 a day; Pro is about $20 a month |
| Turnstile site (in Cloudflare) | Bot protection on the forms | Free |

Resend's `onboarding@resend.dev` sender **is for testing only**. It can only deliver to the email address on the Resend account. The Worker therefore refuses to start in `production` with an `@resend.dev` sender, and allows it only in `staging`, where every recipient must also be listed in `STAGING_ALLOWED_EMAILS`.

## Modes

| `MODE` | Email | Turnstile | Recipients | Use |
| --- | --- | --- | --- | --- |
| `mock` | Never sent; written to the outbox table | `mock-turnstile-pass` | anyone | Local UI work: `node worker/dev/mock-server.js` |
| `staging` | Resend; `onboarding@resend.dev` allowed | real | only `STAGING_ALLOWED_EMAILS` | The owner testing the real flow |
| `production` | Resend from the verified domain | real | the public, double opt-in | Live |

**Fail closed.** If any required setting is missing or unsafe, every endpoint answers `503 service_unavailable` and nothing is sent. That covers a missing mode, a short secret, a non-https URL, a missing Resend or Turnstile key outside mock, a test sender in production, or an empty staging allowlist. `GET /v1/health` lists the missing setting *names* only.

## Domain and DNS (production)

1. In Resend, add the sending domain. A subdomain such as `alerts.example.com` keeps this mail's reputation separate.
2. Add the DNS records Resend shows:
   - the DKIM `TXT` (or `CNAME`) records;
   - the SPF `TXT` record (and the `MX` record) on the bounce subdomain.
   Wait until Resend says **Verified**.
3. Add a DMARC record for the domain. Start with monitoring:
   `_dmarc.example.com TXT "v=DMARC1; p=none; rua=mailto:dmarc@example.com"`
   Move to `p=quarantine` after a few clean weeks.
4. In Resend, turn **off** open and click tracking for this domain. The privacy promise is no tracking.
5. Create an API key with **sending access** for that domain only.
6. Optional but recommended: add a webhook in Resend to `https://<worker>/v1/webhooks/resend` for `email.bounced` and `email.complained`, then set its signing secret as `RESEND_WEBHOOK_SECRET`. Without the secret the webhook endpoint stays disabled.

## Deploy (staging first)

Run these from `worker/` with Wrangler, using the owner's account:

```bash
cp wrangler.toml.example wrangler.toml            # gitignored; fill in the placeholders
wrangler d1 create skatedeals-alerts               # put the database_id into wrangler.toml
wrangler d1 migrations apply skatedeals-alerts --remote
openssl rand -base64 48 | wrangler secret put HMAC_SECRET
openssl rand -base64 48 | wrangler secret put TOKEN_PEPPER
wrangler secret put RESEND_API_KEY
wrangler secret put TURNSTILE_SECRET
wrangler secret put STAGING_ALLOWED_EMAILS         # staging: your own inbox(es)
wrangler deploy
curl https://<worker>/v1/health                    # {"ok":true,...,"mode":"staging"}
```

Keep a copy of `HMAC_SECRET` for GitHub, below. Never rotate `TOKEN_PEPPER` casually: it makes every link and stored hash invalid.

Staging checklist:

- [ ] Subscribe with an allowed address, verify, then edit rules.
- [ ] A disallowed address gets `403`.
- [ ] One-click unsubscribe deletes the row: run `wrangler d1 execute skatedeals-alerts --remote --command "SELECT COUNT(*) FROM subscribers"`.
- [ ] Run one scrape with delivery on (below), and get one digest.
- [ ] Run again, and get no second digest.

For production, set `MODE = "production"`, set `EMAIL_FROM` to the verified domain, remove `STAGING_ALLOWED_EMAILS`, and `wrangler deploy`.

## GitHub Actions settings

| Name | Kind | Value |
| --- | --- | --- |
| `ALERTS_HMAC_SECRET` | Secret | Same as the Worker's `HMAC_SECRET` |
| `ALERTS_API_URL` | Variable | `https://<worker>` (https, no path) |
| `ALERTS_DELIVERY_ENABLED` | Variable | `1` to turn delivery on; unset or anything else is off |
| `ALERTS_ALLOW_BOOTSTRAP` | Variable | `1` for the **first** enabled run only, then delete it |

With `ALERTS_DELIVERY_ENABLED` unset, the scrape behaves exactly as before. The new workflow steps are skipped, and `alerts_delivery.py` is not imported.

## Daily delivery flow

1. The scrape and the owner's digest run as before.
2. `alerts_delivery.deliver_subscriber_alerts` signs `GET /v1/internal/routes`. It receives `{route_id, rules}` for **verified** subscribers only: opaque ids and rules, never addresses.
3. For each route, `notification_engine.evaluate` plans events with that route's own journal (`alerts_state/<sha256(route)>.json`). The rules are the engine's own:
   - events fire on newly qualifying conditions only;
   - failed or suspect store scans produce nothing;
   - back in stock needs verified evidence;
   - a watch re-arms after its condition clears.
4. The events are marked `sending` and the journal is saved **before** anything is posted. If the save fails, nothing is sent.
5. The job signs `POST /v1/internal/deliveries`. The Worker keeps one row per `(subscriber, event_id)` and emails only events it has never handled:
   - **Resend idempotency:** each send carries an `Idempotency-Key`.
   - **Unsubscribe:** every email has `List-Unsubscribe` and `List-Unsubscribe-Post` (RFC 8058) plus a footer link.
   - **Links:** product links must go to the tracked store hosts.
6. Each answer is written back to the journal:

| Worker status | Meaning | Journal |
| --- | --- | --- |
| `sent` | emailed now | delivered |
| `duplicate` | every event already emailed | delivered |
| `inactive` | subscriber is gone | delivered (dropped) |
| `deferred` | daily cap reached (3 by default) | pending, tried next run |
| `failed` | provider refused before accepting | pending, tried next run |
| `uncertain` | provider may have accepted | held; never resent automatically |
| no answer (network) | unknown | pending; the Worker's per-event record makes the retry safe |

7. Actions saves `alerts_state/` to its cache, never to git. A missing cache stops delivery until `ALERTS_ALLOW_BOOTSTRAP=1` is set on purpose. One known subscriber's missing journal skips only that subscriber.

**Scale.** The engine evaluates each subscriber's rules against the whole catalog. That's fine for the MVP cap of 200 subscribers × 10 rules on a 600-item catalog, but measure it before raising the cap.

## Privacy and retention

| Data | Where | Kept |
| --- | --- | --- |
| Email address | D1 `subscribers` only | While pending or subscribed. Unsubscribe and delete remove it immediately, along with rules, tokens, and deliveries. |
| Pending, never verified | D1 | Deleted after 7 days (daily cron) |
| Verify and manage tokens | D1, hashed | Verify links last 48 hours, single use; manage links last 30 days. Expired or used tokens are deleted. |
| Delivery records | D1 | Event ids only, 90 days |
| Bounce or complaint | D1 `suppressions` | Only an HMAC hash of the address, to refuse a re-signup |
| Rate-limit counters | D1 | Hashed buckets, 2 days |
| Subscriber journals | Actions cache | Hashes only. Deleted when the subscriber leaves. |

These things never contain an address, token, or subscriber rule:
- git and GitHub Pages;
- Actions logs (counts only) and Worker responses to the job;
- `price_history.json` and the report.

## Rollback

- **Stop sending at once:** delete the `ALERTS_DELIVERY_ENABLED` variable. The next scrape skips subscriber delivery entirely.
- **Stop signups:** set `MAX_ACTIVE_SUBSCRIBERS = "0"` and redeploy (new signups get `503 signups_closed`). Or set `MODE` to something invalid, which makes every endpoint return `503`.
- **Bad Worker version:** `wrangler rollback`. The schema only grows by new migrations, so an older Worker still runs against it.
- **Remove everything:** `wrangler delete`, then delete the D1 database, which erases all subscriber data. Then remove the GitHub variable and secret. The scraper and the owner's digest are unaffected.

## Migrations

- **Files:** `worker/migrations/NNNN_*.sql`, applied in order with `wrangler d1 migrations apply`. Never edit an applied migration; add a new file.
- **Tests:** they apply every migration to a fresh SQLite database, so a broken migration fails CI.
- **Rules:** a stored rule is schema v1 JSON. A future v2 needs a migration that rewrites `rules.fields`, plus matching updates to `worker/src/rules.js` and `alerts_delivery._clean_rule`.
- **From YAML:** `watchlist.yaml` stays the owner's source of truth and keeps working unchanged. Moving the owner into D1 is optional and later: subscribe the owner's address, then recreate the YAML rules through `PUT /v1/preferences`.

## Security notes

- **Internal HMAC:** requests are signed over method, path, timestamp, nonce, and body hash. The clock window is 5 minutes and each nonce works once. Python and JavaScript share a test vector.
- **Public API:**
  - CORS allows only `PUBLIC_ORIGIN`, plus localhost in mock mode.
  - Bodies are capped at 16 KB and must be JSON.
  - Strict validation rejects unknown fields.
  - Turnstile checks fail closed.
- **No enumeration:** subscribe and link answers are the same for any address, and the per-address limits are silent.
- **Abuse limits:**
  - per IP: 5 signups an hour, 10 link requests an hour;
  - per address: 3 verification emails a day, 3 link emails a day;
  - 200 new signups a day overall;
  - an active-subscriber cap;
  - 10 rules per subscriber, and 3 emails per subscriber per day.
- **Mail content** is rendered by the Worker with every value escaped. Links can only go to tracked store hosts.

## Tests

```bash
cd worker && node --test test/*.test.js          # 30 tests, real SQLite, network mocked
python -m unittest test_alerts_delivery          # includes an end-to-end run against the mock Worker
```

No test sends email or touches the network. CI runs both.

## Follow-ups (not in this slice)

- **The alerts page and manage page (Grok, against [alerts-api.md](alerts-api.md)).** Without a page there is no way to subscribe, so the backend can be deployed to staging but is not useful to the public yet.
- **Resolving held deliveries:** a small owner CLI to review and resolve `uncertain` subscriber deliveries, on both the Worker rows and the route journal. Until it exists, a held delivery stays held. That is safe (no duplicates), but that watch stays quiet.
- **Sneaker size rules** for subscribers. The engine supports them; the subscriber schema leaves them out for now.
- **Privacy note:** a short privacy page, linked from the form and the emails, written from the retention table above.
