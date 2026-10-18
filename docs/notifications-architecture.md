# Notifications architecture: from one owner to opt-in subscribers

Status: proposal (issue #52). Documentation only. Nothing here changes the scraper, `notify.py`, `watchlist.py`, the workflow, or the page. Prices and limits were checked in October 2026 and are listed under [Sources](#sources); confirm them before signing up for anything.

## Summary

- **Phase 1 (Codex, issue #51)** stays exactly where SkateDeals runs today: a static site on GitHub Pages, a daily GitHub Actions scrape, and SMTP to one owner. This document gives it an event, rule, and delivery contract that does not need to change when more people subscribe.
- **Phase 2 (later, optional)** adds public, opt-in subscriptions with the smallest backend that can hold email addresses safely: one Cloudflare Worker with a D1 (SQLite) database, and a transactional email API (Resend, or Amazon SES at higher volume). The scrape stays the only place rules are evaluated. The Worker stores subscribers, sends mail, and handles verification and unsubscribe.
- **Nothing personal ever goes into git.** This repository and everything it commits are public: GitHub Pages serves the repo root, and the daily job commits `price_history.json`, `previous_data.json`, and the report. Email addresses, tokens, and per-subscriber rules live only in the Phase 2 database and in GitHub Secrets.
- **The one unavoidable Phase 2 cost is a domain** to send from (roughly $10–15 a year). Gmail and Yahoo require SPF, DKIM, and DMARC, and a `github.io` address cannot be authenticated. At low traffic everything else fits in free tiers.

## How it works today

| Piece | What it does | Where state lives |
| --- | --- | --- |
| `.github/workflows/scrape.yml` | Daily at 07:17 UTC, backup at 09:43 UTC (skipped when today already succeeded), plus manual runs. Runs `python scraper.py`, then commits the data files and the report to `main`. | Git (public) |
| `scraper.py` → `pipeline.py` | Scrapes each store and part on its own, records health, updates price history, matches the watchlist, builds the digest. | `previous_data.json`, `price_history.json`, `scrape_health.json` (public) |
| `watchlist.py` + `watchlist.yaml` | Rules: `brand` or `name`, `part`, `width` / `min_width` / `max_width`, `max_price`, `alert_on_drop`, `alert_on_low`, `back_in_stock_width`, `note`. A *hit* highlights a row; an *alert* is a hit with a reason. Reasons come from comparing today with yesterday's catalog. | `watchlist.yaml` (public) |
| `notify.py` | One HTML + text digest over SMTP to `EMAIL_TO`. Sends on new items, meaningful drops, store warnings, or watchlist alerts. Errors are logged and never fail the scrape. `EMAIL_DRY_RUN=1` writes a preview. | Secrets: `SMTP_*`, `EMAIL_FROM`, `EMAIL_TO`, `REPORT_URL` |
| Page stars | Starred rows, saved in the browser under `salesscraper2.stars`. Not connected to email. | Browser only |

Facts the design relies on:

- **Deduplication today is "compared with yesterday".** It works for one daily run. It does not remember what was sent: a manual rerun, a failed store that recovers, or a listing that flickers out for one scan can each look new again. Issue #51 adds persistent delivery state; the contract below says what that state should key on.
- **Price history is keyed by listing URL** (`history.py`). Since #48, a URL whose name starts naming another size restarts its series and keeps the old product in `earlier_products`, and a CCS (Shopify) listing whose path changed keeps its history with the old URL in `previous_urls`. Event identity builds on that series, not on names.
- **Scrape health is per store and part** (`scrape_health.json`), with `failed` and `suspect` flags. A failed or suspect key must never produce "back in stock", "new", or the end of a qualifying run.
- **The data is daily.** An alert can only be as fresh as the morning scrape, so "real time" is not a goal.

## Contract: listings, events, rules, matches, deliveries

The contract separates *what happened to a listing* (the same for everyone and public) from *who cares about it* (private). Phase 1 uses one owner; Phase 2 adds rows, not new concepts.

```
scrape ──► ListingEvent (public facts, no people)
                │
rule ──────────►│ RuleMatch (event × rule)
                │
recipient ─────►│ Delivery (match × recipient, sent once)
```

### Listing key and series

- `listing_key` is the history key: the normalized listing URL (`filters.normalize_url`).
- `series` is the `first_seen` date of the listing's current price series. It changes only when history restarts the series (another size on the same URL). A CCS listing that moved paths keeps its series, so an event that already went out is not sent again after the move.

### ListingEvent

A fact about one listing on one scan day, decided only from successful, non-suspect scans of that listing's store and part.

| Field | Meaning |
| --- | --- |
| `event_id` | Deterministic: `"{type}:{listing_key}:{series}:{param}:{since}"`. The same facts always give the same id, so reruns and retries cannot create a second event. |
| `type` | `new`, `price_drop`, `price_at_or_below`, `all_time_low`, `back_in_stock` |
| `param` | What qualified, in integer cents or a size: the new price for `price_drop`, the low for `all_time_low`, the ceiling for `price_at_or_below`, the width for a width-specific restock. Empty otherwise. |
| `since` | The first scan day of the current *qualifying run* (below). |
| `listing` | Public facts copied from the catalog: `store`, `part`, `name`, `url`, `price_cents`, `original_cents`, `width`, `image`. |
| `observed_on` | The scan day that produced it. |

**Qualifying runs (re-qualification).** A condition such as "price at or below $50" is one run from the first successful scan where it holds until a successful scan where it no longer holds. The rules for a run:

- A failed or suspect scan of that store and part neither starts nor ends a run.
- A listing carried after a single miss (`record_misses`) does not end a run. Absence ends it only after `GONE_AFTER_MISSES` (two) consecutive misses on successful scans, the same rule the page uses for "gone".
- When a run ends and the condition later holds again, that is a new run with a new `since`, so a new `event_id`. That is the only way the same listing alerts twice for the same condition.

Event types:

- `new`: first successful observation of a `listing_key` (a new series counts as new).
- `price_drop`: today's price is a meaningful drop (`filters.is_meaningful_drop`, $2 or 5%) from the previous observed price. `param` is the new price, so each lower price is its own event and holding steady is not.
- `price_at_or_below`: the price is under a rule's ceiling. This is the one rule-parameterized event. `param` is the ceiling, so two rules with different ceilings get different events.
- `all_time_low`: the price equals a *qualified* low (3 observations over 7 days, `history.all_time_low_status`). `param` is the low, so a deeper low is a new event.
- `back_in_stock`: only on reliable evidence. Either the `stock` field recorded `out_of_stock` and the listing is in stock again, or the listing returns after it was gone (two misses on successful scans). A listing that was simply missing from a failed scan is never "back".

### Rule

The same shape in YAML (Phase 1) and in the database (Phase 2). It extends today's watchlist fields; nothing existing changes meaning.

| Field | Phase 1 (YAML) | Phase 2 (database) |
| --- | --- | --- |
| `rule_id` | The YAML `id`. Should become required, because deduplication keys on it. A missing id gets a stable one derived from the fingerprint. | Random id. |
| `owner_id` | `"owner"` | The subscriber's id |
| `recipient_id` | `"owner"`, resolved at send time to `EMAIL_TO` | The subscriber's id, resolved to their verified address |
| Match fields | `brand`, `name`, `part`, `width`, `min_width`, `max_width` | Same |
| Triggers | `max_price`, `alert_on_drop`, `alert_on_low`, `back_in_stock_width`, plus `alert_on_new` (today's default when no trigger is set) | Same |
| `note` | Shown in the email | Same, length-limited |
| `fingerprint` | Hash of the normalized match fields and triggers, not `note` | Same |
| `schema_version` | `1` | `1` |

- **Owner and recipient are separate fields** from day one, even though both are `"owner"` now. Later, one person could own a rule that mails a shared address, or a rule could stay paused with no recipient, without changing the model.
- **Editing a rule's match fields or triggers changes its fingerprint**, so the rule may alert again for listings that already qualify. That is deliberate ("your edited rule matches these"). Editing only `note` changes nothing.

### RuleMatch and Delivery

- `match_id = "{rule_id}:{fingerprint}:{event_id}"`: one rule matched one event.
- A delivery is `(recipient_id, event_id)`, sent at most once even when several of that recipient's rules match the same event. The email lists every matching rule's note.
- The delivery record has `status` (`pending`, `sent`, `failed`, `suppressed`), `attempts`, `first_attempt`, and `sent_at`. A `failed` delivery is retried on later runs while its event is still qualifying, up to 3 attempts or 3 days, then dropped. A send that fails never blocks the scrape.
- One digest per recipient per run: every new delivery for that recipient in one message.

### Where Phase 1 state goes

The Phase 1 delivery state can be committed beside the other data files because it holds no personal data:

- event ids, rule ids, fingerprints, `recipient_id = "owner"`, status, and dates only;
- bounded to deliveries from the last 90 days, matching the price-history window;
- never an address or a token, so `EMAIL_TO` stays a secret.

Phase 2 subscriber deliveries live in the Phase 2 database, not in git. Even opaque subscriber ids in a public file would leak who subscribes to what and when.

### Interface notes for Codex (issue #51)

These are the shapes that let Phase 2 reuse Phase 1 without a rewrite. Names are suggestions; the semantics are the contract. If #51 settles on different names, this document should be updated to match rather than the code bent to fit it.

- **A pure function from facts to events:** `listing_events(catalog, history, health, previous) -> [ListingEvent]`. No rules and no people, deterministic for the same input.
- **A pure function from rules to matches:** `match_rules(events, rules) -> [RuleMatch]`, where `rules` is a list of rule dicts that can come from YAML or, later, from the Phase 2 API.
- **Delivery planning as its own step:** `plan_deliveries(matches, delivered) -> [Delivery]`, which applies `(recipient_id, event_id)` dedup and the retry policy.
- **Sending stays in `notify.py`**, behind dry run, and still never raises.
- **A parser that accepts every current `watchlist.yaml` file unchanged.** New fields are optional.

## Phase 2 options

All three keep the scrape on GitHub Actions and the site on GitHub Pages. They differ in where subscribers and sending live.

### Option A: a hosted newsletter list (for example Buttondown)

Subscribers sign up on the provider's hosted form and pick topics (tags such as "Decks 8.5 and wider", "Heroin"). The daily job sends one email per topic through the provider's API.

- **Operating complexity:** lowest. No server or database, and the provider runs double opt-in, unsubscribe, bounces, and compliance.
- **Cost at low traffic:** free for the first 100 subscribers, API included. Tagging is listed as a paid add-on (about $9 a month); the next tier is about $9 a month for 1,000 subscribers.
- **Deliverability:** good. It is the provider's core business; a custom sending domain is still advised.
- **Validation, unsubscribe, abuse:** handled by the provider.
- **Security:** one API key in GitHub Secrets. Addresses never touch this repo.
- **The catch:** it is a newsletter, not per-person rules. "This deck under $50 in 8.5" becomes a topic, and every topic is a separately curated list. It suits "follow a brand" and stops working at "my size, my price".

### Option B (recommended): a Cloudflare Worker with D1, plus a transactional email API

One small Worker serves a handful of JSON endpoints and stores subscribers, rules, tokens, and deliveries in D1 (SQLite). Mail goes through Resend (or Amazon SES). The scrape asks the Worker for active rules, evaluates them with the Phase 1 Python engine, and hands the matches back for delivery.

- **Operating complexity:** low to moderate. It is one Worker and one database, and there are no servers to patch. Deploys come from this repo with `wrangler`. Schema changes are plain SQL migrations.
- **Cost at low traffic:**
  - **Workers:** the free plan has about 100,000 requests a day, and a daily batch plus signups uses a few hundred.
  - **D1:** the free plan covers this scale. Since September 2026, queries over the daily row limit fail until midnight UTC instead of being billed, which only matters far beyond this size.
  - **Resend:** 3,000 emails a month free, but only 100 a day, which means about 100 subscribers each receiving one daily digest. Beyond that, Pro is about $20 a month for 50,000. Amazon SES is about $0.10 per 1,000 but starts in a sandbox that needs a human-reviewed production request.
- **Deliverability:**
  - Needs a verified domain with SPF, DKIM, and DMARC.
  - Each message carries `List-Unsubscribe` and `List-Unsubscribe-Post: List-Unsubscribe=One-Click` (RFC 8058) plus a visible link. Gmail and Yahoo expect this from bulk senders.
  - Complaint rates must stay under 0.3%.
  - Daily digests to people who confirmed are the easy case.
- **Validation, unsubscribe, abuse:** built here, and small: double opt-in, signed one-use tokens, one-click unsubscribe, rate limits, Cloudflare Turnstile on the form, and caps. Details are in the MVP section.
- **Security:**
  - The email API key and token secret live only in Worker secrets.
  - GitHub Actions holds one shared HMAC secret for the internal endpoints.
  - The static page holds no secret at all.
- **Why this one:** it is the smallest setup that supports per-person rules with real consent, and rules are still evaluated by exactly one engine, the Phase 1 Python code. That avoids a second, drifting JavaScript copy of the matching logic.

### Option C: Supabase (Postgres, auth, edge functions) plus an email API

Supabase supplies Postgres with row-level security, magic-link sign-in, and functions; mail through Resend or similar.

- **Operating complexity:** moderate. More built in (auth, an admin UI), but more surface: row-level security policies, a separate functions runtime, and auth emails to configure.
- **Cost at low traffic:** the free plan has a 500 MB database. Free projects pause after a week without activity and stay unreachable until restored by hand. Pro, which removes the pause, starts at about $25 a month. Email costs are the same as Option B.
- **Deliverability:** the same as Option B with the same email API. Supabase's built-in auth email is rate-limited and meant for development, so a custom SMTP provider is needed anyway.
- **Validation, unsubscribe, abuse:** magic links come for free. Unsubscribe and rate limits are still ours to build.
- **Security:** row-level security mistakes expose data directly from the client. The anon key is public by design, so every policy has to be right.
- **Fits when:** subscribers later need real accounts or a richer self-service area. It is too much for a daily digest.

### Side by side

| | A: hosted list | B: Worker + D1 + email API | C: Supabase + email API |
| --- | --- | --- | --- |
| Per-person rules (brand, size, price) | No, topics only | Yes | Yes |
| Servers or databases to run | None | One Worker, one SQLite database | Postgres, functions, auth |
| Likely cost, under 100 subscribers | $0, or about $9 a month for tags | $0 plus the domain | $0 with pause risk, or about $25 a month |
| Next cost step | About $9 a month | About $20 a month (Resend Pro) or SES per 1,000 | About $25 a month plus email |
| Double opt-in and unsubscribe | Provider | Built (small) | Partly built |
| Matching logic | One per topic, manual | Phase 1 Python engine, reused | Phase 1 engine, or re-implemented |
| Biggest risk | Outgrown quickly | Getting consent and token handling right | Paused project; row-level security mistakes |

## Recommended Phase 2 MVP (Option B)

### Daily flow

1. **The scrape runs unchanged.** It builds `ListingEvent`s from successful scans only.
2. **New workflow step: fetch active rules.** `GET /internal/rules`, signed with HMAC, returns `{rule_id, owner_id, recipient_id, fingerprint, fields}` for verified, active subscribers. It returns no addresses. The rules are held in memory for the run and never written to disk or logs.
3. **The Phase 1 engine evaluates them,** together with the owner's YAML rules: `match_rules(events, rules)`.
4. **Hand the matches to the Worker.** `POST /internal/matches`, signed with HMAC, sends the matches plus each event's public facts. The Worker plans deliveries with the same `(recipient_id, event_id)` rule against its `deliveries` table, renders one digest per subscriber, and sends.
5. **The owner's own mail** can keep the Phase 1 SMTP path, or move to the Worker later.

What happens when things fail:

- **Worker unreachable:** the step logs a warning and the scrape still commits. The next run posts again, and dedup makes that safe.
- **Rerun or backup cron:** same events, same ids, no second email.
- **A store fails today:** it produces no events, so it cannot send "back in stock" tomorrow on its own.

The internal endpoints accept only requests signed with HMAC-SHA256 over the method, path, timestamp, and body hash. They reject a timestamp older than 5 minutes or a reused nonce.

### Endpoints

Public endpoints are called by the static site:

| Endpoint | Purpose | Notes |
| --- | --- | --- |
| `POST /subscribe` | `{email, rules[], consent: true, consent_version, turnstile_token}` | Creates a *pending* subscriber and sends one verification email. Rules stay inactive until verified. Always returns `202` with the same body, so the endpoint cannot be used to test whether an address is subscribed. |
| `POST /verify` | `{token}` | Activates the subscriber and returns a manage link. The page reads the token from the URL fragment (`#token=`), which keeps it out of server logs and Referer headers, and posts it. |
| `POST /link` | `{email, turnstile_token}` | Emails a fresh manage link. Always `202`. Also serves people who lost their link. |
| `GET` / `PUT /preferences` | `Authorization: Bearer <manage token>` | Read and replace the subscriber's rules: at most 10 rules, the same validation as the Python rule parser, `note` up to 80 characters. |
| `POST /unsubscribe` | Token in the body, or the RFC 8058 one-click `POST` to the `List-Unsubscribe` URL | Immediate. Works without Turnstile, because one-click must. |
| `DELETE /subscriber` | Bearer manage token | Deletes the subscriber and their rules. Keeps a suppression hash only. |

Internal endpoints are called by GitHub Actions, signed with HMAC: `GET /internal/rules` and `POST /internal/matches`.

Provider webhooks for bounces and complaints (verified signature) suppress the address.

### Data model (D1)

- `subscribers`: `id`, `email`, `email_hash`, `status` (`pending`, `active`, `unsubscribed`, `suppressed`), `consent_version`, `created_at`, `verified_at`.
- `rules`: `id`, `subscriber_id`, `fields` (JSON, schema v1), `fingerprint`, `created_at`, `updated_at`.
- `tokens`: `token_hash`, `subscriber_id`, `purpose` (`verify`, `manage`), `expires_at`, `used_at`.
  - Tokens are 32 random bytes, stored only as a hash.
  - Verify tokens expire in 48 hours and are single-use.
  - Manage tokens expire in 30 days, and every digest carries a fresh one.
- `deliveries`: `subscriber_id`, `event_id`, `status`, `attempts`, `sent_at`, unique on (`subscriber_id`, `event_id`).
- `suppressions`: `email_hash`, `reason`, `created_at`. It lets a re-signup after a complaint be refused without keeping the address.

### Consent

- Opt-in only: a consent checkbox that starts unchecked, and plain text about what is sent (at most one digest a day, only when a rule matches) and how to stop.
- Double opt-in: nothing is sent except the verification email until the person clicks it. There are no imports, no adding friends, and no pre-checked boxes.
- `consent_version` records which wording they agreed to.
- Every email has the one-click unsubscribe header and a visible link. Unsubscribing takes effect immediately, well inside Yahoo's 2-day expectation.

### Privacy and retention

| Data | Kept for |
| --- | --- |
| Pending, never verified | Deleted after 7 days |
| Active subscriber and rules | While subscribed |
| Unsubscribed | Address and rules deleted at once; suppression hash kept |
| Deliveries | 90 days, the same as the price-history window |
| Tokens | Until used or expired, then deleted |
| Logs | No addresses or tokens; subscriber ids only |

- No open or click tracking: turn both off at the email provider.
- No third-party scripts on the signup page beyond Turnstile.
- A short privacy note on the page says what is stored, why, for how long, and how to delete it.

### Abuse limits

- Turnstile on `/subscribe` and `/link`.
- Rate limits per IP and per email hash: 5 signups an hour per IP, and 3 verification emails a day per address.
- At most 10 rules per subscriber, at most one digest per subscriber per day, and an MVP-wide cap of about 200 active subscribers so a spike cannot exhaust the email plan.
- Bounces and complaints suppress the address automatically. If complaints approach 0.3%, pause sending.
- The Worker validates every rule field and treats `note` and names as text, never markup.

### Security

- The static site has **no secrets** and is not trusted. It only calls the public endpoints, and the Worker validates everything again.
- CORS allows only `https://pchoward.github.io` on the public endpoints.
- Secrets:
  - Worker: email API key, HMAC secret, token secret.
  - GitHub: the HMAC secret only (`ALERTS_HMAC_SECRET`) plus the Worker URL.
- Addresses never appear in git, Actions logs, the event feed, or the report.
- **Prerequisite:** a sending domain with SPF, DKIM, and DMARC (start at `p=none` and tighten later).

## Migrating from YAML

1. **Phase 1 (#51):**
   - `watchlist.yaml` keeps working byte for byte.
   - The owner's rules get `owner_id = recipient_id = "owner"`.
   - `id` becomes required for new rules, and missing ids get a stable derived id.
   - Delivery state starts empty, so the first run sends what currently qualifies once, and then only new events.
2. **Phase 2, owner unchanged:** YAML stays the owner's source of truth in git. Subscriber rules live in D1. The engine reads both and treats them the same.
3. **Optional later:** the owner moves into D1 by creating a subscriber, importing the YAML rules with their existing `rule_id`s and fingerprints, and marking the YAML read-only. Matching ids mean no repeat alerts.
4. **Rollback:** turn off the Phase 2 workflow step. The scrape, the report, and the owner's mail keep running as in Phase 1.

## Future UI contract (for Grok; do not build during the image-card redesign)

This defines what a later UI change needs. None of it should be built in #50 or before Phase 2 exists.

- **Entry points:**
  - A "Get alerts" link in the top bar.
  - An "Alert me" action in a card's Details sheet that opens the form prefilled from that listing: `part`, `name` or `brand`, `width`, and the current price as a suggested `max_price`.
  - Stars stay local. They can prefill the form but never subscribe anyone.
- **Form fields:**
  - email;
  - rule fields as in the Rule table, with the parts and widths that the filters already offer;
  - trigger checkboxes (new, drop, all-time low, under a price, back in stock);
  - an optional note;
  - the consent checkbox, unchecked, with a link to the privacy note;
  - Turnstile.
- **States:** idle, submitting, "check your email" (the same message whether or not the address exists), error with retry, rate-limited.
- **Manage page:** a static page that reads `#token=` from the URL, calls `GET /preferences`, and offers edit, add, remove (up to 10), unsubscribe, and delete. If the token is expired, it offers "email me a new link".
- **Accessibility and mobile:**
  - The form works on a phone (16px inputs, as in `mobile.css`).
  - Every control has a label, and errors are announced with `aria-live`.
  - The flow never relies on a popup.
- **No client logic decides who gets mail.** The page only submits preferences.

## What not to build yet

- Accounts, passwords, or OAuth sign-in. Magic links are enough for a daily digest.
- SMS, push, or "real-time" alerts. The data changes once a day.
- Per-subscriber frequencies or quiet hours. One daily digest covers it.
- Open or click tracking, or analytics on subscribers.
- An admin dashboard. The D1 console and a script are enough at this size.
- Running our own mail server, or sending subscriber mail from a personal Gmail account (deliverability and terms problems).
- Any secret, address, or subscriber rule in this repository, the event feed, or browser code.
- A JavaScript copy of the matching rules. One engine, in Python.
- Payments or premium tiers.

## Open questions for the owner

- Which domain to send from, and who controls its DNS.
- Whether the owner's own alerts should stay on SMTP or move to the Worker once it exists.
- The subscriber cap and the rule limit (200 and 10 proposed).
- Whether Option A (topics only) is enough at first. It needs no code and could test interest before building Option B.

## Sources

Checked October 2026. Treat third-party pricing as approximate and confirm it on the provider's own page.

- Cloudflare D1 free-tier limit enforcement: <https://developers.cloudflare.com/changelog/post/2026-09-01-d1-free-tier-limit-enforcement/>
- Cloudflare free limits summary (third party): <https://eastondev.com/blog/en/posts/dev/20260526-cloudflare-free-limits/>
- Resend pricing: <https://resend.com/pricing.md> and free-tier summary <https://automationatlas.io/answers/resend-free-tier-explained-2026/>
- Amazon SES pricing and sandbox (third party): <https://www.usecarly.com/blog/amazon-ses-pricing/>, <https://cloudburn.io/blog/amazon-ses-pricing>
- Buttondown pricing and free-plan API: <https://buttondown.com/pricing?plan=free>, <https://newsletter.buttondown.com/archive/updates-from-january-9711>
- Supabase pricing and inactivity pause: <https://supabase.com/docs/pricing>, <https://supabase.com/pricing.md>
- Gmail and Yahoo sender requirements, RFC 8058: <https://www.resend.com/blog/gmail-and-yahoo-bulk-sending-requirements-for-2024>, <https://aws.amazon.com/cn/blogs/messaging-and-targeting/an-overview-of-bulk-sender-changes-at-yahoo-gmail/>, <https://www.palisade.email/learning/one-click-unsubscribe>
