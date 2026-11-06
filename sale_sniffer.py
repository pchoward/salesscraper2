"""Catch flash sales between scheduled scrapes (owner, 2026-11-04).

Every couple of hours a cheap check reads sale *signals*, not catalogs:

* each Skate Shopify shop's sale collections: ``/collections/<h>.json``
  carries ``products_count`` (one request per collection);
* Tactics' sale pages: the "N Results" count on page 1;
* sale sections no scraper reads (``sale_watch``).

It compares them with the previous check (kept in the workflow cache, never
committed). A big jump, or a sale section that wasn't there last time,
starts the Skate scraper. Guard rails: at most ``MAX_PER_DAY`` triggered
scrapes per US-Eastern day, ``MIN_GAP_HOURS`` apart, and none while a Skate
scrape is queued or running. Nothing is emailed.

It also re-runs the site's Pages deploy when the latest one failed (a
GitHub-side timeout once left the live site a day stale).

``python sale_sniffer.py --state sniff.json`` checks and prints the decision;
``--trigger`` also starts the scrape (the workflow passes it).
"""

import argparse
import datetime
import json
import logging
import os
import re
import subprocess
import sys
import time
import urllib.request
from zoneinfo import ZoneInfo

logger = logging.getLogger("sale_sniffer")

EASTERN = ZoneInfo("America/New_York")
DELAY = 1.5
# A store's sale count "jumps" when it grows by both of these.
JUMP_RATIO = 1.25
JUMP_MIN = 15
MAX_PER_DAY = 3
MIN_GAP_HOURS = 3
WORKFLOW = "scrape.yml"
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def _get(url, timeout=30):
    request = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", "replace")
    except Exception as exc:
        logger.info("sniff: could not read %s: %s", url, exc)
        return None


def shopify_count(base, handle, fetch=_get):
    """``products_count`` of one Shopify collection, or None."""
    text = fetch(f"{base.rstrip('/')}/collections/{handle}.json")
    try:
        return int(json.loads(text or "")["collection"]["products_count"])
    except (ValueError, KeyError, TypeError):
        return None


def results_count(html):
    """The "57 Results" count on a Tactics listing page, or None."""
    match = re.search(r"([\d,]+)\s+Results?\b", html or "", re.I)
    return int(match.group(1).replace(",", "")) if match else None


def sources():
    """[(key, kind, where)] of the signals to read: Shopify collections and Tactics pages."""
    from stores import ccs, exodus, kinetic, spot, tactics, tgm
    out = []
    for shop in (tgm.SHOP, kinetic.SHOP, spot.SHOP, exodus.SHOP):
        for url in shop.sale_jsons:
            if "/collections/" in url:
                handle = url.split("/collections/", 1)[1].split("/", 1)[0]
                out.append((f"{shop.store}:{handle}", "shopify", (shop.base, handle)))
    out.append(("CCS:clearance", "shopify", (ccs.CLEARANCE_JSON.split("/collections/")[0], "clearance")))
    seen = set()
    for scraper in tactics.scrapers():
        if scraper.url not in seen and scraper.url.startswith("https://"):
            seen.add(scraper.url)
            out.append((f"Tactics:{scraper.url.split('tactics.com/', 1)[1]}", "page", scraper.url))
    return out


def read_signals(fetch=_get, sleep=time.sleep, source_list=None, sections=None):
    """{"counts": {key: n}, "sections": [url, ...]}; unreadable signals are left out."""
    counts = {}
    for key, kind, where in (source_list if source_list is not None else sources()):
        sleep(DELAY)
        value = shopify_count(*where, fetch=fetch) if kind == "shopify" else results_count(fetch(where))
        if value is not None:
            counts[key] = value
    if sections is None:
        try:
            import sale_watch
            report = sale_watch.check()
        except Exception as exc:  # the counts still decide
            logger.warning("sniff: sale-section check skipped: %s", exc)
            report = {}
        sections = sorted(entry["url"] for entries in report.values() for entry in entries)
    return {"counts": counts, "sections": list(sections)}


def changes(previous, current):
    """Reasons to scrape now: counts that jumped and sections that appeared."""
    reasons = []
    before = (previous or {}).get("counts") or {}
    for key, now in sorted((current.get("counts") or {}).items()):
        was = before.get(key)
        if was is None:
            continue
        if now >= was * JUMP_RATIO and now - was >= JUMP_MIN:
            reasons.append(f"{key} sale grew {was} -> {now}")
    if previous is not None:
        old = set(previous.get("sections") or [])
        for url in current.get("sections") or []:
            if url not in old:
                reasons.append(f"new sale section {url}")
    return reasons


def _eastern_day(stamp):
    return datetime.datetime.fromisoformat(stamp).astimezone(EASTERN).date().isoformat()


