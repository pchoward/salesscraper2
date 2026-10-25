# Personal notification trial (phase 1)

The default stays unchanged: with `NOTIFICATION_ENGINE_ENABLED` absent/off, the existing SMTP digest and `watchlist.yaml` behavior continue. The opt-in engine uses the same renderer and SMTP configuration and adds stateful watch events to the existing digest, rather than sending a separate message for each watch. It does not introduce accounts, a database, a provider, signup, forms, or push notifications. No UI or scraping rules change.

## Rules and qualification

Existing `brand`, `name`, `part`, `width`, `min_width`, `max_width`, `max_price`, `alert_on_drop`, `alert_on_low`, and `back_in_stock_width` fields remain accepted. The engine also accepts:

- `product_url` (or `url`) for a normalized exact product identity instead of a brand/name selector.
- `size` for an exact deck width or a numeric US sneaker size. Sneaker size watches require reliable available-size data; missing size data is not evidence of availability.
- `alert_on_stock: true` for a verified out-of-stock → in-stock transition.
- `owner_id` and `recipient_id`: separate opaque, non-personal aliases containing only letters, numbers, `_`, or `-`. Defaults are `personal` and `primary`. Never use an address or person's name as an alias.

Example rule (no recipient address in the file):

```yaml
rules:
  - id: personal-baker-85
    owner_id: personal
    recipient_id: primary
    brand: Baker
    part: Decks
    width: 8.5
    max_price: 50
    alert_on_drop: true
    alert_on_low: true
```

Selectors combine (brand/name/product identity, category, and size). Trigger fields combine as alternatives, preserving the existing watchlist pattern. As with the current watchlist, `max_price: 50` means **strictly under $50**, not $50 exactly. The stateful engine interprets `alert_on_drop` as the shared meaningful-drop rule: at least $2 or 5%, rather than the legacy engine's any-price-dip behavior. A verified low uses the existing observation-count/span requirements in `history.all_time_low_status`; history calculations are unchanged. No per-size historical-low claim is made for sneakers, because the existing history is listing-level.

A rule without trigger fields alerts once when a product first matches that watch, on meaningful subsequent price drops, or on a verified stock return. Registering a new watch can therefore include already-listed matching products in the first digest. A changed selector/trigger/ID is a new watch identity; changing only its note is not. Identical duplicate rules are deduplicated. Removing a rule cancels its pending events and removes its condition memory for the selected route; re-adding it starts a new registration.

Threshold/low conditions alert when they become true, then remain quiet while true. A new lower verified low or another meaningful drop is a new event. A definite above-threshold price or verified negative stock can re-arm a watch. Failed/suspect categories and first-miss carried rows freeze observation state and cannot generate or deliver watch events. Missing/reappearing listings alone never establish stock status. Existing reliable `shoe_sizes` and explicit `stock: in_stock/out_of_stock` evidence are supported; deck stock returns remain quiet unless reliable positive evidence is available. Known out-of-stock evidence is captured before the existing miss handler clears it.

For phase 1 only the route selected by `NOTIFICATION_OWNER_ID` / `NOTIFICATION_RECIPIENT_ID` is delivered through the configured `EMAIL_TO`. Other route aliases are skipped, never silently redirected. Selected watch alerts replace the outgoing watch block, so another route's quiet-watch notes are not exposed. Ordinary public deal/digest sections retain their existing behavior. Future multi-user delivery still needs a separate authorized address mapping, storage/access controls, and orchestration; aliases are not user accounts.

## First personal trial

1. Use your existing `watchlist.yaml`, or set `WATCHLIST_PATH` to a private local rules file. Keep addresses, credentials, and sensitive notes out of tracked files.
2. Preview locally, with no scrape or send:

   ```bash
   python -m notification_engine --preview
   ```

   This reads the saved catalog/history/health and writes ignored `email_preview.html` only when events qualify. It never sends, acknowledges events, or writes event state. An existing state file is read without modification; missing state is simulated for the preview. Keep the preview private because it can contain configured recipients. `python scraper.py --email-dry-run` also previews the engine when enabled, but runs the usual scrape first.
