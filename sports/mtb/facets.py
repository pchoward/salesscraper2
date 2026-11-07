"""MTB-owned specification field definitions; rendering is shared."""
from sports import protection

FIELDS = (
    {"key": "wheel_size", "label": "Wheel size (in)", "param": "mtb_wheel", "categories": ("Bikes", "Frames", "Forks & Shocks", "Suspension", "Wheels", "Tires")},
    {"key": "travel_mm", "label": "Suspension travel (mm)", "param": "mtb_travel", "categories": ("Bikes", "Frames", "Forks & Shocks", "Suspension")},
    {"key": "frame_size", "label": "Frame size", "param": "mtb_frame", "categories": ("Bikes", "Frames")},
    {"key": "tire_width", "label": "Tire width (in)", "param": "mtb_tirewidth", "categories": ("Tires",)},
    {"key": "axle", "label": "Axle / spacing", "param": "mtb_axle", "categories": ("Frames", "Forks & Shocks", "Suspension", "Wheels")},
    {"key": "rotor_mm", "label": "Rotor diameter (mm)", "param": "mtb_rotor", "categories": ("Brakes",)},
    {"key": "speed", "label": "Speed", "param": "mtb_speed", "categories": ("Drivetrain", "Bikes"),
     "order": ["13-speed", "12-speed", "11-speed", "10-speed", "9-speed", "8-speed", "7-speed"]},
    {"key": "casing", "label": "Casing", "param": "mtb_casing", "categories": ("Tires",)},
    {"key": "tubeless", "label": "Tubeless", "param": "mtb_tubeless", "categories": ("Tires",)},
    {"key": "riding_type", "label": "Riding type", "param": "mtb_ride", "categories": ()},
) + protection.facet_fields("mtb", ("Protection", "Helmets", "Goggles", "Gloves"))

# Compatibility for callers on the original MTB branch.
def payload(data):
    import sports
    from sports.facets import payload as build
    return build(data, sports.MTB)
