"""Write worker/wrangler.toml for the "Deploy Worker" workflow (owner,
2026-11-28: deploy from GitHub Actions instead of a codespace).

The real wrangler.toml is the owner's private, git-ignored file. This builds
the same file from repository variables, with the defaults the owner's file
had (CLAUDE.md, 2026-11-20). Nothing here is secret: HMAC_SECRET,
TOKEN_PEPPER, RESEND_API_KEY and the other secrets live on the Worker
(Cloudflare dashboard or `wrangler secret put`) and a deploy keeps them.

A deploy replaces the Worker's plain variables with the [vars] below, so every
value the live Worker uses must be here: override any default with a
repository variable named WORKER_<NAME> (e.g. WORKER_MODE=production).

    python worker/write_wrangler_toml.py            # writes worker/wrangler.toml
    python worker/write_wrangler_toml.py --print    # shows it, writes nothing
"""
import json
import os
import sys

DEFAULTS = {
    "MODE": "staging",
    "PUBLIC_ORIGIN": "https://shreddeals.com",
    "MANAGE_PAGE_URL": "https://shreddeals.com/sale_items_chart.html",
    "CONSENT_VERSION": "2026-10",
    "EMAIL_FROM": "ShredDeals <alerts@shreddeals.com>",
    "MAX_ACTIVE_SUBSCRIBERS": "200",
    "MAX_RULES_PER_SUBSCRIBER": "10",
    "DAILY_EMAILS_PER_SUBSCRIBER": "3",
    "CATALOG_SEARCH_ENABLED": "true",
    "NEWSLETTER_INBOX": "deals@shreddeals.com",
}
REQUIRED = {"PUBLIC_API_URL": "ALERTS_API_URL", "D1_DATABASE_ID": "WORKER_D1_ID"}


class ConfigError(ValueError):
    pass


def _string(value):
    # TOML basic strings take JSON's escapes for the characters we allow.
    return json.dumps(str(value), ensure_ascii=False)


def settings(env):
    """The [vars] values and the D1 id, from ``env``. Raises ConfigError."""
    values = {name: str(env.get(f"WORKER_{name}") or default).strip() for name, default in DEFAULTS.items()}
    api_url = str(env.get("ALERTS_API_URL") or "").strip().rstrip("/")
    d1 = str(env.get("WORKER_D1_ID") or "").strip()
    missing = [variable for variable, value in (("ALERTS_API_URL", api_url), ("WORKER_D1_ID", d1)) if not value]
    if missing:
        raise ConfigError("missing repository variable(s): " + ", ".join(missing))
    if not api_url.startswith("https://"):
        raise ConfigError("ALERTS_API_URL must start with https://")
    if not all(c in "0123456789abcdef-" for c in d1.lower()):
        raise ConfigError("WORKER_D1_ID doesn't look like a D1 database id")
    if values["MODE"] not in ("staging", "production"):
        raise ConfigError("WORKER_MODE must be staging or production")
    for name, value in values.items():
        if any(ord(c) < 32 for c in value):
            raise ConfigError(f"WORKER_{name} has a control character")
    values["PUBLIC_API_URL"] = api_url
    return values, d1


def render(env):
    values, d1 = settings(env)
    lines = [
        "# Written by worker/write_wrangler_toml.py for the Deploy Worker workflow.",
        'name = "skatedeals-alerts"',
        'main = "src/index.js"',
        'compatibility_date = "2026-10-01"',
        "workers_dev = true",
        "",
        "[vars]",
    ]
    lines += [f"{name} = {_string(values[name])}" for name in ["MODE", "PUBLIC_ORIGIN", "PUBLIC_API_URL"] +
              [n for n in DEFAULTS if n not in ("MODE", "PUBLIC_ORIGIN")]]
    lines += [
        "",
        "[[d1_databases]]",
        'binding = "DB"',
        'database_name = "skatedeals-alerts"',
        f"database_id = {_string(d1)}",
        'migrations_dir = "migrations"',
        "",
        "[triggers]",
        'crons = ["37 4 * * *"]',
        "",
        "[observability]",
        "enabled = true",
        "",
    ]
    return "\n".join(lines)


def main(argv=None, env=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        text = render(os.environ if env is None else env)
    except ConfigError as error:
        print(f"::error::{error}", file=sys.stderr)
        return 1
    if "--print" in argv:
        print(text)
        return 0
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wrangler.toml")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
