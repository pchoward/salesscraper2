"""Ski UI configuration, modelled on evo's ski filters (owner, 2026-11-02).
Offer extraction is owned by the Ski adapter (sports/ski/stores.py, evo.py)."""
from sports import protection

FIELDS = (
    {"key": "condition", "label": "Condition", "param": "ski_condition", "categories": ()},  # Demo (2026-11-12)
    {"key": "ski_type", "label": "Type", "param": "ski_type", "categories": ("Skis", "Boots", "Bindings")},
    {"key": "length", "label": "Ski length", "param": "ski_length", "categories": ("Skis", "Poles")},
    {"key": "waist", "label": "Waist width", "param": "ski_waist", "categories": ("Skis",)},
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
    {"key": "goggle_size", "label": "Frame size", "param": "ski_gsize", "categories": ("Goggles", "Protection"),
     "order": ["Small", "Medium", "Large", "XL"]},
    {"key": "goggle_fit", "label": "Fit", "param": "ski_gfit", "categories": ("Goggles", "Protection")},
    {"key": "goggle_lens", "label": "Lens", "param": "ski_glens", "categories": ("Goggles", "Protection")},
    {"key": "lens_shape", "label": "Lens shape", "param": "ski_lshape", "categories": ("Goggles",),
     "order": ["Cylindrical", "Spherical", "Toric"]},
    {"key": "helmet_shell", "label": "Helmet shell", "param": "ski_shell", "categories": ("Helmets",),
     "order": ["In-mold", "Hard shell", "Hybrid"]},
    {"key": "ability", "label": "Ability level", "param": "ski_ability", "categories": ()},
    {"key": "gender", "label": "Gender", "param": "ski_gender", "categories": (),
     "order": ["Men", "Women", "Unisex", "Kids"]},
) + protection.facet_fields("ski", ("Helmets", "Protection", "Goggles", "Gloves"))
