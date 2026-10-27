"""Which price-history rows are the same product, and an audit of where that breaks.

Price history is keyed by listing URL. That holds up as long as one URL is one
product. Two things break it:

* URL churn: the same product shows up under a new URL, so its history
  starts over (fragmentation).
* URL reuse: a URL starts selling a different product, so two products share
  one history and one all-time low (a false merge).

Identity hierarchy, strongest evidence first. Only level 2 ever joins two URLs.

1. The listing URL (whitespace removed). Always the history key.
2. A Shopify product handle (CCS, TGM, Muir Skate) on a URL with no query string.
   Shopify keeps handles unique within a shop, so
   ``/collections/clearance/products/<handle>`` and ``/products/<handle>``
   are the same product page. ``update_price_history`` moves the history to
   the new URL when the old one is no longer listed.
3. Evidence that is recorded but never joins URLs:

   * Skate Warehouse ``descpage-<CODE>`` codes. The catalog shows one code
     used for a pair of trucks and later for a SINGLE truck at half the
     price, and for a deck and its R7 construction. Joining on the code
     would invent price drops.
   * Tactics variant paths (``/brand/product/<color-size>``) and Zumiez
     ``-1.html`` twins. Both are listed side by side as different variants.
   * Product names. Similar or equal names are never proof: stores reuse
     a name across widths and colors.

A guard runs in the other direction: when the name on a URL starts stating a
different size (deck width, wheel diameter or durometer, truck size), the
earlier product's summary is kept under ``earlier_products`` and the price
series restarts, so two sizes never share an all-time low.

``audit_history`` reports all of this without changing anything. Run
``python history_identity.py`` for the stored file, or ``--git`` to replay
every committed ``previous_data.json``.
"""

import collections
import re
from urllib.parse import parse_qs, urlsplit

from filters import extract_deck_dimensions, item_passes_filters, normalize_product_name, normalize_url
from matching import canonical_width, describe_item

# Shops known to run on Shopify, where a product handle is unique per shop.
SHOPIFY_HOSTS = frozenset({"shop.ccs.com", "tgmskateboards.com", "www.tgmskateboards.com", "muirskate.com", "www.muirskate.com"})

_SHOPIFY_HANDLE_RE = re.compile(r"/products/([^/?#]+)/?$")
_SKATEWAREHOUSE_CODE_RE = re.compile(r"/descpage-([A-Za-z0-9]+)\.html$")
_ZUMIEZ_SLUG_RE = re.compile(r"/([^/]+?)(?:-(\d+))?\.html$")


def listing_identity(url):
    """What a listing URL says about the product behind it.

    Returns ``url`` (normalized), ``retailer``, ``key`` (equal keys are the
    same product), ``basis`` (``"shopify-handle"`` or ``"url"``), and the
    informational ``retailer_code`` and ``variant``. Only a Shopify handle
    makes ``key`` differ from the URL itself.
    """
    clean = normalize_url(url)
    info = {
        "url": clean,
        "retailer": "other",
        "key": clean,
        "basis": "url",
        "retailer_code": None,
        "variant": None,
    }
    if not clean:
        return info
    try:
        parts = urlsplit(clean)
    except ValueError:
        return info
    host = parts.netloc.lower()
    path = parts.path
    if host in SHOPIFY_HOSTS:
        info["retailer"] = "ccs" if "ccs" in host else "tgm" if "tgm" in host else "muirskate"
        match = _SHOPIFY_HANDLE_RE.search(path)
        if match and not parts.query and not parts.fragment:
            handle = match.group(1).lower()
            info["key"] = f"shopify:{host.removeprefix('www.')}:{handle}"
            info["basis"] = "shopify-handle"
    elif host.endswith("skatewarehouse.com"):
        info["retailer"] = "skatewarehouse"
        match = _SKATEWAREHOUSE_CODE_RE.search(path)
        if match:
            info["retailer_code"] = match.group(1).upper()
        color = parse_qs(parts.query).get("color")
        if color:
            info["variant"] = color[0].upper()
    elif host.endswith("tactics.com"):
        info["retailer"] = "tactics"
        segments = [segment for segment in path.split("/") if segment]
        if len(segments) > 2:
            info["variant"] = "/".join(segments[2:])
    elif host.endswith("zumiez.com"):
        info["retailer"] = "zumiez"
        match = _ZUMIEZ_SLUG_RE.search(path)
        if match and match.group(2):
            info["variant"] = f"-{match.group(2)}"
    return info


