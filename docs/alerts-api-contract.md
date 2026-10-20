# Alerts API contract (UI side)

Status: assumed by the Alerts MVP page (`page.js`) while issue #58 is still open. No backend is implemented in this repository. The static page never includes a service secret.

The page talks to the Worker described in [notifications-architecture.md](notifications-architecture.md). Paths below are appended to a configurable base URL. Set the base to the origin plus an optional prefix (`https://alerts.example.com` or `https://alerts.example.com/v1`), not to a single endpoint.

## How the page chooses a mode

Configuration is read in this order:

1. `window.SKATEDEALS_ALERTS.apiBase` (or `baseUrl`)
2. `<meta name="skatedeals-alerts-api" content="https://...">`
3. The empty `ALERTS_API_BASE` constant in `page.js`

| Mode | When | What the page does |
| --- | --- | --- |
| Live | Base is `https://` (or `http://localhost` / `http://127.0.0.1` off GitHub Pages) | Calls the API. A rule is shown as Active only after a confirmed response. |
| Mock | `window.SKATEDEALS_ALERTS = { mock: true }` and the host is not `*.github.io` | In-memory preview. The panel says no email is sent. State dies on reload. |
| Coming soon | Anything else, including `mock: true` on `*.github.io` | Visible copy: "Email alerts coming soon." No subscribe request, no saved subscription. |

`window.SKATEDEALS_ALERTS.turnstileSiteKey` is optional and public. `consentVersion` defaults to `2026-10-20`. Usernames, passwords, query strings, and fragments in the base URL are ignored so a secret cannot be smuggled into the page config.

## Auth and the fragment

The static site is not trusted. It sends no cookies (`credentials: "omit"`).

- Verification links should use `#verify=<token>` (single-use).
- Manage links should use `#manage=<token>`.
- `#token=<token>` and `#token=<token>&purpose=verify|manage` are also accepted, matching the architecture note. `purpose` omitted tries verify, then treats the value as a manage token.
- Tokens are percent-encoded. They are never put in a query string. `POST /verify` may return `manage_token`. A `manage_link` / `manage_url` is used only when its token is in the fragment; a query-string token is discarded.
- After verify, the page replaces the fragment with `#manage=<manage token>`.
- `GET`, `PUT /preferences`, and `DELETE /subscriber` send `Authorization: Bearer <manage token>`.
- `POST /unsubscribe` sends that token in the JSON body and in the Authorization header.

## Rules

At most 10 rules. `note` is at most 80 characters. The client strips `status` before it sends a rule; the server assigns status.

| Field | Meaning |
| --- | --- |
| `rule_id` | Server id. Omitted on create. Send it back unchanged on edit. |
| `brand`, `name` | Word match, same as `watchlist.yaml`. Exact-product watches send `name` and `brand` when both are known. Brand watches send `brand` only. |
| `product_url` | Optional `https` URL for an exact product. Omitted for a brand watch. |
| `part` | `Decks`, `Trucks`, `Wheels`, `Bearings`, `Sneakers`, `Accessories`, `Completes`, or omitted for any type. |
| `size` | Deck width or US shoe size, as text. |
| `width` | Numeric inches when `part` is `Decks` and `size` is numeric. |
| `max_price` | Target price. A match is strictly under this amount. Omitted if the field is blank. |
| `alert_on_drop` | Meaningful drop: at least $2 or 5%. |
| `alert_on_low` | Qualified historical low (3 observations over 7 days). |
| `alert_on_stock` | Verified restock. |
| `back_in_stock_width` | Set with `alert_on_stock` when `width` is known. |
| `alert_on_new` | Newly listed. |
| `paused` | `true` to pause. Omit to leave the rule on. |
| `note` | Optional digest text. Not used for matching. |

`min_width` and `max_width` are accepted by `cleanRule` but the form does not edit them yet.

If none of the trigger flags are set, the page tells the person the daily default applies: newly listed, meaningful drop, or verified restock. The server still makes that decision.

The page shows **Active** only when the preferences payload has `status: "active"` for the subscriber and `status: "active"` on that rule, and the rule is not paused. A missing rule status stays **Pending verification**. **Paused** requires an active subscriber and `paused: true` or `status: "paused"`.

## Endpoints

JSON in and out. Unknown emails are not revealed by `/subscribe` or `/link`.

### `POST /subscribe`

