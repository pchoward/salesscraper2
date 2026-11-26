"""Ski UI configuration, modelled on evo's ski filters (owner, 2026-11-02).
Offer extraction is owned by the Ski adapter (sports/ski/stores.py, evo.py)."""
from sports import packs, protection

FIELDS = (
    {"key": "condition", "label": "Condition", "param": "ski_condition", "categories": ("Skis", "Boots", "Bindings")},  # Demo (2026-11-12)
    {"key": "ski_type", "label": "Type", "param": "ski_type", "categories": ("Skis", "Boots", "Bindings")},
    {"key": "length", "label": "Ski length", "param": "ski_length", "categories": ("Skis", "Poles")},
    {"key": "waist", "label": "Waist width (stated or model number)", "param": "ski_waist", "categories": ("Skis",)},
    {"key": "radius", "label": "Turn radius", "param": "ski_radius", "categories": ("Skis",)},
    {"key": "rocker", "label": "Rocker profile", "param": "ski_rocker", "categories": ("Skis",)},
    {"key": "bindings", "label": "Bindings", "param": "ski_bindings", "categories": ("Skis",)},
    {"key": "mondo", "label": "Boot size (Mondo)", "param": "ski_mondo", "categories": ("Boots",)},
    {"key": "flex", "label": "Flex (stated or model number)", "param": "ski_flex", "categories": ("Boots",)},
    {"key": "last", "label": "Last width", "param": "ski_last", "categories": ("Boots",)},
    {"key": "sole", "label": "Binding compatibility", "param": "ski_sole", "categories": ("Boots", "Bindings")},
    {"key": "din", "label": "DIN (stated or model number)", "param": "ski_din", "categories": ("Bindings",)},
    {"key": "brake", "label": "Brake width", "param": "ski_brake", "categories": ("Bindings",)},
    {"key": "walk", "label": "Walk mode", "param": "ski_walk", "categories": ("Boots",)},
    {"key": "closure", "label": "Closure", "param": "ski_closure", "categories": ("Boots",)},  # BOA (2026-11-21)
    {"key": "goggle_size", "label": "Frame size", "param": "ski_gsize", "categories": ("Goggles",),
     "order": ["Small", "Medium", "Large", "XL"]},
    {"key": "goggle_fit", "label": "Fit", "param": "ski_gfit", "categories": ("Goggles",)},
    {"key": "goggle_lens", "label": "Lens", "param": "ski_glens", "categories": ("Goggles",)},
    {"key": "lens_shape", "label": "Lens shape", "param": "ski_lshape", "categories": ("Goggles",),
     "order": ["Cylindrical", "Spherical", "Toric"]},
    {"key": "helmet_shell", "label": "Helmet shell", "param": "ski_shell", "categories": ("Helmets",),
     "order": ["In-mold", "Hard shell", "Hybrid"]},
    # Ability and Condition: skis, boots and bindings only (Grok's list,
    # docs/filters-evo-model.md, 2026-11-21).
    {"key": "ability", "label": "Ability level", "param": "ski_ability", "categories": ("Skis", "Boots", "Bindings")},
    {"key": "gender", "label": "Gender", "param": "ski_gender", "categories": (),
     "order": ["Men", "Women", "Unisex", "Kids"]},
) + protection.facet_fields("ski", ("Helmets", "Protection", "Gloves")) + (packs.facet_field("ski"),)  # not Goggles: helmet/armor fields

# Section order per heading (docs/filters-evo-model.md): Brand comes first on
# the page, then these, in this order; Condition last. A field not listed for
# a heading keeps its place after the listed ones. Boots and Bindings need
# opposite orders, so the order can't be one tuple.
ORDER = {
    "Skis": ("length", "gender", "waist", "ski_type", "ability", "rocker", "bindings", "radius", "condition"),
    "Boots": ("mondo", "gender", "flex", "last", "ski_type", "ability", "sole", "walk", "closure", "condition"),
    "Bindings": ("din", "brake", "gender", "sole", "ability", "ski_type", "condition"),
    "Poles": ("length", "gender"),
    "Goggles": ("gender", "goggle_size", "goggle_fit", "goggle_lens", "lens_shape"),
    "Helmets": ("prot_size", "gender", "rotational", "certification", "age", "helmet_shell", "helmet_style", "protects"),
    "Protection": ("prot_size", "gender", "protects", "certification", "age", "helmet_style", "rotational"),
    "Gloves": ("prot_size", "gender", "protects", "age", "certification", "helmet_style", "rotational"),
}


def rank(key):
    """"Skis:2 Boots:6 Bindings:7": a field's position on each heading that
    orders it, for the sidebar's data-rank."""
    return " ".join(f"{heading}:{keys.index(key) + 1}" for heading, keys in ORDER.items() if key in keys)
