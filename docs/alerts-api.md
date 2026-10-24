# Alerts API v1 (contract for the UI)

This is the contract between the SkateDeals alerts page and the alerts Worker (`worker/`). It is checked by tests. Two complete sessions are replayed against the Worker by `worker/test/contract.test.js`, which requires the exact status codes and bodies shown:

- `worker/contract/examples.json`: the original flow with brand/name rules;
- `worker/contract/examples-digest-watch.json`: the general digest and product watches (issue #70).

If this page and those files ever disagree, the files are right; please report the difference.

**Status:** deployed to staging only (allowlisted addresses). Stars and browser-only settings never send email; only a subscription confirmed by email does.

## Build against the mock

```bash
cd worker
node dev/mock-server.js        # http://localhost:8787, no Cloudflare account, no email sent
```

In mock mode:

- **Captcha:** the Turnstile token `mock-turnstile-pass` passes and any other token fails. The real widget isn't needed.
- **Email:** nothing is sent. Messages land in `GET /v1/mock/outbox`, newest first, with their links. `DELETE /v1/mock/outbox` clears it.
- **Links:** verification and manage links point at `MANAGE_PAGE_URL`, which defaults to `http://localhost:8000/alerts.html`. Change it with `MANAGE_PAGE_URL=... node dev/mock-server.js`.
- **CORS:** allows the site origin plus any `http://localhost:*` or `http://127.0.0.1:*` page.
- **Storage:** data lives in memory until the server stops. Set `MOCK_DB=/tmp/alerts.db` to keep it.

## Conventions

- **Base URL:** `PUBLIC_API_URL`, the Worker's address. The page must read it from one constant so staging and production can differ.
- **Requests** with a body send `Content-Type: application/json`, at most 16 KB.
- **Errors** are `{"error": "<code>"}`, sometimes with `fields` (validation) or `retry_after` (seconds, also in the `Retry-After` header).
- **Authenticated calls** send `Authorization: Bearer <manage_token>`.
- **Tokens arrive in the URL fragment**, `#verify=<token>` or `#manage=<token>`, so they never reach a server log or a `Referer` header. Read them with `location.hash`, then remove them with `history.replaceState`. Keep the manage token in memory, or at most in `sessionStorage`, never in `localStorage`.
- **Uniform answers:** `/v1/subscribe` and `/v1/link` answer the same way whether or not an address is subscribed. Show "Check your email" for every `202`.

## Rules (schema v1)

A subscription holds up to `max_rules` rules (10 by default) of three kinds. One subscription can mix them, and one confirmation covers all of them. `kind` picks the kind; leaving it out means `"search"`, so rules written before kinds existed keep working unchanged.

| Kind | Made by | Emails about |
| --- | --- | --- |
| `digest` | the main page's **Subscribe** | today's deals in general: no product chosen |
| `watch` | a product card's **Alert me** | one store listing, by its URL |
| `search` | (advanced) words in product names | any listing whose name has those words |

Every response adds `"id"` (`r_` + 24 hex characters) and returns keys sorted. Editing only display text (`note`, or a watch's `label`) keeps the id.

### `digest`: the general daily deals email

| Field | Type | Rules |
| --- | --- | --- |
| `kind` | `"digest"` | required |
| `parts` | list of `"Decks"`, `"Trucks"`, `"Wheels"`, `"Bearings"`, `"Sneakers"`, `"Accessories"`, `"Completes"` | Optional; omitted means every part. Returned in that order. |
| `events` | list of `"new"`, `"drop"`, `"low"` | Optional; omitted means all three. Returned in that order. |
| `min_width`, `max_width` | number 5–12 | Optional, inclusive. They narrow decks only, so `parts` must include `Decks` (or be omitted). |
| `max_price` | number, more than 0 and up to 2000 | Optional. Only listings at or under this price. |
| `note` | string ≤ 80 | Optional. |

- **Simple mode** is just `{"kind": "digest"}`.
- **Events:**
  - `new`: a listing that first went on sale today;
  - `drop`: a sale price at least $2 or 5% under the previous scrape's price;
  - `low`: a listing that newly reached its lowest tracked price (at least 3 observations over 7 days).

  These follow the same rules as the owner's own daily digest.
- **Frequency and size:** at most **one digest email a day**, after the daily scrape, and only when something qualifies. It shows the best 30 listings (new lows first, then the biggest drops, then new listings by discount) and links to the site for the rest. When the subscriber's watches or searches also fire that day, everything arrives in **one email**.
- **One per subscriber.** A second digest rule is `one_digest_only`.

### `watch`: one product

| Field | Type | Rules |
| --- | --- | --- |
| `kind` | `"watch"` | required |
| `product_url` | string | Required. The listing URL exactly as the catalog has it (the card's link), on a tracked store: https, no fragment, at most 500 characters. |
| `label` | string ≤ 120 | Optional display text, normally the product name from the card. Never used for matching. |
| `max_price` | number, more than 0 and up to 2000 | Alert when the price goes under this. |
| `alert_on_drop` | boolean | Alert on a meaningful price drop ($2 or 5%). |
| `alert_on_low` | boolean | Alert on a verified historical low. |
| `alert_on_stock` | boolean | Alert when it comes back in stock (verified). |
| `note` | string ≤ 80 | Shown in the email. |

- **Simple mode:**
  - **Alert when below $X** is `{"kind": "watch", "product_url": ..., "max_price": X}`.
  - **Any meaningful price drop** is `{"kind": "watch", "product_url": ...}`. With no trigger, the Worker stores `alert_on_drop: true` and returns it.

  A watch never sends a "new match" email just for existing.
- **`product_key`** is added by the Worker in responses. Do not send it back (`unknown_field`). It names the product a watch follows:
  - **Shopify stores (CCS, Muir Skate):** the key is `shopify:<host>:<handle>`, so `/collections/<any>/products/<handle>` and `/products/<handle>` are one product. The watch follows the product when the store moves it between those URLs, and its price memory goes with it.
  - **Every other store:** the URL is the key. The rules are the same as `history_identity.py`'s. A retailer code, a variant path, or a similar name never joins two listings.
- **Cross-store:** a watch follows **one store's listing**. The same deck at another store is a different watch. The site's cross-store groups are name-based and can be wrong, so they never decide who gets an email. To watch two stores, add two watches.
- **Exact listings only.** Brand and name words are never used. Sending `brand`, `name`, `part`, or a width with `"kind": "watch"` is `not_for_kind`.
- **Duplicates:** the same product twice (even under two Shopify URLs) with the same triggers is `duplicate`.
- **Sizes:** a listing URL already pins the deck width the card showed. Sneaker sizes are not supported yet.
- **A listing that leaves the sale** sends nothing. If it returns, its watch picks up where it left off.

### `search`: words in the product name (the original v1 rule)

| Field | Type | Rules |
| --- | --- | --- |
| `kind` | `"search"` or omitted | Stored and returned without `kind`. |
| `brand` | string ≤ 60 | Every word must be in the product name. `brand` or `name` is required. |
| `name` | string ≤ 80 | One product, same word matching. |
| `part` | `"Decks"` \| `"Wheels"` \| `"Trucks"` \| `"Bearings"` | Default `"Decks"`. |
| `width` | number 5–12 | Decks only. An exact width; not combinable with `min_width`/`max_width`. |
| `min_width`, `max_width` | number 5–12 | Decks only, inclusive. `min_width` ≤ `max_width`. |
| `max_price` | number, more than 0 and up to 2000 | Alert when the price goes under this. |
| `alert_on_drop` | boolean | Alert on a meaningful price drop. |
| `alert_on_low` | boolean | Alert on a verified historical low. |
| `alert_on_stock` | boolean | Alert when it comes back in stock (verified). |
| `back_in_stock_width` | number 5–12 | Decks only. Back in stock in this width. |
| `note` | string ≤ 80 | Shown in the email. Plain text; `<` and `>` are rejected. |

- **Defaults:** a rule with none of the trigger fields alerts once when a listing first matches, then again on a meaningful drop or a verified restock. That's the same as `watchlist.yaml` with no triggers.
- **Matching is by words**, so it can match more than one product. That is intended here; for one exact product, use a `watch`.
- **Duplicates:** two rules that differ only in `note` are a duplicate.

### Validation errors

Errors use `fields` keyed `rules[<index>].<field>`:

| Code | Meaning |
| --- | --- |
| `unknown_field` | a field no kind has (including the response-only `id` and `product_key`) |
| `not_for_kind` | a field that belongs to a different kind, such as `brand` on a watch |
| `invalid` | `kind`, `part`, or a `parts`/`events` entry is not an allowed value |
| `brand_or_name_required` | a search rule without either |
| `required`, `invalid_url`, `store_not_tracked` | a watch's `product_url` |
| `must_be_text`, `too_long`, `invalid_characters` | text fields |
| `width_out_of_range`, `decks_only`, `below_min_width`, `width_or_range_not_both` | widths |
| `price_out_of_range` | `max_price` |
| `must_be_boolean` | flags |
| `must_be_list`, `at_least_one`, `duplicate`, `invalid` (on `parts`, `events`) | a digest's lists |
| `duplicate` | same as an earlier rule |
| `one_digest_only` | a second digest rule |
| `rules: must_be_list`, `at_least_one`, `too_many` | the list itself |

## Endpoints

### `GET /v1/health`

`200 {"ok": true, "api_version": "1", "mode": "mock" | "staging" | "production"}`. When the service is misconfigured it returns `503 {"ok": false, "problems": [setting names]}`. Every other endpoint then answers `503 {"error": "service_unavailable"}`. Show "Alerts are unavailable right now."

Call this from the page before showing the form. Responses carry CORS headers for the site origin, including the 503s, so the page can always read whether alerts are available. The same holds for the other public endpoints' 503 while the service is misconfigured. `OPTIONS /v1/health` answers a preflight. Other origins get no CORS grant. Neither does an origin that only matches a rejected `PUBLIC_ORIGIN` setting.

### `POST /v1/subscribe`

```json
{
  "email": "rider@example.com",
  "rules": [{ "brand": "Heroin", "part": "Decks", "min_width": 8.6, "max_price": 60, "note": "Wide Heroin decks" }],
  "consent": true,
  "consent_version": "2026-10",
  "turnstile_token": "<from the Turnstile widget>"
}
```

| Status | Body | Show |
| --- | --- | --- |
| 202 | `{"status": "check_email"}` | "Check your email to confirm." Same for new, pending, and already-subscribed addresses. An existing subscriber gets a manage link instead, and their rules are **not** changed. |
| 400 | `invalid_email`, `consent_required`, `consent_outdated`, `captcha_failed`, `invalid_rules` (+ `fields`) | The field error. Reset Turnstile after `captcha_failed`. |
| 403 | `staging_recipient_not_allowed` | Staging only. |
| 415 | `json_required` | (programming error) |
| 429 | `rate_limited` + `retry_after` | "Too many tries, try again later." |
| 503 | `signups_closed`, `email_unavailable` | "Signups are closed" / "Couldn't send the email, try again later." |

- `consent` must be `true` from a checkbox that **starts unchecked**.
- `consent_version` must match the server's `CONSENT_VERSION`. Send the version of the wording the person saw, and bump both together when the wording changes.

### `POST /v1/verify`

The page calls this with the token from `#verify=<token>`, then removes the fragment.

```json
{ "token": "<verify token>" }
```

- `200 {"status": "active", "manage_token": "<token>", "preferences": <Preferences>}`. The link is single use and expires after 48 hours.
- `400 {"error": "invalid_token"}`: expired, used, or unknown. Offer the "Email me a link" form.
- `503 {"error": "signups_closed"}`.

### `POST /v1/link`

```json
{ "email": "rider@example.com", "turnstile_token": "<token>" }
```

- Always `202 {"status": "check_email"}`. Only verified subscribers actually get an email, and that email carries `#manage=<token>`, valid for 30 days.
- Errors: `400 invalid_email` / `captcha_failed`, `429 rate_limited`.

### `GET /v1/preferences` and `PUT /v1/preferences`

Both need `Authorization: Bearer <manage_token>`. `PUT` replaces the whole list:

```json
{ "rules": [{ "brand": "Powell Peralta", "part": "Decks", "width": 9, "alert_on_drop": true }] }
```

Both return `200 <Preferences>`:

```json
{
  "status": "active",
  "email_masked": "r***@example.com",
  "consent_version": "2026-10",
  "verified_at": "2026-10-20T15:04:05.000Z",
  "max_rules": 10,
  "rules": [{ "id": "r_0123456789abcdef01234567", "alert_on_drop": true, "brand": "Powell Peralta", "part": "Decks", "width": 9 }]
}
```

- `401 {"error": "invalid_token"}`: expired or unknown. Offer "Email me a link".
- `400 invalid_rules` with `fields`, and `429 rate_limited`.

### `POST /v1/unsubscribe`

Unsubscribing deletes the subscriber's address, rules, tokens, and delivery records. Three forms are accepted:

- `Authorization: Bearer <manage_token>`, the page's "Unsubscribe" button;
- `{"token": "<unsubscribe token>"}`;
- `?token=<unsubscribe token>`, which is what the email's one-click header (RFC 8058) and its footer link use.

Answers:
- `200 {"status": "unsubscribed"}`.
- `400 invalid_token` for a forged token. An already-used real link also answers `200`.

`GET /v1/unsubscribe?token=...` shows a confirm page with a button. A plain GET never unsubscribes anyone, so link scanners can't.

### `DELETE /v1/subscriber`

Bearer manage token. `200 {"status": "deleted"}`. This removes the same data as unsubscribe.

## What the page should do

- **Main page Subscribe:** `{"kind": "digest"}`, with optional `parts`, `events`, deck widths, and `max_price` under Advanced. Also: email, an unchecked consent checkbox (with the consent text and a link to the privacy note), and the Turnstile widget.
- **Card Alert me:** `{"kind": "watch", "product_url": <the card's link>, "label": <its name>}` plus `max_price` ("below $X") or nothing ("any meaningful drop"). Advanced adds `alert_on_low` and `alert_on_stock`. Never substitute brand/name words for an exact product.
- **Search rules** (brand/name words, parts, deck widths) remain available for "anything matching" alerts.
- **States:** idle, submitting, "check your email", field errors, rate-limited, and unavailable.
- **An already-subscribed address** that submits Subscribe or Alert me again gets `202` and a manage link, and its rules are **not** changed. To add a watch or the digest, the page uses `PUT /v1/preferences` with the manage token, sending the whole list. Starring stays local and never subscribes anyone.
- **Manage page**:
  - reads `#verify=` or `#manage=`;
  - edits up to `max_rules` rules;
  - offers unsubscribe and delete;
  - offers "Email me a new link" whenever a token is rejected.
- **Accessibility:** every control is labeled, errors are announced with `aria-live`, phone inputs are 16px, and there are no popups.
- **The page holds no secret** and decides nothing about who gets mail; the Worker re-checks everything.

## Internal endpoints (not for the page)

The daily GitHub Actions job (`alerts_delivery.py`) calls the following. The page must never call them.

- `GET /v1/internal/routes`: verified subscribers' rules of every kind, by opaque route id, never with addresses.
- `POST /v1/internal/deliveries`: one entry per route. It carries `hits` (watch and search alerts, up to 25) and/or a `digest` section, and the Worker sends at most one email for it:

  ```json
  {"event_id": "<64 hex: one id per route and day>", "total": 41,
   "items": [{"kind": "drop", "price_before": "54.99", "item": {"name": "...", "store": "Zumiez", "part": "Decks", "url": "https://www.zumiez.com/...", "price_new": "44.99", "price_old": "79.95"}}]}
  ```

  - `items` holds 1–30 entries of kind `new`, `drop`, or `low`. A `drop` must carry `price_before`.
  - `total` is how many qualified, at least `items.length`.
  - Item links must go to tracked store hosts.
  - The Worker records `event_id` like any alert event, so a day's digest is emailed once even if the job runs again.
- `POST /v1/webhooks/resend`, called by Resend

Each request is signed with `HMAC_SECRET`:
- Headers: `X-SkateDeals-Timestamp`, `X-SkateDeals-Nonce`, `X-SkateDeals-Signature: v1=<hex>`.
- The signature is an HMAC-SHA256 over `v1\nMETHOD\nPATH?QUERY\nTIMESTAMP\nNONCE\nsha256hex(BODY)`.
- Each nonce works once, and timestamps older than 5 minutes are refused.

`docs/alerts-backend.md` describes the delivery flow.
