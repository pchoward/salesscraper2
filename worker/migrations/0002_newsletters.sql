-- Store newsletters for the promo strip (owner, 2026-11-27): emails that
-- stores we cannot scrape (Jenson USA, Dan's Comp, Competitive Cyclist) send
-- to the deals inbox. Only the text needed to read a code, percent and end
-- date is kept, for RETENTION.newsletterSeconds. No subscriber data.
CREATE TABLE newsletters (
  message_key TEXT PRIMARY KEY,           -- SHA-256 of the Message-ID (or of the raw mail)
  store TEXT NOT NULL,                    -- from the sender's verified domain, never from the mail text
  received_at INTEGER NOT NULL,
  subject TEXT NOT NULL,
  body TEXT NOT NULL                      -- plain text, at most MAX_TEXT characters
);
CREATE INDEX newsletters_received ON newsletters (received_at);
