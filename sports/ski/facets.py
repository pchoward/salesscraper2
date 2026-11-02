"""Ski UI configuration. Offer extraction is owned by the Ski adapter."""
FIELDS = (
    {"key": "length", "label": "Ski length", "param": "ski_length", "categories": ("Skis", "Poles")},
    {"key": "mondo", "label": "Boot size (Mondo)", "param": "ski_mondo", "categories": ("Boots",)},
    {"key": "style", "label": "Style", "param": "ski_style", "categories": ()},
    {"key": "gender", "label": "Gender", "param": "ski_gender", "categories": ()},
)