```json
{
  "email": "person@example.com",
  "rules": [],
  "consent": true,
  "consent_version": "2026-10-20",
  "turnstile_token": ""
}
```

`202` every time the body is structurally acceptable (valid email shape, `consent: true`, rules valid), whether or not the address already exists:

```json
{
  "status": "accepted",
  "message": "If this address can receive mail, we sent a verification link. Alerts stay off until you confirm."
}
```

The page treats only `202` as accepted. Rules stay inactive until verify. `400` for a missing consent box, a malformed address, or invalid rules (`invalid_request` or `invalid_rules`). `429` `rate_limited`. `400` `turnstile_required` when the human check is required and the token is missing. `503` when the worker is misconfigured (fail closed).

### `POST /verify`

```json
{ "token": "<verify token from the fragment>" }
```

`200`:

```json
{
  "status": "active",
  "manage_token": "<manage token>",
  "email_masked": "p***@example.com"
}
```

`400` `invalid_token` when the token is unknown or already used. The page does not mark anything active on that response.

### `POST /link`

```json
{ "email": "person@example.com", "turnstile_token": "" }
```

`202` with the same body whether or not an account exists:

```json
{
  "status": "accepted",
  "message": "If an account exists for this address, we sent a new manage link."
}
```

### `GET /preferences` and `PUT /preferences`

Bearer manage token. `PUT` replaces the whole list, including pauses and deletions:

```json
{ "rules": [] }
```

`200`:

```json
{
  "status": "pending",
  "verified": false,
  "email_masked": "p***@example.com",
  "consent_version": "2026-10-20",
  "rules": [
    {
      "rule_id": "r_1",
      "brand": "Baker",
      "name": "Baker Figgy Deck 8.25",
      "part": "Decks",
      "size": "8.25",
      "width": 8.25,
      "max_price": 49.99,
      "alert_on_drop": true,
      "status": "pending"
    }
  ],
  "limits": { "max_rules": 10, "note_max": 80 }
}
```

`status` is `pending`, `active`, or `paused` on the subscriber (`paused` is not used for the subscriber; use `active` plus per-rule pause). Each rule's `status` is `pending`, `active`, or `paused`. `PUT` is allowed while verification is still pending; every rule in that response stays `pending`.

`401` `token_expired` with a message the page can show. The page then offers "email me a new link" and does not keep showing the old rules as active.

### `POST /unsubscribe`

```json
{ "token": "<manage token>" }
```

`200`:

```json
{
  "status": "unsubscribed",
  "message": "You are unsubscribed. We deleted your address and rules."
}
```

This is the button on the manage panel. The page expects the address and rules to be deleted, matching the architecture retention note. One-click unsubscribe from the digest can hit this same route without Turnstile.

### `DELETE /subscriber`

Bearer manage token. `200`:

```json
{
  "status": "deleted",
  "message": "Your address and rules were deleted."
}
```

The current panel uses `POST /unsubscribe` for the button. `DELETE` is part of the contract for a privacy deletion that also keeps a suppression hash.

## Errors the page understands

| HTTP | `error` | Page behavior |
| --- | --- | --- |
| 0 | `network` | "Could not be reached. Nothing was saved." |
| 0 | `unavailable` | Coming-soon state. No request was sent. |
| 400 | `invalid_request`, `invalid_rules`, `invalid_token`, `turnstile_required` | Show `message`. Do not mark active. |
| 401 | `token_expired` | Ask for a new manage link. |
| 429 | `rate_limited` | Ask them to wait. Nothing was changed. |
| 503 | `unavailable` | Fail closed. Nothing was saved. |

## Difference from issue #58

#58 does not ship an HTTP schema yet (no open PR). This document follows the endpoint list in `docs/notifications-architecture.md` and adds the fields the manage UI needs:

- Explicit `paused` and per-rule `status`, plus subscriber `status` / `verified` / `email_masked` / `limits`.
- `manage_token` on `POST /verify`, not only a link. Links are honored only when the token is in the fragment.
- `#verify=` and `#manage=` in addition to `#token=`.
- `alert_on_stock`, `alert_on_new`, `size`, and `product_url`, which phase 1 already describes, alongside `width` and `back_in_stock_width`.
- `PUT /preferences` while the subscriber is still `pending`.

If #58 picks different paths, return the base URL with the prefix included. If it omits `rule.status`, the page will keep showing Pending verification rather than guess Active.
