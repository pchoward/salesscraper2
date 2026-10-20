# Alerts API v1 (contract for the UI)

This is the contract between a future SkateDeals alerts page and the alerts Worker (`worker/`). It is checked by tests: `worker/contract/examples.json` is one complete session, and `worker/test/contract.test.js` replays it against the Worker and requires the exact status codes and bodies shown there. If this page and that file ever disagree, the file is right; please report the difference.

**Status:** backend only. Nothing is deployed, and no page uses this yet. Stars and browser-only settings never send email; only a subscription confirmed by email does.

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

## Rule object (schema v1)

| Field | Type | Rules |
| --- | --- | --- |
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
- **Limits:** at most `max_rules` per subscriber (10 by default). Two rules that differ only in `note` are a duplicate.
- **Responses** add `"id"` (`r_` + 24 hex characters) and return keys sorted. Editing only `note` keeps the id.

Validation errors use `fields` keyed `rules[<index>].<field>`:

| Code | Meaning |
| --- | --- |
| `unknown_field` | a field not in the table |
| `invalid` | `part` is not one of the four |
| `brand_or_name_required` | neither was given |
| `must_be_text`, `too_long`, `invalid_characters` | text fields |
| `width_out_of_range`, `decks_only`, `below_min_width`, `width_or_range_not_both` | widths |
| `price_out_of_range` | `max_price` |
| `must_be_boolean` | flags |
| `duplicate` | same as an earlier rule |
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

- **Subscribe form:**
  - email;
  - one or more rules, built from the parts and deck widths the filters already offer;
  - trigger checkboxes;
  - an optional note;
  - an unchecked consent checkbox, with the consent text and a link to the privacy note;
  - the Turnstile widget.
- **States:** idle, submitting, "check your email", field errors, rate-limited, and unavailable.
- **"Alert me" from a card** may prefill `part`, `brand` or `name`, and `width`, with `max_price` set to the current price. Starring stays local and never subscribes anyone.
- **Manage page**:
  - reads `#verify=` or `#manage=`;
  - edits up to `max_rules` rules;
  - offers unsubscribe and delete;
  - offers "Email me a new link" whenever a token is rejected.
- **Accessibility:** every control is labeled, errors are announced with `aria-live`, phone inputs are 16px, and there are no popups.
- **The page holds no secret** and decides nothing about who gets mail; the Worker re-checks everything.

## Internal endpoints (not for the page)

The daily GitHub Actions job (`alerts_delivery.py`) calls the following. The page must never call them.

- `GET /v1/internal/routes`
- `POST /v1/internal/deliveries`
- `POST /v1/webhooks/resend`, called by Resend

Each request is signed with `HMAC_SECRET`:
- Headers: `X-SkateDeals-Timestamp`, `X-SkateDeals-Nonce`, `X-SkateDeals-Signature: v1=<hex>`.
- The signature is an HMAC-SHA256 over `v1\nMETHOD\nPATH?QUERY\nTIMESTAMP\nNONCE\nsha256hex(BODY)`.
- Each nonce works once, and timestamps older than 5 minutes are refused.

`docs/alerts-backend.md` describes the delivery flow.
