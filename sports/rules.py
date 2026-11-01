"""Which listings belong in each new sport's catalog (filters.filter_reason's signature).

Skate's rules (filters.py) are mostly about what is not a skateboard part:
cruisers, longboards, apparel, wheel brands. The new sports start simpler: a
named listing in one of the sport's categories that is not apparel. Store
adapters choose the sale sections; markdowns are decided there and by the
shared deal checks. A sport outgrows this by getting its own function here.
"""

from filters import normalize_product_name

_APPAREL = ("t-shirt", " tee ", "hoodie", "sweatshirt", "socks", " hat ", "beanie", "sticker", "gift card")


def _basic(sport, name, part):
    name = normalize_product_name(name)
    if not name:
        return "missing name"
    if part not in sport.parts:
        return f"not a {sport.label} category"
    text = f" {name.casefold()} "
    if any(word in text for word in _APPAREL):
        return "apparel"
    return None


def bmx(name, part, url="", price_new=None, price_old=None, description="", product_type=""):
    import sports
    return _basic(sports.BMX, name, part)


def ski(name, part, url="", price_new=None, price_old=None, description="", product_type=""):
    import sports
    return _basic(sports.SKI, name, part)


def mtb(name, part, url="", price_new=None, price_old=None, description="", product_type=""):
    import sports
    return _basic(sports.MTB, name, part)