def allowed(state, now, busy=False):
    """(True, "") when a triggered scrape may start now, else (False, why)."""
    if busy:
        return False, "a Skate scrape is already queued or running"
    triggers = list((state or {}).get("triggers") or [])
    today = now.astimezone(EASTERN).date().isoformat()
    if sum(1 for stamp in triggers if _eastern_day(stamp) == today) >= MAX_PER_DAY:
        return False, f"already {MAX_PER_DAY} triggered scrapes today"
    if triggers:
        last = datetime.datetime.fromisoformat(max(triggers))
        if now - last < datetime.timedelta(hours=MIN_GAP_HOURS):
            return False, f"last triggered scrape was under {MIN_GAP_HOURS} hours ago"
    return True, ""


def scrape_busy(run=subprocess.run, workflow=WORKFLOW):
    """True when a run of ``workflow`` is queued or in progress (needs gh)."""
    try:
        result = run(["gh", "run", "list", "--workflow", workflow, "--limit", "5", "--json", "status"],
                     capture_output=True, text=True, timeout=60)
        runs = json.loads(result.stdout or "[]")
    except Exception as exc:
        logger.warning("sniff: could not list scrape runs: %s", exc)
        return True  # unsure: don't start another
    return any(entry.get("status") in ("queued", "in_progress", "waiting", "pending", "requested") for entry in runs)


def start_scrape(run=subprocess.run, workflow=WORKFLOW):
    result = run(["gh", "workflow", "run", workflow, "--ref", "main"], capture_output=True, text=True, timeout=60)
    return result.returncode == 0


# ---- BMX, Ski, MTB (owner, 2026-11-06: evo's Big Snow Sale and Fanatik's
# TRP promo arrived as new collections; this check was Skate only) ---------
SPORTS_WORKFLOW = "scrape-sports.yml"
# Sale-like collection names, including "up-to-60-off-snow" and "past-season".
SPORT_SALE_HANDLE = re.compile(
    r"sale|clearance|closeout|deal|black[-_]?friday|blacker|cyber|doorbuster|flash|outlet|markdown|blowout|bfcm|"
    r"(?:^|-)\d+-off(?:-|$)|(?:^|-)off(?:-|$)|percent-off|past-season|last-chance", re.I)
# Clothing and the like are not in the BMX/Ski/MTB catalogs; snow and ski are.
SPORT_IGNORE = re.compile(
    r"jacket|pant|shirt|tee|hood|sock|hat|beanie|underwear|fleece|base-?layer|midlayer|outerwear|apparel|"
    r"clothing|swim|sandal|footwear|shoe|gift|test|do-not-use|road|gravel|triathlon|"
    r"muc-?off|off-?road|kick-?off|off-?set", re.I)  # "off" inside a brand or word, not "N% off"
SECTIONS_PER_STORE = 8


def sport_shops():
    """[(store name, base, collection handles read)] for every BMX/Ski/MTB Shopify store."""
    import importlib
    from stores import shopify
    seen = {}
    for sport in ("bmx", "mtb", "ski"):
        module = importlib.import_module(f"sports.{sport}.stores")
        for value in vars(module).values():
            for store in (value if isinstance(value, (tuple, list)) else [value]):
                if isinstance(store, shopify.ShopifyStore) and store.base not in seen:
                    handles = {url.split("/collections/", 1)[1].split("/", 1)[0]
                               for url in store.sale_jsons if "/collections/" in url}
                    seen[store.base] = (store.store, store.base, handles)
    return list(seen.values())


def sport_sources():
    return [(f"{name}:{handle}", "shopify", (base, handle))
            for name, base, handles in sport_shops() for handle in sorted(handles)]


def homepage_sale_collections(base, read_handles, fetch=_get):
    """Sale-like collections the store's homepage links to and we don't read.

    Some stores launch a sale in a collection their public collection list
    doesn't include (evo's 3,500 collections leave out "up-to-60-off-snow");
    the homepage's sale banner links to it."""
    import sale_watch
    if not sale_watch._allowed(base, "/", fetch):
        return []
    html = fetch(base.rstrip("/") + "/") or ""
    found = []
    for handle in re.findall(r'href="(?:https?://[^"/]+)?/collections/([a-z0-9][a-z0-9-]*)', html, re.I):
        handle = handle.lower()
        if handle in read_handles or not SPORT_SALE_HANDLE.search(handle) or SPORT_IGNORE.search(handle):
            continue
        url = f"{base.rstrip('/')}/collections/{handle}"
        if url not in found:
            found.append(url)
    return found


def read_sport_signals(fetch=_get, sleep=time.sleep, shops=None):
    """Sale collection sizes and new sale-like collections at the BMX/Ski/MTB shops."""
    import sale_watch
    shops = shops if shops is not None else sport_shops()
    sources = [(f"{name}:{handle}", "shopify", (base, handle)) for name, base, handles in shops for handle in sorted(handles)]
    result = read_signals(fetch=fetch, sleep=sleep, source_list=sources, sections=[])
    urls = []
    for name, base, handles in shops:
        sleep(DELAY)
        try:
            found = sale_watch.shopify_sections(base, handles, fetch, sale_re=SPORT_SALE_HANDLE, ignore=SPORT_IGNORE,
                                                limit=SECTIONS_PER_STORE, sleep=sleep)
        except Exception as exc:
            logger.info("sniff: sections at %s skipped: %s", name, exc)
            continue
        urls += [entry["url"] for entry in found]
        sleep(DELAY)
        try:
            urls += homepage_sale_collections(base, handles, fetch)
        except Exception as exc:
            logger.info("sniff: homepage of %s skipped: %s", name, exc)
    result["sections"] = sorted(set(urls))
    return result


