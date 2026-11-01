"""BMX stores. Each returns scrapers like stores/registry.py's skate stores.

Albe's BMX first: Shopify, with a sale collection of ~750 bikes and parts
(store probe, 2026-11-01). Its product types map to the BMX categories
(sports/__init__.py, grouped like Dan's Comp and Circuit BMX); types not
listed are skipped. ``python -c "from sports.bmx import stores;
stores.preview()"`` shows what a live run would keep without saving anything.
"""

import sports
from sports import brands
from stores import shopify

# Shopify product_type (lowercased, punctuation dropped) -> BMX category.
TYPES = {
    "bmx bikes": "Bikes", "bmx bike": "Bikes", "bikes": "Bikes", "complete bikes": "Bikes",
    "frames": "Frames & Forks", "frame": "Frames & Forks", "forks": "Frames & Forks", "fork": "Frames & Forks",
    "bars": "Steering", "handlebars": "Steering", "stems": "Steering", "stem": "Steering", "grips": "Steering",
    "headsets": "Steering", "headset": "Steering", "bar ends": "Steering", "detanglers": "Steering",
    "gyros": "Steering",
    "cranks": "Drivetrain", "crank": "Drivetrain", "sprockets": "Drivetrain", "sprocket": "Drivetrain",
    "chains": "Drivetrain", "chain": "Drivetrain", "bottom brackets": "Drivetrain", "bottom bracket": "Drivetrain",
    "pedals": "Drivetrain", "chain tensioners": "Drivetrain", "tensioners": "Drivetrain",
    "wheels": "Wheels", "wheel": "Wheels", "wheelsets": "Wheels",
    "hubs": "Wheel Parts", "hub": "Wheel Parts", "rims": "Wheel Parts", "rim": "Wheel Parts",
    "spokes": "Wheel Parts", "spokes nipples": "Wheel Parts", "nipples": "Wheel Parts", "axles": "Wheel Parts",
    "hub guards": "Wheel Parts", "pegs": "Wheel Parts", "drivers": "Wheel Parts", "freewheels": "Wheel Parts",
    "rim strips": "Wheel Parts", "valve caps": "Wheel Parts",
    "tires": "Tires", "tire": "Tires", "tubes": "Tires", "tube": "Tires",
    "seats": "Seating", "seat": "Seating", "seat posts": "Seating", "seat post": "Seating",
    "seatposts": "Seating", "seat clamps": "Seating", "seat post clamps": "Seating",
    "brakes": "Braking", "brake": "Braking", "brake levers": "Braking", "levers": "Braking",
    "brake cables": "Braking", "cables": "Braking", "brake parts": "Braking", "brake pads": "Braking",
    "grips bar ends": "Steering", "bar ends": "Steering", "handlebar": "Steering", "bmx bars": "Steering",
    "bmx frames": "Frames & Forks", "bmx forks": "Frames & Forks", "bmx wheels": "Wheels",
    "bmx tires": "Tires", "bmx hubs": "Wheel Parts", "hubguards": "Wheel Parts", "hub guard": "Wheel Parts",
    "spoke": "Wheel Parts", "rim strip": "Wheel Parts", "valve cap": "Wheel Parts", "peg": "Wheel Parts",
    "seat clamp": "Seating", "seat post clamp": "Seating", "seatpost": "Seating", "seat posts clamps": "Seating",
    "cranksets": "Drivetrain", "crank arms": "Drivetrain", "spindles": "Drivetrain", "chainrings": "Drivetrain",
    "pedal": "Drivetrain", "chain tensioner": "Drivetrain", "bb": "Drivetrain",
}

ALBES = shopify.ShopifyStore(
    "Albe's BMX",
    "Albe's BMX",
    "https://www.albes.com",
    collection="bmx-sale-bikes-parts",
    types=TYPES,
    brand_of=brands.for_sport(sports.BMX),
    own_vendor="albe",  # the shop's own name as a vendor is not a brand
)

PARTS = ("Bikes", "Frames & Forks", "Steering", "Drivetrain", "Wheels", "Wheel Parts", "Tires", "Seating", "Braking")


def scrapers():
    return shopify.scrapers_for(ALBES, PARTS)


def preview():
    import sports

    with sports.BMX.active():
        return shopify.preview(ALBES, PARTS)
