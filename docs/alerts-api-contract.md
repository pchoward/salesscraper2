# Alerts API contract

The page uses the alerts API **v1** implemented on branch `claude/alerts-backend` (PR #60). That branch's `docs/alerts-api.md` and `worker/contract/examples.json` are the contract. This file only records how the static page behaves. It does not define a second set of endpoints.

`tests/fixtures/alerts-api-examples.json` is a snapshot of `worker/contract/examples.json` from `c12cc104fe22de764c702061d3b597ce885a29d5` so the UI tests can run without that branch checked out. If the snapshot and PR #60 disagree, PR #60 wins and the snapshot should be updated.

## Page configuration

Read in this order:

1. `window.SKATEDEALS_ALERTS.apiBase` (or `baseUrl`)
2. `<meta name="skatedeals-alerts-api" content="https://...">`
3. The empty `ALERTS_API_BASE` constant in `page.js`

`https://` bases are accepted. `http://` is accepted only for `localhost` or `127.0.0.1`, and never on `*.github.io`. A base with a username, password, query, or fragment is ignored.

| Situation | What the page does |
| --- | --- |
| Allowed base URL | Calls `/v1/...` on that origin. `credentials: "omit"`. |
| No allowed base, including `mock: true` | Visible copy: "Email alerts coming soon." No request is sent. |
| `mock: true` on `*.github.io` | Ignored. Coming soon, unless a separate allowed base URL is set. |

There is no in-page subscription store. `window.SKATEDEALS_ALERTS.turnstileSiteKey` is optional and public. `consentVersion` defaults to `2026-10`, which is the mock server's `CONSENT_VERSION` and the version in the examples. The health response does not include the consent version.

## What the page sends

`GET /v1/health` runs before signup. When `mode` is `mock`, the page sends the documented public token `mock-turnstile-pass` and says that no email is sent. In any other mode it uses the Turnstile widget only if a site key is configured. It never invents a passing token.

Signup is `POST /v1/subscribe`. A manage link is `POST /v1/link`. Verify is `POST /v1/verify` with the `#verify=` fragment. Preferences are `GET` and `PUT /v1/preferences` with `Authorization: Bearer`. Unsubscribe is `POST /v1/unsubscribe` with that header and no body. Delete is `DELETE /v1/subscriber`. The page does not call `/v1/internal/*`, `/v1/webhooks/resend`, or `/v1/mock/outbox`.

A 202 `{"status":"check_email"}` is not an active alert. The page shows "Check your email to confirm." An already-active address gets that same response and the new rules are not saved; the page says so. Active is shown only after a response whose subscriber `status` is `active` (`POST /v1/verify` or `GET`/`PUT /v1/preferences`).

`PUT /v1/preferences` replaces the whole list. Response `id` values are not sent back (`unknown_field`). The last rule is not removed with an empty list; the page asks the person to unsubscribe. Adding stops at `max_rules` from the preferences payload (10 in the examples).

Rule fields the form can send: `brand`, `name`, `part` (`Decks`, `Wheels`, `Trucks`, `Bearings`), deck `width`, `max_price`, `alert_on_drop`, `alert_on_low`, `alert_on_stock`, `back_in_stock_width` (with a deck width and restock), and `note`. Numbers are JSON numbers. False flags are omitted. Part is required because an omitted part becomes Decks on the server.

## Tokens

Email links use `#verify=` and `#manage=`. The page reads the fragment and removes it with `history.replaceState`. It does not write the manage token back into the URL. The token is kept in memory and in `sessionStorage` under `skatedeals.alerts.manage`. It is never put in `localStorage`. A token in the query string is ignored.

## Errors

The page reads `{"error":"<code>"}`, optional `fields`, and `retry_after` (or the `Retry-After` header). A 503, or health `{"ok":false}`, is shown as "Alerts are unavailable right now."

## Health and CORS (fixed in PR #60)

`GET /v1/health` used to return before the worker added CORS headers, so a page on another origin could not read `mode`. PR #60 now sends `Access-Control-Allow-Origin` on health, for the site origin, and for `localhost`/`127.0.0.1` in mock mode only. It does so on the fail-closed 503s too, so the page can read `mode`. A browser on another origin can now tell it is talking to the mock, and can see "unavailable" as a real 503. That was checked in Chromium against the mock server. The page logic above did not need to change. It still sends `mock-turnstile-pass` only when a readable health body says `mode` is `mock`, and it does not treat a network failure as the documented 503.

## Not in the API, so not in the UI

Pause, per-rule pending/active/paused badges, `alert_on_new`, `product_url`, `size`, and the catalog parts Sneakers, Accessories, and Completes. A card with one of those parts makes the person pick Decks, Wheels, Trucks, or Bearings before submit. Stars stay in local storage and never subscribe.