def size_signature(name, part):
    """Sizes the name states, as ``{attribute: value}``. Empty when none.

    Uses the cross-store matcher's parser, so 8.12 and 8.125 are one width
    and 55.5mm is not 55mm.
    """
    info = describe_item({"name": name or "", "part": part or ""})
    return dict(info.get("sizes") or [])


def sizes_conflict(left, right):
    """Attributes both signatures state with different values, as ``{attr: (a, b)}``."""
    return {
        attribute: (left[attribute], right[attribute])
        for attribute in sorted(set(left) & set(right))
        if left[attribute] != right[attribute]
    }


def _stored_width_conflict(entry):
    """A deck row whose stored width disagrees with the width in its name."""
    if (entry or {}).get("part") != "Decks":
        return None
    stored = entry.get("width")
    named, _length = extract_deck_dimensions(entry.get("name") or "")
    try:
        stored = float(stored)
    except (TypeError, ValueError):
        return None
    if named is None or canonical_width(stored) == canonical_width(named):
        return None
    return (stored, named)


def _finding(kind, risk, action, store, urls, detail, names=None, dates=None):
    return {
        "kind": kind,
        "risk": risk,
        "action": action,
        "store": store or "",
        "urls": sorted(urls),
        "names": names or [],
        "dates": dates or [],
        "detail": detail,
    }


def _catalog_rows(catalog):
    """Listings that could be in price history: they pass the store filters."""
    for key, items in (catalog or {}).items():
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict) and normalize_url(item.get("url")) and item_passes_filters(item):
                yield key, item


def _lifetimes_from_snapshots(snapshots):
    """Per URL: store, part, first/last day, days seen, names in order, prices."""
    rows = {}
    for day, catalog in snapshots:
        seen_today = set()
        for _key, item in _catalog_rows(catalog):
            url = normalize_url(item.get("url"))
            row = rows.setdefault(
                url,
                {
                    "store": item.get("store") or "",
                    "part": item.get("part") or "",
                    "days": [],
                    "names": [],
                    "prices": [],
                },
            )
            name = normalize_product_name(item.get("name") or "")
            if name and (not row["names"] or row["names"][-1][1] != name):
                row["names"].append((day, name))
            if url not in seen_today:
                seen_today.add(url)
                if not row["days"] or row["days"][-1] != day:
                    row["days"].append(day)
                    row["prices"].append((day, item.get("price_new")))
    return rows


def _lifetimes_from_history(history):
    rows = {}
    for raw_url, entry in (history or {}).items():
        if not isinstance(entry, dict):
            continue
        url = normalize_url(raw_url)
        first = str(entry.get("first_seen") or "")[:10]
        last = str(entry.get("last_seen") or "")[:10]
        if not url or not first or not last:
            continue
        rows[url] = {
            "store": entry.get("store") or "",
            "part": entry.get("part") or "",
            "days": [first, last],
            "names": [(last, normalize_product_name(entry.get("name") or ""))],
            "prices": [],
        }
    return rows


