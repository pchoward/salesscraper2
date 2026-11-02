"""Per-variant spec offers for the sidebar spec filters (sports/facets.py,
previews/sport-filters.js), in the format the MTB adapter uses:

    item["technical_offers"] = [{"variant_id", "price", "compare", "available",
                                 "specs": {key: [values]}}, ...]
    item["technical_specs"]  = {key: [values across offers]}

A filter matches a listing when one of its buyable sale variants has the value,
and the card can show that variant's price. Specs are only what the store
states; a key is left out when unknown.
"""

from stores import shopify


def technical_offers(variants, variant_specs=None, shared=None):
    """Offers for these sale variants. ``variant_specs(variant)`` gives one
    variant's own specs (a ski's length); ``shared`` applies to every variant
    (a hub's type)."""
    shared = {key: sorted({str(value) for value in values}) for key, values in (shared or {}).items() if values}
    offers = []
    for variant in variants or ():
        price = shopify._amount(variant.get("price"))
        compare = shopify._amount(variant.get("compare_at_price"))
        if price is None or compare is None:
            continue
        specs = dict(shared)
        for key, values in ((variant_specs(variant) if variant_specs else None) or {}).items():
            if values:
                specs[key] = sorted({str(value) for value in values})
        available = variant.get("available")
        offers.append({"variant_id": variant.get("id"), "price": float(price), "compare": float(compare),
                       "available": available if isinstance(available, bool) else None, "specs": specs})
    return offers


def attach(item, offers):
    """Put the offers and their combined specs on the listing."""
    if not offers:
        return
    item["technical_offers"] = offers
    combined = {}
    for offer in offers:
        for key, values in offer["specs"].items():
            combined.setdefault(key, set()).update(values)
    if combined:
        item["technical_specs"] = {key: sorted(values) for key, values in combined.items()}
