// Subscriber rule schema v1. A subset of watchlist.yaml, checked here and
// again in alerts_delivery.py before the Python engine sees it.

import { sha256Hex } from "./crypto.js";

export const PARTS = ["Decks", "Wheels", "Trucks", "Bearings"];
const TEXT_FIELDS = { brand: 60, name: 80, note: 80 };
const WIDTH_FIELDS = ["width", "min_width", "max_width", "back_in_stock_width"];
const FLAG_FIELDS = ["alert_on_drop", "alert_on_low", "alert_on_stock"];
const ALLOWED = new Set(["part", ...Object.keys(TEXT_FIELDS), ...WIDTH_FIELDS, "max_price", ...FLAG_FIELDS]);
const CONTROL = /[\u0000-\u001f\u007f-\u009f<>]/;

function cleanText(value) {
  return String(value).normalize("NFKC").replace(/\s+/g, " ").trim();
}

function number(value) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

/**
 * Returns { rule, errors }. `rule` is normalized (keys sorted, defaults
 * applied); `errors` maps field names to short reason codes.
 */
export function validateRule(input) {
  const errors = {};
  if (!input || typeof input !== "object" || Array.isArray(input)) {
    return { rule: null, errors: { rule: "must_be_object" } };
  }
  for (const key of Object.keys(input)) {
    if (!ALLOWED.has(key)) errors[key] = "unknown_field";
  }
  const rule = {};
  const part = input.part === undefined ? "Decks" : input.part;
  if (!PARTS.includes(part)) errors.part = "invalid";
  else rule.part = part;

  for (const [field, limit] of Object.entries(TEXT_FIELDS)) {
    if (input[field] === undefined || input[field] === null || input[field] === "") continue;
    if (typeof input[field] !== "string") {
      errors[field] = "must_be_text";
      continue;
    }
    const value = cleanText(input[field]);
    if (!value) continue;
    if (value.length > limit) errors[field] = "too_long";
    else if (CONTROL.test(value)) errors[field] = "invalid_characters";
    else rule[field] = value;
  }
  if (!rule.brand && !rule.name && !errors.brand && !errors.name) errors.brand = "brand_or_name_required";

  for (const field of WIDTH_FIELDS) {
    if (input[field] === undefined || input[field] === null) continue;
    const value = number(input[field]);
    if (value === null || value < 5 || value > 12) errors[field] = "width_out_of_range";
    else if (rule.part && rule.part !== "Decks") errors[field] = "decks_only";
    else rule[field] = Math.round(value * 1000) / 1000;
  }
  if (rule.min_width !== undefined && rule.max_width !== undefined && rule.min_width > rule.max_width) {
    errors.max_width = "below_min_width";
  }
  if (rule.width !== undefined && (rule.min_width !== undefined || rule.max_width !== undefined)) {
    errors.width = "width_or_range_not_both";
  }

  if (input.max_price !== undefined && input.max_price !== null) {
    const value = number(input.max_price);
    if (value === null || value <= 0 || value > 2000) errors.max_price = "price_out_of_range";
    else rule.max_price = Math.round(value * 100) / 100;
  }
  for (const field of FLAG_FIELDS) {
    if (input[field] === undefined || input[field] === null) continue;
    if (typeof input[field] !== "boolean") errors[field] = "must_be_boolean";
    else if (input[field]) rule[field] = true;
  }
  if (Object.keys(errors).length) return { rule: null, errors };
  return { rule: Object.fromEntries(Object.entries(rule).sort(([a], [b]) => a.localeCompare(b))), errors };
}

/** Validates a whole rule list; errors are keyed `rules[i].field`. */
export function validateRules(list, maxRules) {
  if (!Array.isArray(list)) return { rules: null, errors: { rules: "must_be_list" } };
  if (list.length === 0) return { rules: null, errors: { rules: "at_least_one" } };
  if (list.length > maxRules) return { rules: null, errors: { rules: "too_many" } };
  const errors = {};
  const rules = [];
  const seen = new Set();
  list.forEach((input, index) => {
    const result = validateRule(input);
    if (!result.rule) {
      for (const [field, code] of Object.entries(result.errors)) errors[`rules[${index}].${field}`] = code;
      return;
    }
    const { note, ...identity } = result.rule;
    const signature = JSON.stringify(identity);
    if (seen.has(signature)) {
      errors[`rules[${index}]`] = "duplicate";
      return;
    }
    seen.add(signature);
    rules.push(result.rule);
  });
  return Object.keys(errors).length ? { rules: null, errors } : { rules, errors };
}

/** Stable id: the same rule content (note aside) keeps the same id across edits. */
export async function ruleId(subscriberId, rule) {
  const { note, ...identity } = rule;
  return `r_${(await sha256Hex(`${subscriberId}:${JSON.stringify(identity)}`)).slice(0, 24)}`;
}