def audit_history(history, snapshots=None, gap_days=7):
    """Find identity problems in stored price history. Changes nothing.

    ``history`` is the ``price_history.json`` dict. ``snapshots`` is an
    optional list of ``(date, catalog)`` pairs, oldest first, where each
    catalog is a ``previous_data.json`` dict; with them the audit can see
    names change on one URL, URLs come and go, and gaps in a listing. The
    last snapshot of a day stands for that day. A gap is ``gap_days`` or
    more scan days on which the listing's store and part returned items but
    not this listing.

    Returns ``{"counts": {kind: n}, "findings": [...]}``. Each finding has
    ``kind``, ``risk`` (``false merge``, ``fragmentation``, or ``none``),
    ``action`` (what the code does about it), ``store``, ``urls``,
    ``names``, ``dates``, and ``detail``.
    """
    history = history if isinstance(history, dict) else {}
    by_day = {}
    for day, catalog in snapshots or []:
        if isinstance(catalog, dict):
            by_day[str(day)[:10]] = catalog
    snapshots = sorted(by_day.items())
    lifetimes = _lifetimes_from_snapshots(snapshots) if snapshots else _lifetimes_from_history(history)
    findings = []

    # 1. One URL, two sizes: a false merge already in the stored history.
    for raw_url, entry in sorted(history.items()):
        if not isinstance(entry, dict):
            continue
        conflict = _stored_width_conflict(entry)
        if conflict:
            findings.append(
                _finding(
                    "size_changed_same_url",
                    "false merge",
                    "report only: the stored row is not rewritten; it splits if its name changes size again",
                    entry.get("store"),
                    [normalize_url(raw_url)],
                    f'stored width {conflict[0]:g}" but the name now says {conflict[1]:g}"',
                    names=[normalize_product_name(entry.get("name") or "")],
                )
            )
    reported = {finding["urls"][0] for finding in findings}
    for url, row in sorted(lifetimes.items()):
        names = row["names"]
        if len(names) < 2:
            continue
        sized = [(day, name, size_signature(name, row["part"])) for day, name in names]
        conflicts = {}
        for (_d1, _n1, s1), (_d2, _n2, s2) in zip(sized, sized[1:]):
            conflicts.update(sizes_conflict(s1, s2))
        if conflicts:
            if url in reported:
                continue
            shown = ", ".join(f"{attr} {a} then {b}" for attr, (a, b) in conflicts.items())
            findings.append(
                _finding(
                    "size_changed_same_url",
                    "false merge",
                    "split automatically from now on; this past change is report only",
                    row["store"],
                    [url],
                    f"the name changed size on the same URL ({shown})",
                    names=[name for _day, name in names],
                    dates=[day for day, _name in names],
                )
            )
        else:
            findings.append(
                _finding(
                    "renamed_same_url",
                    "none",
                    "history continues; no size changed",
                    row["store"],
                    [url],
                    "the name changed but states the same sizes",
                    names=[name for _day, name in names],
                    dates=[day for day, _name in names],
                )
            )

    urls = sorted(set(lifetimes) | {normalize_url(url) for url in history if normalize_url(url)})
    identities = {url: listing_identity(url) for url in urls}

    # 2. Shopify handle under two URLs: reliable churn.
    by_handle = collections.defaultdict(list)
    for url, identity in identities.items():
        if identity["basis"] == "shopify-handle":
            by_handle[identity["key"]].append(url)
    for key, members in sorted(by_handle.items()):
        if len(members) < 2:
            continue
        spans = [_span(lifetimes.get(url)) for url in members]
        findings.append(
            _finding(
                "shopify_handle_moved",
                "fragmentation",
                "history moves to the new URL automatically from now on; past rows are report only",
                (lifetimes.get(members[0]) or history.get(members[0]) or {}).get("store"),
                members,
                f"same Shopify product ({key.split(':')[-1]}) under {len(members)} URLs",
                dates=[span for span in spans if span],
            )
        )

    # 3. One retailer code, several product pages: why codes never join URLs.
    by_code = collections.defaultdict(list)
    for url, identity in identities.items():
        if identity["retailer_code"]:
            by_code[(identity["retailer"], identity["retailer_code"], identity["variant"] or "")].append(url)
    for (retailer, code, _variant), members in sorted(by_code.items()):
        if len(members) < 2:
            continue
        names = [_latest_name(url, lifetimes, history) for url in sorted(members)]
        findings.append(
            _finding(
                "shared_retailer_code",
                "false merge",
                "never joined: the code is not unique to one product",
                retailer,
                members,
                f"code {code} is used by {len(members)} different product pages",
                names=names,
                dates=[_span(lifetimes.get(url)) for url in sorted(members)],
            )
        )

    # 4 and 5. Same store, part, and name at several URLs.
    by_name = collections.defaultdict(list)
    for url, row in lifetimes.items():
        name = row["names"][-1][1] if row["names"] else ""
        if name and row["days"]:
            by_name[(row["store"], row["part"], name.casefold())].append(url)
    for (store, _part, _name), members in sorted(by_name.items()):
        if len(members) < 2:
            continue
        if len({identities[url]["key"] for url in members}) == 1:
            continue  # one Shopify product; reported as shopify_handle_moved
        members.sort(key=lambda url: (lifetimes[url]["days"][0], url))
        overlapping = any(
            lifetimes[b]["days"][0] <= lifetimes[a]["days"][-1] for a, b in zip(members, members[1:])
        )
        names = [_latest_name(url, lifetimes, history) for url in members]
        spans = [_span(lifetimes[url]) for url in members]
        if overlapping:
            findings.append(
                _finding(
                    "variant_ambiguity",
                    "false merge",
                    "never joined: listed at the same time, so they are different variants",
                    store,
                    members,
                    "the same name is listed at several URLs at once (size, color, or quantity only in the URL)",
                    names=names,
                    dates=spans,
                )
            )
        else:
            findings.append(
                _finding(
                    "possible_url_churn",
                    "fragmentation",
                    "report only: an equal name is not proof of the same product",
                    store,
                    members,
                    "the same name moved to a new URL; the history restarted",
                    names=names,
                    dates=spans,
                )
            )

    if snapshots:
        findings.extend(_scan_findings(snapshots, lifetimes, gap_days))

    order = {
        "size_changed_same_url": 0,
        "shared_retailer_code": 1,
        "variant_ambiguity": 2,
        "shopify_handle_moved": 3,
        "possible_url_churn": 4,
        "duplicate_in_scan": 5,
        "history_gap": 6,
        "renamed_same_url": 7,
    }
    findings.sort(key=lambda row: (order.get(row["kind"], 99), row["store"], row["urls"]))
    counts = collections.Counter(row["kind"] for row in findings)
    return {"counts": {kind: counts[kind] for kind in order if counts[kind]}, "findings": findings}


