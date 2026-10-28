// Outgoing mail: Resend in staging and production, the outbox table in mock
// mode. Every message is rendered here from validated data, and every
// dynamic value is escaped.

export const STORE_HOSTS = new Set([
  "www.zumiez.com",
  "www.skatewarehouse.com",
  "shop.ccs.com",
  "www.tactics.com",
  "tgmskateboards.com",
  "www.tgmskateboards.com",
  "www.deathgearproducts.com",
  "deathgearproducts.com",
  "kineticskateboarding.com",
  "www.kineticskateboarding.com",
  "skateparkoftampa.com",
  "www.skateparkoftampa.com",
  "exodusrideshop.com",
  "www.exodusrideshop.com",
  "socalskateshop.com",
  "www.socalskateshop.com",
  "www.skatedeluxe.com",
  "muirskate.com",
  "www.muirskate.com",
]);

export function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function footer(links) {
  return {
    text: [
      "",
      "You get this because you subscribed to SkateDeals alerts and confirmed your email.",
      `Manage your alerts: ${links.manage}`,
      `Unsubscribe: ${links.unsubscribe}`,
    ].join("\n"),
    html: `<p style="color:#64748b;font-size:12px;margin-top:24px">You get this because you subscribed to SkateDeals alerts and confirmed your email.<br>
<a href="${escapeHtml(links.manage)}">Manage your alerts</a> · <a href="${escapeHtml(links.unsubscribe)}">Unsubscribe</a></p>`,
  };
}

function wrap(title, bodyHtml) {
  return `<!doctype html><html><body style="font-family:Arial,Helvetica,sans-serif;color:#0f172a;max-width:600px;margin:0 auto;padding:16px">
<h1 style="font-size:20px">${escapeHtml(title)}</h1>${bodyHtml}</body></html>`;
}

export function verificationEmail(links) {
  const subject = "Confirm your SkateDeals alerts";
  const text = [
    "Someone (hopefully you) asked to get SkateDeals deal alerts at this address.",
    "",
    `Confirm: ${links.verify}`,
    "",
    "The link works for 48 hours. If you did not ask for this, ignore this email; nothing will be sent.",
  ].join("\n");
  const html = wrap(
    subject,
    `<p>Someone (hopefully you) asked to get SkateDeals deal alerts at this address.</p>
<p><a href="${escapeHtml(links.verify)}" style="background:#1d4ed8;color:#fff;padding:10px 16px;border-radius:6px;text-decoration:none;display:inline-block">Confirm alerts</a></p>
<p style="color:#64748b">The link works for 48 hours. If you did not ask for this, ignore this email; nothing will be sent.</p>`,
  );
  return { subject, text, html };
}

export function manageLinkEmail(links) {
  const subject = "Your SkateDeals alerts link";
  const text = [
    "Here is a link to see or change your SkateDeals alerts.",
    "",
    `Manage: ${links.manage}`,
    "",
    "The link works for 30 days. If you did not ask for it, you can ignore this email.",
  ].join("\n");
  const html = wrap(
    subject,
    `<p>Here is a link to see or change your SkateDeals alerts.</p>
<p><a href="${escapeHtml(links.manage)}" style="background:#1d4ed8;color:#fff;padding:10px 16px;border-radius:6px;text-decoration:none;display:inline-block">Manage alerts</a></p>
<p style="color:#64748b">The link works for 30 days. If you did not ask for it, you can ignore this email.</p>`,
  );
  return { subject, text, html };
}

function money(value) {
  const number = Number(value);
  return Number.isFinite(number) ? `$${number.toFixed(2)}` : "";
}

const DIGEST_LABELS = { drop: "Price drop", low: "Lowest price we've tracked", new: "New on sale" };

function itemRow(item, why, was) {
  const price = money(item.price_new);
  return {
    text: [`${item.name} at ${item.store}: ${price}${was}`, `  ${why}`, `  ${item.url}`, ""],
    html: `<tr><td style="padding:10px 0;border-bottom:1px solid #e2e8f0">
<a href="${escapeHtml(item.url)}" style="color:#1d4ed8;font-weight:bold">${escapeHtml(item.name)}</a><br>
<span>${escapeHtml(item.store)} · <strong>${escapeHtml(price)}</strong>${escapeHtml(was)}</span><br>
<span style="color:#475569">${escapeHtml(why)}</span></td></tr>`,
  };
}

