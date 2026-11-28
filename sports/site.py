"""Shared public metadata and sport links for the homepage and catalogs."""
from html import escape

from sports import SPORTS

SITE_URL = "https://shreddeals.com"
TAGLINE = "Every shop's sale rack for skate, ski, bike and BMX, in one place."
DESCRIPTIONS = {
    "skate": "Skate decks, wheels, trucks, shoes and more on sale at skate shops, updated daily.",
    "ski": "Skis, boots, bindings and more on sale at ski shops, updated daily.",
    "mtb": "Mountain bikes, suspension, drivetrain parts and more on sale at bike shops, updated daily.",
    "bmx": "BMX bikes, frames, wheels and more on sale at BMX shops, updated daily.",
}


def metadata(sport=None):
    title = f"ShredDeals · {sport.label} deals" if sport else "ShredDeals · Gear on sale"
    description = DESCRIPTIONS[sport.id] if sport else TAGLINE
    url = f"{SITE_URL}/{sport.page_path if sport else ''}"
    return "\n".join((
        f"<title>{escape(title)}</title>",
        f'<meta name="description" content="{escape(description)}">',
        f'<meta property="og:title" content="{escape(title)}">',
        f'<meta property="og:description" content="{escape(description)}">',
        '<meta property="og:type" content="website">',
        f'<meta property="og:url" content="{escape(url)}">',
    ))


def sport_link(sport_id, label, href, current, *, tab=False):
    attributes = f' id="sport-{sport_id}"' if tab else ""
    if sport_id == current:
        attributes += ' aria-current="page"'
    return f'<a{attributes} href="{escape(href)}">{escape(label)}</a>'


def catalog_sport_nav(sport, asset_prefix):
    links = "".join(
        sport_link(other.id, other.label, asset_prefix + other.page_path, sport.id)
        for other in SPORTS.values()
    )
    return f'<nav class="catalog-sport-links" aria-label="Sports">{links}</nav>'
