"""evo's skate sale (evo.com, Shopify) on the Skate tab (owner, 2026-11-26).

evo was read only for MTB and Ski (sports/mtb/stores.py, sports/ski/stores.py)
until the owner found Bronson G3 pro bearings at $19.47 (was $37.95) there
and nowhere on Skate. evo's skate collections hold about 960 skateboards
(535 marked down) and 665 parts (308 marked down) on 2026-11-26; robots.txt
allows the collection feeds (it disallows only sorted and "+" filtered
collection URLs, which are never requested).

Read with the shared Shopify code. Only skate types map to a part; the
usual Skate rules apply (minimum discount, deck width, cruisers and
longboards out, the wheel, truck and bearing brand lists, tracked shoes).
Longboard wheels, trucks and grip are left unmapped on purpose.

``python -m stores.evo_skate`` previews what a run would keep.
"""

from stores import shopify

SHOP = shopify.ShopifyStore(
    "evo",
    "evo",
    "https://www.evo.com",
    collection="skateboards",
    more_collections=("skateboard-parts", "skateboard-helmets", "skateboard-backpacks", "skateboard-shoes"),
    extra_types={
        "skateboard decks": "Decks",
        "skateboard completes": "Completes",
        # Cruisers and longboards: the Skate rules drop them by name; mapped so
        # the drop is counted rather than silently unread.
        "cruiser complete": "Completes",
        "longboard completes": "Completes",
        "skateboard wheels": "Wheels",
        "skateboard trucks": "Trucks",
        "skate tools": "Accessories",
        "cushions": "Accessories",
        "skate helmets": "Protection",
        "backpacks": "Packs",
        "day packs": "Packs",
        # Snow packs: the pack rules keep them on Ski.
        "snowboard backpacks": "Packs",
        "ski snowboard backpacks": "Packs",
        "shoes": "Sneakers",
    },
    own_vendor="evo",
)


def scrapers():
    return shopify.scrapers_for(SHOP)


if __name__ == "__main__":
    raise SystemExit(shopify.preview(SHOP))
