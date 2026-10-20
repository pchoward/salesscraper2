// Retention, run daily by the Worker's cron trigger. See
// docs/alerts-backend.md for the policy.

export const RETENTION = {
  pendingSubscriberSeconds: 7 * 86400,
  usedTokenSeconds: 86400,
  deliverySeconds: 90 * 86400,
  rateLimitSeconds: 2 * 86400,
  outboxSeconds: 7 * 86400,
};

export async function runMaintenance(db, now = Math.floor(Date.now() / 1000)) {
  const statements = [
    ["pending", "DELETE FROM subscribers WHERE status = 'pending' AND created_at < ?", now - RETENTION.pendingSubscriberSeconds],
    ["tokens", "DELETE FROM tokens WHERE expires_at < ? OR (used_at IS NOT NULL AND used_at < ?)", now, now - RETENTION.usedTokenSeconds],
    ["deliveries", "DELETE FROM deliveries WHERE created_at < ? AND status = 'sent'", now - RETENTION.deliverySeconds],
    ["rate_limits", "DELETE FROM rate_limits WHERE window_start < ?", now - RETENTION.rateLimitSeconds],
    ["nonces", "DELETE FROM nonces WHERE expires_at < ?", now],
    ["outbox", "DELETE FROM outbox WHERE created_at < ?", now - RETENTION.outboxSeconds],
  ];
  const removed = {};
  for (const [name, sql, ...params] of statements) {
    const result = await db.prepare(sql).bind(...params).run();
    removed[name] = result.meta ? result.meta.changes : 0;
  }
  return removed;
}