def _span(row):
    if not row or not row.get("days"):
        return ""
    return f"{row['days'][0]} to {row['days'][-1]}"


def _latest_name(url, lifetimes, history):
    row = lifetimes.get(url)
    if row and row["names"]:
        return row["names"][-1][1]
    return normalize_product_name((history.get(url) or {}).get("name") or "")


def _scan_findings(snapshots, lifetimes, gap_days):
    """Duplicates inside one scan, and listings that vanished and came back."""
    findings = []
    days_with_key = collections.defaultdict(set)
    for day, catalog in snapshots:
        counts = collections.Counter()
        for key, item in _catalog_rows(catalog):
            days_with_key[key].add(day)
            counts[normalize_url(item.get("url"))] += 1
        for url, count in sorted(counts.items()):
            if count > 1:
                findings.append(
                    _finding(
                        "duplicate_in_scan",
                        "none",
                        "one observation per day is kept",
                        (lifetimes.get(url) or {}).get("store"),
                        [url],
                        f"listed {count} times in one scan",
                        dates=[day],
                    )
                )
    all_days = [day for day, _catalog in snapshots]
    for url, row in sorted(lifetimes.items()):
        key = f"{row['store']}_{row['part']}"
        seen = set(row["days"])
        present = [day for day in all_days if day in seen]
        if len(present) < 2:
            continue
        start = all_days.index(present[0])
        end = all_days.index(present[-1])
        missed = []
        gaps = []
        for day in all_days[start : end + 1]:
            if day in seen:
                if len(missed) >= gap_days:
                    gaps.append((missed[0], missed[-1], len(missed), _price_on(row, missed[0], before=True), _price_on(row, day)))
                missed = []
            elif day in days_with_key.get(key, ()):
                missed.append(day)
        if gaps:
            longest = max(gaps, key=lambda gap: gap[2])
            findings.append(
                _finding(
                    "history_gap",
                    "none",
                    "history continues on the same URL; the gap has no daily points",
                    row["store"],
                    [url],
                    f"{len(gaps)} gap(s); longest {longest[2]} scan days, back at {longest[4]} (was {longest[3]})",
                    names=[row["names"][-1][1]] if row["names"] else [],
                    dates=[f"{first} to {last}" for first, last, _n, _b, _a in gaps],
                )
            )
    return findings