function section(title, rows) {
  return {
    text: [title, "", ...rows.flatMap((row) => row.text)],
    html: `<h2 style="font-size:16px;margin:20px 0 4px">${escapeHtml(title)}</h2><table style="width:100%;border-collapse:collapse">${rows
      .map((row) => row.html)
      .join("")}</table>`,
  };
}

/**
 * One email per delivery: the person's own alerts first, then the general
 * digest (if they have one and it is due). Either part may be empty.
 */
export function digestEmail(hits, links, digest = null) {
  const parts = [];
  if (hits.length) {
    const rows = hits.map((hit) => {
      const was = hit.item.price_old ? ` (was ${money(hit.item.price_old)})` : "";
      return itemRow(hit.item, `${hit.reasons.join(", ")}${hit.note ? ` · ${hit.note}` : ""}`, was);
    });
    parts.push(section("Your SkateDeals alerts matched", rows));
  }
  if (digest) {
    const rows = digest.items.map((entry) => {
      const before = entry.price_before || entry.item.price_old;
      return itemRow(entry.item, DIGEST_LABELS[entry.kind], before ? ` (was ${money(before)})` : "");
    });
    const more = digest.total - digest.items.length;
    const done = section("Today's deals", rows);
    if (more > 0) {
      done.text.push(`${more} more today: ${links.site}`, "");
      done.html += `<p><a href="${escapeHtml(links.site)}">See ${more} more on SkateDeals</a></p>`;
    }
    parts.push(done);
  }
  const plural = (count, word) => `${count} ${word}${count === 1 ? "" : "s"}`;
  let subject;
  if (hits.length && digest) subject = `SkateDeals: ${plural(hits.length, "alert")} and ${plural(digest.total, "deal")} today`;
  else if (digest) subject = `SkateDeals daily deals: ${digest.total} today`;
  else subject = hits.length === 1 ? `SkateDeals alert: ${hits[0].item.name}`.slice(0, 120) : `SkateDeals alerts: ${hits.length} matches`;
  const end = footer(links);
  return {
    subject,
    text: `${parts.map((part) => part.text.join("\n")).join("\n")}${end.text}`,
    html: wrap(hits.length ? "Your SkateDeals alerts" : "Today's SkateDeals deals", parts.map((part) => part.html).join("") + end.html),
  };
}

/**
 * Sends one message. Returns "sent", "failed" (definitely not accepted, safe
 * to retry), or "uncertain" (may have been accepted; do not retry blindly).
 */
export async function sendEmail(env, settings, message, fetcher = fetch) {
  const headers = message.headers || {};
  if (settings.mode === "mock") {
    await env.DB.prepare(
      "INSERT INTO outbox (to_addr, subject, text_body, html_body, headers, created_at) VALUES (?, ?, ?, ?, ?, ?)",
    )
      .bind(message.to, message.subject, message.text, message.html, JSON.stringify(headers), Math.floor(Date.now() / 1000))
      .run();
    return "sent";
  }
  if (settings.mode === "staging" && !settings.stagingAllowed.includes(String(message.to).toLowerCase())) {
    return "failed";
  }
  let response;
  try {
    response = await fetcher("https://api.resend.com/emails", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${settings.resendApiKey}`,
        "Content-Type": "application/json",
        ...(message.idempotencyKey ? { "Idempotency-Key": message.idempotencyKey } : {}),
      },
      body: JSON.stringify({
        from: settings.from,
        to: [message.to],
        subject: message.subject,
        text: message.text,
        html: message.html,
        headers,
      }),
    });
  } catch {
    return "uncertain";
  }
  if (response.ok) return "sent";
  if (response.status === 429 || (response.status >= 400 && response.status < 500)) return "failed";
  return "uncertain";
}
