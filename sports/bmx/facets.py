"""BMX UI configuration. Offer extraction is owned by the BMX adapter."""
from sports import protection

FIELDS = (
    {"key": "kind", "label": "Product kind", "param": "bmx_kind", "categories": ()},
    {"key": "wheel_size", "label": "Wheel size (in)", "param": "bmx_wheel", "categories": ("Bikes", "Frames & Forks", "Wheels", "Tires", "Wheels & Hubs", "Tires & Tubes")},
    {"key": "condition", "label": "Condition", "param": "bmx_condition", "categories": ()},
    # Dan's Comp-style filters (docs/multi-sport-plan.md section 3; sports/bmx/dans.py).
    {"key": "hub_type", "label": "Hub Type", "param": "bmx_hub", "categories": ("Bikes", "Wheels", "Wheel Parts", "Wheels & Hubs")},
    {"key": "top_tube", "label": "Toptube Length", "param": "bmx_tt", "categories": ("Bikes", "Frames & Forks")},
    {"key": "drive_side", "label": "Drive Side", "param": "bmx_drive",
     "categories": ("Bikes", "Wheels", "Wheel Parts", "Wheels & Hubs", "Drivetrain")},
    {"key": "bar_rise", "label": "Bar Rise", "param": "bmx_rise", "categories": ("Steering", "Bars & Steering")},
    {"key": "crank_length", "label": "Crank Length", "param": "bmx_crank", "categories": ("Drivetrain",)},
    {"key": "axle", "label": "Axle", "param": "bmx_axle", "categories": ("Bikes", "Frames & Forks", "Wheels", "Wheel Parts", "Wheels & Hubs")},
    {"key": "material", "label": "Material", "param": "bmx_material", "categories": ()},
    {"key": "color", "label": "Color", "param": "bmx_color", "categories": ()},
) + protection.facet_fields("bmx", ("Protection", "Helmets", "Pads & Gloves"))
