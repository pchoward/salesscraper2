"""BMX UI configuration. Offer extraction is owned by the BMX adapter."""
FIELDS = (
    {"key": "kind", "label": "Product kind", "param": "bmx_kind", "categories": ()},
    {"key": "wheel_size", "label": "Wheel size (in)", "param": "bmx_wheel", "categories": ("Bikes", "Frames & Forks", "Wheels", "Tires")},
    {"key": "condition", "label": "Condition", "param": "bmx_condition", "categories": ()},
)