def _price_on(row, day, before=False):
    prices = row.get("prices") or []
    chosen = None
    for when, price in prices:
        if (when < day) if before else (when == day):
            chosen = price
    return chosen if chosen is not None else "?"


def load_git_snapshots(repo=".", path="previous_data.json", limit=None):
    """``(date, catalog)`` for every commit of ``path``, oldest first."""
    import json
    import subprocess

    log = subprocess.run(
        ["git", "-C", repo, "log", "--format=%H %ad", "--date=format:%Y-%m-%dT%H%M", "--", path],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split("\n")
    commits = [line.split(" ", 1) for line in log if line.strip()]
    if limit:
        commits = commits[: int(limit)]
    snapshots = []
    for sha, stamp in reversed(commits):
        shown = subprocess.run(
            ["git", "-C", repo, "show", f"{sha}:{path}"],
            capture_output=True,
            text=True,
        )
        if shown.returncode != 0:
            continue
        try:
            snapshots.append((stamp, json.loads(shown.stdout)))
        except ValueError:
            continue
    return snapshots


def _print_report(report, examples):
    print("Price history identity audit")
    for kind, count in report["counts"].items():
        print(f"  {kind}: {count}")
    shown = collections.Counter()
    for finding in report["findings"]:
        if shown[finding["kind"]] >= examples:
            continue
        shown[finding["kind"]] += 1
        print(f"\n[{finding['kind']}] risk: {finding['risk']}. {finding['detail']}")
        print(f"  action: {finding['action']}")
        for index, url in enumerate(finding["urls"]):
            name = finding["names"][index] if index < len(finding["names"]) and len(finding["names"]) == len(finding["urls"]) else ""
            when = finding["dates"][index] if index < len(finding["dates"]) and len(finding["dates"]) == len(finding["urls"]) else ""
            print(f"  {url}" + (f"  ({when})" if when else "") + (f"  {name}" if name else ""))
        if len(finding["names"]) != len(finding["urls"]):
            for index, name in enumerate(finding["names"]):
                when = finding["dates"][index] if index < len(finding["dates"]) else ""
                print(f"    {when}  {name}")


if __name__ == "__main__":
    import argparse
    import json
    import os

    here = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--git", action="store_true", help="replay every committed previous_data.json")
    parser.add_argument("--limit", type=int, default=None, help="newest N commits with --git")
    parser.add_argument("--examples", type=int, default=5, help="examples printed per kind")
    parser.add_argument("--json", action="store_true", help="print the full report as JSON")
    args = parser.parse_args()
    with open(os.path.join(here, "price_history.json"), encoding="utf-8") as handle:
        stored = json.load(handle)
    snaps = load_git_snapshots(here, limit=args.limit) if args.git else None
    result = audit_history(stored, snaps)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        _print_report(result, args.examples)