3. For a local live trial, initialize an ignored checkpoint once:

   ```bash
   python -m notification_engine --initialize
   ```

   It refuses to overwrite an existing checkpoint. Use the existing environment/secret pattern for `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_FROM`, `EMAIL_TO`, `SMTP_SECURITY`, and `REPORT_URL`. Do not paste secret values into chat or command history. The engine adds no new credential requirement. Set `NOTIFICATION_ENGINE_ENABLED=1` only when ready for the normal scraper to send.
4. For GitHub Actions, put credentials/addresses in **repository Actions secrets** as before. Set repository variable `NOTIFICATION_ENGINE_ENABLED=1`. Optional alias variables `NOTIFICATION_OWNER_ID=personal` and `NOTIFICATION_RECIPIENT_ID=primary` must match the rules; blank values use these defaults. For the first checkpoint only, set variable `NOTIFICATION_ALLOW_BOOTSTRAP=1`, run **Scraper - Run Full Scrape**, verify the checkpoint-save step succeeded, then remove/reset that bootstrap variable **before subsequent runs**. A missing checkpoint thereafter fails closed; do not leave bootstrap enabled because cache loss could otherwise restart registrations and resend initial qualifications. Dry-run does not create a checkpoint.
5. Review the first digest and Actions logs. No live email was sent while developing or testing this feature. This PR does not enable the feature or modify your secrets/settings.

Changing the real recipient behind an alias does not reset delivered-event memory. Use a new non-personal recipient alias and update the rules if intentionally starting a trial for a different recipient. Multiple `EMAIL_TO` addresses are treated as one explicitly configured delivery group; phase 1 does not route individual addresses from rules.

## State and persistence

`notification_state.json` and its empty local lock file are gitignored. `NOTIFICATION_STATE_PATH` can select another private writable location for local runs. The administration CLI uses `--state PATH`. Local state writes are atomic, fsynced, and created with private permissions; an exclusive lock serializes local reruns.

The versioned checkpoint stores only hashed owner/recipient/rule/product identities, retailer/category, condition flags, event sequence, numeric prices, dates, and delivery status. No addresses, credentials, product URLs, names, rule notes, or rendered email bodies are retained. These hashes are pseudonymous identifiers, not a claim of anonymization. Unexpected schema fields, unsupported versions, corrupt files, and oversized state fail closed instead of resetting history.

Observation memory is bounded at 4,096 watch/product identities. Active condition memory is not evicted simply because it is old, preventing an unchanged low price from alerting again after retention expiry. New identities are skipped with a warning at capacity. Each email includes at most 25 watch/product groups, oldest pending first; remaining qualifying events stay queued for later healthy runs. Ordinary digest sections keep their existing behavior. Event history is bounded at 1,024 records; pending/delivered events expire after 30 days (stale pending events are logged and discarded). Ambiguous events are held until explicitly resolved and can consume capacity; a full event journal skips new events rather than deleting unresolved deliveries. Expired delivery history does not erase active qualification memory. Removing unused rules frees their selected-route records. This is intentionally bounded personal-trial storage, not a backend.

The daily Actions workflow restores the latest branch-scoped checkpoint using `actions/cache/restore@v4` and saves a new immutable key containing run ID and run attempt with `actions/cache/save@v4`. Cache saves run even after a scraper-step error when a checkpoint exists. Workflow-level concurrency serializes runs on a branch. The state is never `git add`ed or included in the static site. GitHub caches are **not a secret vault** and may be readable by permitted collaborators or fork/PR workflows under GitHub's cache access rules, hence the minimal hashed schema and absence of personal data. Cache availability/retention is not guaranteed; an evicted/missing checkpoint stops engine delivery unless explicitly initialized again.

## Delivery outcomes, retries, and rollback

