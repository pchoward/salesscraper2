"""MTB-owned specification field definitions; rendering is shared."""
FIELDS = (
    {"key": "wheel_size", "label": "Wheel size (in)", "param": "mtb_wheel", "categories": ("Bikes", "Frames", "Forks & Shocks", "Wheels", "Tires")},
    {"key": "travel_mm", "label": "Suspension travel (mm)", "param": "mtb_travel", "categories": ("Bikes", "Frames", "Forks & Shocks")},
    {"key": "frame_size", "label": "Frame size", "param": "mtb_frame", "categories": ("Bikes", "Frames")},
    {"key": "tire_width", "label": "Tire width (in)", "param": "mtb_tirewidth", "categories": ("Tires",)},
    {"key": "axle", "label": "Axle / spacing", "param": "mtb_axle", "categories": ("Frames", "Forks & Shocks", "Wheels")},
    {"key": "rotor_mm", "label": "Rotor diameter (mm)", "param": "mtb_rotor", "categories": ("Brakes",)},
    {"key": "riding_type", "label": "Riding type", "param": "mtb_ride", "categories": ()},
)

# Compatibility for callers on the original MTB branch.
def payload(data):
    import sports
    from sports.facets import payload as build
    return build(data, sports.MTB)
