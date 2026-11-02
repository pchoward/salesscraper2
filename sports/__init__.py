"""The sports ShredDeals covers: one engine, one catalog per sport.

Each sport says what is different about it: the category chips, branding,
where its data and public page live, its search vocabulary, its stores, and
whether its run sends email or alerts. Everything else (price history,
health checks, sale detection, the page itself) is shared.

Skate is today's SkateDeals, unchanged: its data files stay at the
repository root and its page at sale_items_chart.html, so every existing
link, alert and workflow keeps working. Other sports keep their data under
catalogs/<id>/ (not published) and their page under <id>/ (published).
docs/multi-sport-plan.md has the plan.

    python scraper.py --sport bmx
    python rebuild_page.py --sport bmx
"""

import contextlib
import importlib
import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Sport:
    id: str
    label: str
    # Shown in the page title and header.
    brand: str
    # Category chips, in order.
    parts: tuple
    # The category a fresh visit opens on; "all" for every category.
    default_part: str
    # State files (previous_data.json, price_history.json, scrape_health.json,
    # site_sales.json, report_inputs.json): the run works in this folder.
    data_dir: str
    # The public page; its history.json is written next to it.
    page_path: str
    # Search vocabulary (search/aliases.json's format).
    aliases: str
    # "module:function" returning this sport's scrapers.
    scrapers: str
    # "module:function" with filters.filter_reason's signature: which listings
    # belong in the catalog. Empty for Skate's own rules (filters.py).
    rules: str = ""
    # Owner digest, notification engine and subscriber alerts.
    delivery: bool = False
    # Product-page lookups that only Skate's stores support (deck wheelbase).
    product_details: bool = False

    @property
    def is_default(self):
        return self.id == "skate"

    def data_path(self):
        return ROOT / self.data_dir

    def page_file(self):
        return ROOT / self.page_path

    def aliases_file(self):
        return ROOT / self.aliases

    def build_scrapers(self):
        module, _, function = self.scrapers.partition(":")
        return getattr(importlib.import_module(module), function)()

    def _rules(self):
        if not self.rules:
            return None
        module, _, function = self.rules.partition(":")
        return getattr(importlib.import_module(module), function)

    @contextlib.contextmanager
    def active(self):
        """This sport's listing rules for the duration (rendering a page)."""
        import filters

        previous = filters.use_sport_rules(self._rules())
        try:
            yield self
        finally:
            filters.use_sport_rules(previous)

    @contextlib.contextmanager
    def session(self, folder=None):
        """For a whole run: work in this sport's data folder (created when
        missing; ``folder`` overrides it) under its listing rules, then put
        both back. Every state file and side file (site sales, watchlist) is
        read relative to it. Skate's run is unchanged: its files are at the
        repository root."""
        if self.is_default:
            yield self
            return
        import filters

        folder = Path(folder) if folder is not None else self.data_path()
        folder.mkdir(parents=True, exist_ok=True)
        before = os.getcwd()
        previous = filters.use_sport_rules(self._rules())
        os.chdir(folder)
        try:
            yield self
        finally:
            os.chdir(before)
            filters.use_sport_rules(previous)


SKATE = Sport(
    id="skate",
    label="Skate",
    brand="SkateDeals",
    parts=("Decks", "Trucks", "Wheels", "Bearings", "Sneakers", "Accessories", "Completes", "Protection"),
    default_part="Decks",
    data_dir=".",
    page_path="sale_items_chart.html",
    aliases="search/aliases.json",
    scrapers="stores.registry:build_scrapers",
    delivery=True,
    product_details=True,
)

# Categories follow Dan's Comp and Circuit BMX (docs/multi-sport-plan.md).
BMX = Sport(
    id="bmx",
    label="BMX",
    brand="ShredDeals BMX",
    parts=("Bikes", "Frames & Forks", "Steering", "Drivetrain", "Wheels", "Wheel Parts", "Tires", "Seating", "Braking"),
    default_part="all",
    data_dir="catalogs/bmx",
    page_path="bmx/sale_items_chart.html",
    aliases="sports/bmx/aliases.json",
    scrapers="sports.bmx.stores:scrapers",
    rules="sports.rules:bmx",
)

# Gear West's alpine closeouts first (store probe, 2026-11-01).
SKI = Sport(
    id="ski",
    label="Ski",
    brand="ShredDeals Ski",
    # Issue #134: alpine skiing first; snowboards are a separate, later decision.
    parts=("Skis", "Boots", "Bindings", "Poles", "Helmets"),
    default_part="all",
    data_dir="catalogs/ski",
    page_path="ski/sale_items_chart.html",
    aliases="sports/ski/aliases.json",
    scrapers="sports.ski.stores:scrapers",
    rules="sports.rules:ski",
)

# Ready for catalogs: categories, folders and rules are set; no stores yet,
# so a run builds an empty page and the homepage keeps "coming soon".
MTB = Sport(
    id="mtb",
    label="MTB",
    brand="ShredDeals MTB",
    parts=("Bikes", "Frames", "Forks & Shocks", "Wheels", "Tires", "Drivetrain", "Brakes", "Cockpit", "Pedals",
           "Protection"),
    default_part="all",
    data_dir="catalogs/mtb",
    page_path="mtb/sale_items_chart.html",
    aliases="sports/mtb/aliases.json",
    scrapers="sports:no_stores",
    rules="sports.rules:mtb",
)

SPORTS = {sport.id: sport for sport in (SKATE, SKI, MTB, BMX)}


def no_stores():
    return []


def get(sport_id=None):
    """The sport by id; Skate when none is given. Unknown ids raise KeyError."""
    return SPORTS[sport_id or "skate"]


def published_catalogs(root=None):
    """{sport id: page path} for the other sports whose catalog has listings and
    whose page exists under ``root`` (the repository by default): the
    homepage's tabs open these, and the rest keep "coming soon"."""
    import json

    root = Path(root) if root is not None else ROOT
    found = {}
    for sport in SPORTS.values():
        if sport.is_default or not (root / sport.page_path).is_file():
            continue
        try:
            data = json.loads((root / sport.data_dir / "previous_data.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if any(items for items in data.values()):
            found[sport.id] = sport.page_path
    return found
