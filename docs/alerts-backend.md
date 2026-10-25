# Alerts backend: setup, staging, delivery, and rollback

This implements Phase 2 of [notifications-architecture.md](notifications-architecture.md) (issue #58):

- a Cloudflare Worker with a D1 database for opt-in subscribers (`worker/`);
- delivery from the daily GitHub Actions scrape through the existing Python engine (`alerts_delivery.py`).

The UI contract is [alerts-api.md](alerts-api.md).

**Staging only.** The Worker runs in `staging` mode for the owner's allowlisted address. Subscriber delivery from Actions (`ALERTS_DELIVERY_ENABLED`) and production signups are off. Every switch defaults to off. The owner's own digest (`notify.py`, `notification_engine.py`) is unchanged and does not depend on any of this.

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
./deploy.sh                                        # not plain `wrangler deploy`; see below
curl https://<worker>/v1/health                    # {"ok":true,...,"mode":"staging","commit":"<12 hex>"}
```

**Every later deploy** is `git checkout main && git pull && ./worker/deploy.sh`. The script:
- refuses unless the checkout is exactly `origin/main` with no uncommitted `worker/` changes;
- applies any pending D1 migrations;
- deploys with `GIT_COMMIT` set, so `/v1/health` reports which commit is live.

A merge that changes `worker/` is **not live until this runs**. GitHub Pages does not deploy the Worker.

**Drift check.** The **Alerts Worker drift** workflow runs daily, or on demand from Actions. It fails when the live Worker's commit lacks the newest `worker/src` or `worker/migrations` change on main. It reads only the public health endpoint and never deploys. To turn it on, set the repository variable `ALERTS_API_URL` to the Worker URL. That variable alone does not enable delivery, which still needs `ALERTS_DELIVERY_ENABLED`.

Keep a copy of `HMAC_SECRET` for GitHub, below. Never rotate `TOKEN_PEPPER` casually: it makes every link and stored hash invalid.

Staging checklist:

- [ ] Subscribe with an allowed address, verify, then edit rules.
- [ ] Add a digest and a product watch with `PUT /v1/preferences` (or the page, once it supports them). `GET /v1/preferences` shows `product_key`.
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
3. For each route, `notification_engine.evaluate` plans events for its **search** rules and its **product watches** with that route's own journal (`alerts_state/<sha256(route)>.json`). Watches are evaluated under their own engine alias, so their state is kept apart from search rules (see "Product watches" below). The rules are the engine's own:
   - events fire on newly qualifying conditions only;
   - failed or suspect store scans produce nothing;
   - back in stock needs verified evidence;
   - a watch re-arms after its condition clears.
4. A route with a **digest** rule also gets today's digest section, built once per run for everyone (see "General digest" below).
5. The events are marked `sending` and the journal is saved **before** anything is posted. If the save fails, nothing is sent.
6. The job signs `POST /v1/internal/deliveries`, one entry (one email) per route. The Worker keeps one row per `(subscriber, event_id)` and emails only events it has never handled:
   - **Resend idempotency:** each send carries an `Idempotency-Key`.
   - **Unsubscribe:** every email has `List-Unsubscribe` and `List-Unsubscribe-Post` (RFC 8058) plus a footer link.
   - **Links:** product links must go to the tracked store hosts.
7. Each answer is written back to the journal:

| Worker status | Meaning | Journal |
| --- | --- | --- |
| `sent` | emailed now | delivered |
| `duplicate` | every event already emailed | delivered |
| `inactive` | subscriber is gone | delivered (dropped) |
| `deferred` | daily cap reached (3 by default) | pending, tried next run |
| `failed` | provider refused before accepting | pending, tried next run |
| `uncertain` | provider may have accepted | held; never resent automatically |
| no answer (network) | unknown | pending; the Worker's per-event record makes the retry safe |

8. Actions saves `alerts_state/` to its cache, never to git. A missing cache stops delivery until `ALERTS_ALLOW_BOOTSTRAP=1` is set on purpose. One known subscriber's missing journal skips only that subscriber.

## General digest (`kind: "digest"`)

- **What qualifies:** the owner digest's own rules, from `report.compare_catalogs` and `build_digest`:
  - `new`: a listing that passes the site filters and was not in the previous scrape;
  - `drop`: a sale price at least $2 or 5% under the previous scrape's price;
  - `low`: a listing that is now at its lowest tracked price and was above it in the previous scrape. Lows need at least 3 observations over 7 days.
  When a drop also reaches a new low, it is listed once, as a low.
- **What never qualifies:**
  - stores that failed or looked suspect this run;
  - listings carried after a single miss;
  - any "new" without a previous scrape.
- **Re-listing guard:** a store category with no rows in the previous scrape is a first listing, not news. So is one where more than half of today's rows, and more than 20 of them, are "new". Its new listings are left out that day, but its drops and lows still count. In the replayed October scrapes, this is what stopped new store categories (44 accessories at once, for example) from flooding the email.
- **Filters** per subscriber: `parts`, `events`, deck `min_width`/`max_width`, and `max_price` (at or under).
- **Frequency:** at most one digest email per subscriber per scrape day. Its event id is `sha256(["digest", route_id, day])`, and the Worker records it like any alert event. A second run the same day sends no second digest. Listings first seen in that second run are not emailed; they are on the site.
- **Volume:** the best 30 listings, ranked new lows first, then drops by percent, then new listings by discount. `total` gives the full count, and the email links to the site for the rest. Replaying the scrapes of Oct 11–24, 2026 gave 0–25 qualifying listings a day. One day had 128 (a large Zumiez catalog change), which would have been sent as 30 plus a "98 more" link.
- **One email:** when the subscriber's watches or searches fire too, alerts and the digest arrive together, and that counts once against `DAILY_EMAILS_PER_SUBSCRIBER`.
- **Not retried:** a day's digest is not queued. If the provider refuses it, it may be retried only the same day. An uncertain send is never repeated, and the next day has its own digest.

## Product watches (`kind: "watch"`)

- **Identity:** a watch stores the listing URL and the Worker's `product_key`.
  - `alerts_delivery` recomputes the key with `history_identity.listing_identity` and drops any watch where the two disagree. A watch never guesses.
  - `worker/contract/product-keys.json` holds the test vectors. Both test suites check them, plus that both sides allow the same store hosts.
- **How it is matched:**
  1. The engine sees each watched product under one canonical URL (Shopify `/products/<handle>`, otherwise the URL itself) and a fixed part, and nothing else.
  2. Its history, previous price, stock evidence, and carried listings are mapped the same way.
  3. A watch keeps its price memory when CCS or Muir moves the product between collection and product URLs.
  4. The email links today's real listing.
- **Triggers:** a watch is always explicit. With no trigger it is `alert_on_drop`, so it never sends the engine's "New watch match" on first sight. Other triggers, in addition to or instead of the drop:
  - **price:** under `max_price`;
  - **drop:** a meaningful drop;
  - **low:** a verified historical low;
  - **restock:** a verified restock (`alert_on_stock`).
- **Cross-store:** none. Each watch is one store's listing. Name-based cross-store groups never route email.
- **Removing a watch** deletes its engine records on the next run, and so does removing a search rule. Watch records and search records are evaluated under different engine aliases, so neither affects the other.

## Backward compatibility

- **Stored rules:** existing rules have no `kind` and are `search` rules. They validate, normalize, and get the same ids as before. Their journals are untouched, because search rules are evaluated exactly as before under the route id.
- **No migration:** rules stay JSON in `rules.fields`; the kind is a field in that JSON. The digest's once-a-day record is an ordinary `deliveries` row.
- **API:** the `routes` and `deliveries` payloads stay `version: 1`.
  - **Older delivery job, newer Worker:** an older `alerts_delivery.py` drops rules with a `kind` as invalid and logs a count. It never misreads them.
  - **Older Worker, newer job:** the Worker rejects a delivery with a `digest` section (`400`), and the job keeps those events pending.

  So deploy the Worker first, then merge the Python side.
- **Page:** the page keeps working unchanged. It sends search rules, and responses for search rules look exactly as before. New kinds show up in preferences only after someone adds them.

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
cd worker && node --test 'test/*.test.js'        # 39 tests, real SQLite, network mocked
python -m unittest test_alerts_delivery          # includes an end-to-end run against the mock Worker
```

No test sends email or touches the network. CI runs both.

## Follow-ups (not in this slice)

- **The Subscribe and Alert me flows for digests and watches** (issue #71, UI), against [alerts-api.md](alerts-api.md) and `worker/contract/examples-digest-watch.json`.
- **Resolving held deliveries:** a small owner CLI to review and resolve `uncertain` subscriber deliveries, on both the Worker rows and the route journal. Until it exists, a held delivery stays held. That is safe (no duplicates), but that watch stays quiet.
- **Sneaker size rules** for subscribers, on searches and watches. The engine supports them; the subscriber schema leaves them out for now.
- **Privacy note:** a short privacy page, linked from the form and the emails, written from the retention table above.