PAGES_RUN = "pages build and deployment"
MAX_PAGES_RETRIES = 2


def _gh_json(args, run=subprocess.run):
    result = run(["gh", "api", *args], capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "gh api failed").strip()[:200])
    return json.loads(result.stdout or "null")


def pages_guard(state, repo, gh=_gh_json):
    """Re-run the site's latest Pages deploy when it failed (2026-11-05: a
    deploy timed out on GitHub's side and the site kept serving the previous
    day's Skate page). Each failed run is retried at most MAX_PAGES_RETRIES
    times. Returns (state, report line or "")."""
    state = dict(state or {})
    try:
        runs = gh([f"repos/{repo}/actions/runs?branch=main&per_page=30"])["workflow_runs"]
    except Exception as exc:
        return state, f"Site deploy check skipped: {exc}"
    pages = [run for run in runs if run.get("name") == PAGES_RUN]
    if not pages:
        return state, ""
    latest = pages[0]
    if latest.get("status") != "completed" or latest.get("conclusion") != "failure":
        return state, ""
    tried = dict(state.get("pages_retries") or {})
    key = str(latest["id"])
    if tried.get(key, 0) >= MAX_PAGES_RETRIES:
        return state, f"Site deploy {key} still failing after {MAX_PAGES_RETRIES} retries; leaving it for a person."
    try:
        gh(["-X", "POST", f"repos/{repo}/actions/runs/{key}/rerun-failed-jobs"])
    except Exception as exc:
        return state, f"Site deploy {key} failed and could not be re-run: {exc}"
    tried[key] = tried.get(key, 0) + 1
    state["pages_retries"] = dict(list(tried.items())[-10:])
    return state, f"Site deploy {key} (commit {str(latest.get('head_sha', ''))[:7]}) had failed: re-ran it."


def sniff(state, now, read=read_signals, busy=scrape_busy, start=start_scrape, trigger=False, label="Skate"):
    """Check once. Returns (new_state, report lines)."""
    state = dict(state or {})
    current = read()
    previous = state.get("last")
    reasons = changes(previous, current)
    lines = [f"Checked {len(current['counts'])} sale counts and {len(current['sections'])} unread sale sections."]
    if previous is None:
        lines.append("First check: saved as the baseline, nothing to compare yet.")
    if reasons:
        lines += [f"- {reason}" for reason in reasons]
        ok, why = allowed(state, now, busy() if trigger else False)
        if not ok:
            lines.append(f"Not scraping: {why}.")
        elif not trigger:
            lines.append(f"Would start the {label} scraper (dry run).")
        elif start():
            lines.append(f"Started the {label} scraper.")
            state["triggers"] = (list(state.get("triggers") or []) + [now.isoformat()])[-20:]
        else:
            lines.append(f"Could not start the {label} scraper.")
    elif previous is not None:
        lines.append("No sale jumps or new sale sections.")
    # Keep the last readable value for a signal that failed this time.
    merged = dict(((previous or {}).get("counts") or {}), **current["counts"])
    state["last"] = {"counts": merged, "sections": current["sections"], "checked_at": now.isoformat()}
    return state, lines


def split_state(state):
    """Skate and BMX/Ski/MTB keep their own baseline and trigger history.
    A state saved before the split is Skate's."""
    state = dict(state or {})
    if "last" in state or "triggers" in state:
        skate = {key: state.pop(key) for key in ("last", "triggers") if key in state}
        state.setdefault("skate", skate)
    return state


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--state", default="sniff_state.json")
    parser.add_argument("--trigger", action="store_true", help="start the matching scraper on a jump")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        with open(args.state, encoding="utf-8") as handle:
            state = json.load(handle)
    except (OSError, ValueError):
        state = {}
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    state = split_state(state)
    skate, lines = sniff(state.get("skate"), now, trigger=args.trigger)
    lines = ["### Skate", *lines]
    sports_state, sport_lines = sniff(
        state.get("sports"), now, read=read_sport_signals, trigger=args.trigger, label="BMX, Ski, MTB",
        busy=lambda: scrape_busy(workflow=SPORTS_WORKFLOW), start=lambda: start_scrape(workflow=SPORTS_WORKFLOW))
    lines += ["", "### BMX, Ski, MTB", *sport_lines]
    state.update({"skate": skate, "sports": sports_state})
    repo = os.environ.get("GITHUB_REPOSITORY")
    if args.trigger and repo:
        state, line = pages_guard(state, repo)
        if line:
            lines.append(line)
    with open(args.state, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)
    text = "## Flash-sale check\n\n" + "\n".join(lines) + "\n"
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(text)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
