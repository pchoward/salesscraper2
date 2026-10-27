// Subscriber rule schema v1. Three kinds, checked here and again in
// alerts_delivery.py before the Python engine sees them:
//
//   search  (default; no "kind" stored) brand/name words, part, deck widths.
//           The original v1 rule, unchanged.
//   watch   one store listing, identified by its URL (see productKey).
//   digest  the general daily deals email: no product, optional filters.

import { sha256Hex } from "./crypto.js";
import { STORE_HOSTS } from "./email.js";

export const PARTS = ["Decks", "Wheels", "Trucks", "Bearings"];
// Every part the site lists (page.py PART_ORDER). Digest filters only.
export const CATALOG_PARTS = ["Decks", "Trucks", "Wheels", "Bearings", "Sneakers", "Accessories", "Completes", "Protection"];
export const KINDS = ["search", "watch", "digest"];
export const DIGEST_EVENTS = ["new", "drop", "low"];
// The same hosts as history_identity.SHOPIFY_HOSTS: Shopify keeps a product
// handle unique per shop, so collection paths and /products/ are one product.
const SHOPIFY_HOSTS = new Set(["shop.ccs.com", "tgmskateboards.com", "www.tgmskateboards.com", "muirskate.com", "www.muirskate.com"]);
const SHOPIFY_HANDLE = /\/products\/([^/?#]+)\/?$/;
const MAX_URL = 500;

const TEXT_LIMITS = { brand: 60, name: 80, note: 80, label: 120 };
const WIDTH_FIELDS = ["width", "min_width", "max_width", "back_in_stock_width"];
const FLAG_FIELDS = ["alert_on_drop", "alert_on_low", "alert_on_stock"];
const FIELDS = {
  search: new Set(["kind", "part", "brand", "name", "note", ...WIDTH_FIELDS, "max_price", ...FLAG_FIELDS]),
  watch: new Set(["kind", "product_url", "label", "note", "max_price", ...FLAG_FIELDS]),
  digest: new Set(["kind", "parts", "events", "min_width", "max_width", "max_price", "note"]),
};
// Fields some kind accepts. Sent with the wrong kind they get "not_for_kind",
// so the page can tell a kind mix-up from a typo ("unknown_field").
const KNOWN = new Set(Object.values(FIELDS).flatMap((set) => [...set]));
// Display-only fields: editing them keeps a rule's id and never makes a duplicate.
const DISPLAY = new Set(["note", "label"]);
const CONTROL = /[\u0000-\u001f\u007f-\u009f<>]/;

function cleanText(value) {
  return String(value).normalize("NFKC").replace(/\s+/g, " ").trim();
}

function number(value) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function sorted(rule) {
  return Object.fromEntries(Object.entries(rule).sort(([a], [b]) => a.localeCompare(b)));
}

/**
 * The product a listing URL names. Mirrors history_identity.listing_identity:
 * a Shopify handle on a URL without a query becomes
 * "shopify:<host without www.>:<handle>", so the same product under
 * /collections/<x>/products/<handle> and /products/<handle> is one key.
 * Every other URL is its own key. Nothing joins listings across stores.
 */
export function productKey(url) {
  const parsed = new URL(url);
  if (SHOPIFY_HOSTS.has(parsed.hostname) && !parsed.search && !parsed.hash) {
    const match = SHOPIFY_HANDLE.exec(parsed.pathname);
    if (match) return `shopify:${parsed.hostname.replace(/^www\./, "")}:${match[1].toLowerCase()}`;
  }
  return url;
}

function text(input, rule, errors, field) {
  if (input[field] === undefined || input[field] === null || input[field] === "") return;
  if (typeof input[field] !== "string") {
    errors[field] = "must_be_text";
    return;
  }
  const value = cleanText(input[field]);
  if (!value) return;
  if (value.length > TEXT_LIMITS[field]) errors[field] = "too_long";
  else if (CONTROL.test(value)) errors[field] = "invalid_characters";
  else rule[field] = value;
}

function width(input, rule, errors, field, decksAllowed) {
  if (input[field] === undefined || input[field] === null) return;
  const value = number(input[field]);
  if (value === null || value < 5 || value > 12) errors[field] = "width_out_of_range";
  else if (!decksAllowed) errors[field] = "decks_only";
  else rule[field] = Math.round(value * 1000) / 1000;
}

function widthRange(rule, errors) {
  if (rule.min_width !== undefined && rule.max_width !== undefined && rule.min_width > rule.max_width) {
    errors.max_width = "below_min_width";
  }
}

function maxPrice(input, rule, errors) {
  if (input.max_price === undefined || input.max_price === null) return;
  const value = number(input.max_price);
  if (value === null || value <= 0 || value > 2000) errors.max_price = "price_out_of_range";
  else rule.max_price = Math.round(value * 100) / 100;
}

function flags(input, rule, errors) {
  for (const field of FLAG_FIELDS) {
    if (input[field] === undefined || input[field] === null) continue;
    if (typeof input[field] !== "boolean") errors[field] = "must_be_boolean";
    else if (input[field]) rule[field] = true;
  }
}

/** A list drawn from `allowed`, without repeats, returned in `allowed` order. */
function choiceList(input, rule, errors, field, allowed) {
  if (input[field] === undefined || input[field] === null) return;
  const value = input[field];
  if (!Array.isArray(value)) errors[field] = "must_be_list";
  else if (value.length === 0) errors[field] = "at_least_one";
  else if (!value.every((entry) => allowed.includes(entry))) errors[field] = "invalid";
  else if (new Set(value).size !== value.length) errors[field] = "duplicate";
  else rule[field] = allowed.filter((entry) => value.includes(entry));
}

function search(input, rule, errors) {
  const part = input.part === undefined ? "Decks" : input.part;
  if (!PARTS.includes(part)) errors.part = "invalid";
  else rule.part = part;
  for (const field of ["brand", "name", "note"]) text(input, rule, errors, field);
  if (!rule.brand && !rule.name && !errors.brand && !errors.name) errors.brand = "brand_or_name_required";
  for (const field of WIDTH_FIELDS) width(input, rule, errors, field, !rule.part || rule.part === "Decks");
  widthRange(rule, errors);
  if (rule.width !== undefined && (rule.min_width !== undefined || rule.max_width !== undefined)) {
    errors.width = "width_or_range_not_both";
  }
  maxPrice(input, rule, errors);
  flags(input, rule, errors);
}

function watch(input, rule, errors) {
  rule.kind = "watch";
  const raw = input.product_url;
  if (raw === undefined || raw === null || raw === "") {
    errors.product_url = "required";
  } else if (typeof raw !== "string" || raw.length > MAX_URL) {
    errors.product_url = "invalid_url";
  } else {
    let parsed = null;
    try {
      parsed = new URL(raw);
    } catch {
      // reported below
    }
    // Exactly the canonical listing URL from the catalog: https, no
    // credentials or fragment, and already in the form a browser writes it,
    // so the Python side derives the same product key from the same string.
    if (!parsed || parsed.href !== raw || parsed.protocol !== "https:" || parsed.username || parsed.password || parsed.hash) {
      errors.product_url = "invalid_url";
    } else if (!STORE_HOSTS.has(parsed.hostname)) {
      errors.product_url = "store_not_tracked";
    } else {
      rule.product_url = raw;
      rule.product_key = productKey(raw);
    }
  }
  text(input, rule, errors, "label");
  text(input, rule, errors, "note");
  maxPrice(input, rule, errors);
  flags(input, rule, errors);
  // A watch with no trigger means "any meaningful price drop". Stored
  // explicitly so it never falls back to the engine's "new match" email.
  if (!rule.max_price && !FLAG_FIELDS.some((field) => rule[field])) rule.alert_on_drop = true;
}

function digest(input, rule, errors) {
  rule.kind = "digest";
  choiceList(input, rule, errors, "parts", CATALOG_PARTS);
  choiceList(input, rule, errors, "events", DIGEST_EVENTS);
  const decks = !rule.parts || rule.parts.includes("Decks");
  for (const field of ["min_width", "max_width"]) width(input, rule, errors, field, decks);
  widthRange(rule, errors);
  maxPrice(input, rule, errors);
  text(input, rule, errors, "note");
}

/**
 * Returns { rule, errors }. `rule` is normalized (keys sorted, defaults
 * applied); `errors` maps field names to short reason codes.
 */
export function validateRule(input) {
  if (!input || typeof input !== "object" || Array.isArray(input)) {
    return { rule: null, errors: { rule: "must_be_object" } };
  }
  const kind = input.kind === undefined || input.kind === null ? "search" : input.kind;
  if (!KINDS.includes(kind)) return { rule: null, errors: { kind: "invalid" } };
  const errors = {};
  for (const key of Object.keys(input)) {
    if (!FIELDS[kind].has(key)) errors[key] = KNOWN.has(key) ? "not_for_kind" : "unknown_field";
  }
  const rule = {};
  ({ search, watch, digest })[kind](input, rule, errors);
  if (Object.keys(errors).length) return { rule: null, errors };
  return { rule: sorted(rule), errors };
}

/** What makes two rules the same alert: everything but display text, and a watch's URL spelling. */
function signature(rule) {
  const identity = Object.fromEntries(Object.entries(rule).filter(([key]) => !DISPLAY.has(key) && key !== "product_url"));
  return JSON.stringify(identity);
}

/** Validates a whole rule list; errors are keyed `rules[i].field`. */
export function validateRules(list, maxRules) {
  if (!Array.isArray(list)) return { rules: null, errors: { rules: "must_be_list" } };
  if (list.length === 0) return { rules: null, errors: { rules: "at_least_one" } };
  if (list.length > maxRules) return { rules: null, errors: { rules: "too_many" } };
  const errors = {};
  const rules = [];
  const seen = new Set();
  let digests = 0;
  list.forEach((input, index) => {
    const result = validateRule(input);
    if (!result.rule) {
      for (const [field, code] of Object.entries(result.errors)) errors[`rules[${index}].${field}`] = code;
      return;
    }
    if (result.rule.kind === "digest" && (digests += 1) > 1) {
      errors[`rules[${index}]`] = "one_digest_only";
      return;
    }
    const key = signature(result.rule);
    if (seen.has(key)) {
      errors[`rules[${index}]`] = "duplicate";
      return;
    }
    seen.add(key);
    rules.push(result.rule);
  });
  return Object.keys(errors).length ? { rules: null, errors } : { rules, errors };
}

/** Stable id: the same rule content (display text aside) keeps the same id across edits. */
export async function ruleId(subscriberId, rule) {
  const identity = Object.fromEntries(Object.entries(rule).filter(([key]) => !DISPLAY.has(key)));
  return `r_${(await sha256Hex(`${subscriberId}:${JSON.stringify(identity)}`)).slice(0, 24)}`;
}
