-- SkateDeals alerts: initial schema. Apply with
--   wrangler d1 migrations apply skatedeals-alerts --remote
-- Times are Unix seconds (UTC). No table stores a plaintext token, and no
-- table except subscribers stores an email address.

PRAGMA foreign_keys = ON;

-- One row per person. A row exists only while the person is pending or
-- subscribed: unsubscribing or deleting removes it (and, by cascade, the
-- rules, tokens, and deliveries below).
CREATE TABLE subscribers (
  id TEXT PRIMARY KEY,                    -- random, internal only
  route_id TEXT NOT NULL UNIQUE,          -- opaque alias sent to GitHub Actions
  email TEXT NOT NULL,                    -- needed to send; never leaves the Worker
  email_hash TEXT NOT NULL UNIQUE,        -- HMAC(pepper, normalized email)
  status TEXT NOT NULL CHECK (status IN ('pending', 'active')),
  consent_version TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  verified_at INTEGER,
  updated_at INTEGER NOT NULL
);
CREATE INDEX subscribers_status ON subscribers (status, created_at);

CREATE TABLE rules (
  id TEXT PRIMARY KEY,
  subscriber_id TEXT NOT NULL REFERENCES subscribers (id) ON DELETE CASCADE,
  position INTEGER NOT NULL,
  fields TEXT NOT NULL,                   -- validated JSON, schema v1
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);
CREATE INDEX rules_subscriber ON rules (subscriber_id, position);

-- Verify and manage tokens, stored as HMAC(pepper, token). Unsubscribe
-- tokens are derived (see src/crypto.js) and not stored.
CREATE TABLE tokens (
  token_hash TEXT PRIMARY KEY,
  subscriber_id TEXT NOT NULL REFERENCES subscribers (id) ON DELETE CASCADE,
  purpose TEXT NOT NULL CHECK (purpose IN ('verify', 'manage')),
  expires_at INTEGER NOT NULL,
  used_at INTEGER
);
CREATE INDEX tokens_expiry ON tokens (expires_at);

-- One row per (subscriber, engine event). The primary key is what makes a
-- retried or repeated delivery request send nothing twice.
CREATE TABLE deliveries (
  subscriber_id TEXT NOT NULL REFERENCES subscribers (id) ON DELETE CASCADE,
  event_id TEXT NOT NULL,
  delivery_id TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('sending', 'sent', 'uncertain')),
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  PRIMARY KEY (subscriber_id, event_id)
);
CREATE INDEX deliveries_age ON deliveries (created_at);

-- Addresses that bounced or complained. Only the hash is kept, so a new
-- signup for the same address can be refused without storing it.
CREATE TABLE suppressions (
  email_hash TEXT PRIMARY KEY,
  reason TEXT NOT NULL CHECK (reason IN ('bounce', 'complaint')),
  created_at INTEGER NOT NULL
);

-- Fixed-window counters. Buckets are hashes, never raw IPs or addresses.
CREATE TABLE rate_limits (
  bucket TEXT PRIMARY KEY,
  count INTEGER NOT NULL,
  window_start INTEGER NOT NULL
);

-- Nonces seen on signed internal requests, kept until they could no longer
-- pass the timestamp check.
CREATE TABLE nonces (
  nonce TEXT PRIMARY KEY,
  expires_at INTEGER NOT NULL
);

-- Mock mode only: messages that would have been sent. Never written in
-- staging or production.
CREATE TABLE outbox (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  to_addr TEXT NOT NULL,
  subject TEXT NOT NULL,
  text_body TEXT NOT NULL,
  html_body TEXT NOT NULL,
  headers TEXT NOT NULL,
  created_at INTEGER NOT NULL
);