Before SMTP, the engine checkpoints selected events as `sending`. SMTP acceptance marks them `delivered` (acceptance is not proof of inbox receipt). Known pre-acceptance rejections such as authentication/recipient/sender/DATA rejection remain `pending` for a later healthy scrape. Missing SMTP settings also keep pending events. A pending event is delivered only while its qualification is still valid; retries use the current product details, not a stored email body. Back-in-stock retries require current reliable positive evidence. Events for failed/suspect categories are held. Price-increased or no-longer-qualifying pending events are canceled rather than sending stale claims.

Timeouts, disconnects, partial recipient acceptance, unexpected exceptions, or a restart with `sending` are **uncertain**. They block automatic retries for that watch/product, including new events, until reviewed. Stable per-batch Message-ID headers aid investigation but do not guarantee mailbox deduplication. Successful dry-run previews never acknowledge events. SMTP or checkpoint failures are logged without aborting the scraper; a failed pre-send checkpoint prevents sending.

There is **no exactly-once guarantee across SMTP and GitHub cache storage**. A hard runner loss or cache-save failure after SMTP acceptance can lose the newest acknowledgement while an older checkpoint still exists. A later restore can then duplicate an accepted event. Workflow concurrency, a local two-phase journal, always-save steps, and fail-closed missing-state behavior reduce this window but cannot make SMTP and cache updates transactional. Reliable end-to-end idempotency would require a durable delivery service/store, deliberately outside phase 1. The retry journal covers watch events, not replay of the entire legacy deal digest; ordinary deal/warning sections keep their existing delivery behavior.

Local inspection/resolution, always without sending:

```bash
python -m notification_engine --status
python -m notification_engine --resolve EVENT_ID --outcome delivered
# Only after verifying that SMTP did NOT accept it:
python -m notification_engine --resolve EVENT_ID --outcome retry
```

Status prints counts and held/pending event hashes, never recipients or product details. Resolution requires an existing pending or ambiguous event. `delivered` acknowledges it; `retry` queues an ambiguous event for a subsequent qualifying healthy run. Pending events are already retryable and may only be explicitly acknowledged here. Either action clears the watch's hold only when no ambiguous events remain for that watch. A retry after an actually accepted message can duplicate it. For an Actions-held event, inspect the latest checkpoint and mail/provider logs privately. Then use the **Run workflow** inputs `notification_event_id` and `notification_resolution` (`delivered` or `retry`). The workflow resolves the local restored checkpoint before scraping/sending and persists it under the new run's cache key. For example, after verification:

```bash
gh workflow run scrape.yml --ref main -f notification_event_id=EVENT_HASH -f notification_resolution=delivered
```

The optional `notification_checkpoint_key` input restores an exact reviewed cache key rather than the latest prefix match. Find keys under Actions caches (`gh cache list`); a nonexistent explicit key fails the workflow before sending, even if bootstrap was left enabled. Use it only for deliberate recovery after reconciling acknowledgements, not to replay old event state casually. Values are cache/event hashes, never addresses or credentials. You can combine the checkpoint key and a resolution when repairing a reviewed older checkpoint. A selected recovery run still performs the normal scrape and may send qualifying pending events; choosing `retry` is explicit authorization to retry on that run. Leave all three inputs blank/default for ordinary manual scrapes. The local CLI never updates remote caches automatically.

To roll back code, set `NOTIFICATION_ENGINE_ENABLED=0` first; the legacy digest resumes. Preserve the latest checkpoint and do not remove it or turn bootstrap on to “fix” a delivery problem. Re-enable only with that checkpoint restored. Restoring an older cache/revision can discard acknowledgements and cause repeats; verify intervening deliveries and hold/resolve affected events before using a stale checkpoint. Corrupt state should be replaced only with a reviewed known-good checkpoint, not silently emptied. Remove obsolete caches under GitHub's cache controls only after deciding how outstanding deliveries should be handled.

Tests use synthetic fixtures and mocked SMTP only. Run `python -m unittest test_notification_engine test_notify test_watchlist test_pipeline` or the repository's full unittest discovery command.
