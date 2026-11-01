"""Conservative first-catalog BMX scope/specs; no model-name compatibility guesses.

Initial wheel compatibility is 20/22 inches. Unstated dimensions stay unknown;
explicit electric/race-only products and explicitly other wheel sizes are out.
This module does no fetching and does not change price history or identities.
"""
import re
from decimal import Decimal, InvalidOperation

from product_specs import option_text, text

WHEEL_SIZES = {'12', '14', '16', '18', '20', '22', '24', '26', '27.5', '29'}
ELIGIBLE_WHEELS = {'20', '22'}
_NUMBER = r'(\d+(?:\.\d+)?)'
_INCH = r'(?:["″”]|inches\b|inch\b|in\b)'


def decimal(raw):
    try:
        value = Decimal(str(raw).strip())
        return format(value.normalize(), 'f') if value.is_finite() and value > 0 else None
    except (InvalidOperation, ValueError):
        return None


def wheel_sizes(name, part, description='', product_type=''):
    """Only exact, explicitly wheel-related dimensions; never a top-tube/rise."""
    name = text(name)
    product_type = text(product_type)
    body = text(description)
    found = set()
    for value in re.findall(r'\bwheel\s*(?:size|diameter)\s*[:=]?\s*'+_NUMBER+r'\s*'+_INCH, name+' '+body, re.I):
        found.add(decimal(value))
    # Nominal size in a wheel/tire product title or tire dimensions (20 x 2.4).
    wheel_product = part in ('Wheels', 'Tires') or re.search(r'\brims?\b', product_type+' '+name, re.I)
    if wheel_product:
        for match in re.finditer(r'(?<![\d./])'+_NUMBER+r'\s*'+_INCH, name, re.I):
            tail = name[match.end():]
            if not re.match(r'\s*(?:axle|width|wide|rise|reach|top\s*tube|tt)\b', tail, re.I):
                found.add(decimal(match[1]))
        found.update(decimal(v) for v in re.findall(r'(?<![\d.])'+_NUMBER+r'\s*[x×]\s*\d+(?:\.\d+)?', name, re.I))
    elif part == 'Bikes' or re.search(r'\bforks?\b', product_type+' '+name, re.I):
        # Bike/fork nominal wheel size, but not labeled frame/top-tube lengths.
        for match in re.finditer(r'(?<![\d./])'+_NUMBER+r'\s*'+_INCH, name, re.I):
            if not re.search(r'(?:top\s*tube|\btt|length|rise)\s*[:=]?\s*$', name[:match.start()], re.I) and not re.match(r'\s*(?:top\s*tube|tt|length|rise)\b', name[match.end():], re.I):
                found.add(decimal(match[1]))
    elif re.search(r'\bframe\s*(?:&|and)\s*fork\s*kit\b', name, re.I):
        found.update(decimal(v) for v in re.findall(_NUMBER+r'\s*'+_INCH, name, re.I))
    return sorted(found & WHEEL_SIZES, key=Decimal)


def scope_reason(name, part, description='', product_type=''):
    content = text(name)+' '+text(product_type)
    if re.search(r'\b(?:electric\s+(?:bike|bicycle)|e[- ]?(?:bike|bmx))\b', content, re.I):
        return 'electric bike outside BMX freestyle scope'
    # SE RACING is a brand; a brand token alone is never a race-only claim.
    if re.search(r'\b(?:bmx\s+race\s+(?:bike|frame|fork)|race[- ]only|racing[- ]only|race[- ]specific|not\s+for\s+freestyle)\b', content+' '+text(description), re.I):
        return 'explicit race-only equipment'
    sizes = wheel_sizes(name, part, description, product_type)
    if sizes and not set(sizes) & ELIGIBLE_WHEELS:
        return 'wheel compatibility outside initial 20/22-inch scope: '+', '.join(sizes)
    return None


OPTION_FIELDS = {
    'wheel size': ('wheel_size_inches', 'in', 12, 29),
    'wheel diameter': ('wheel_size_inches', 'in', 12, 29),
    'top tube': ('top_tube_inches', 'in', 10, 30),
    'top tube length': ('top_tube_inches', 'in', 10, 30),
    'toptube length': ('top_tube_inches', 'in', 10, 30),
    'bar rise': ('bar_rise_inches', 'in', 1, 15),
    'rise': ('bar_rise_inches', 'in', 1, 15),
    'crank length': ('crank_length_mm', 'mm', 80, 250),
    'axle diameter': ('axle_mm', 'mm', 8, 25),
    'axle size': ('axle_mm', 'mm', 8, 25),
}


def specifications(name, part, description='', product_type='', options=()):
    """(specs, warnings) from exact named fields. Ranges/unknown units omitted."""
    specs = {}
    warnings = []
    wheels = wheel_sizes(name, part, description, product_type)
    if wheels:
        specs['wheel_size_inches'] = wheels
    # Explicit labeled manufacturer values in title/specification text only.
    plain = text(name)+'; '+text(description)
    pairs = list(options)
    for label, (key, unit, low, high) in OPTION_FIELDS.items():
        pattern = r'\b'+re.escape(label)+r'\s*[:=]\s*'+_NUMBER+r'\s*('+_INCH+r'|mm\b)'
        pairs.extend((label, m[1]+m[2]) for m in re.finditer(pattern, plain, re.I))
    labeled = {}
    for label, raw in pairs:
        label = re.sub(r'\s+', ' ', str(label).lower().replace('_', ' ').replace('-', ' ')).strip()
        if label in ('size', 'diameter') and part in ('Wheels', 'Tires'):
            label = 'wheel size'
        if label not in OPTION_FIELDS:
            continue
        field, unit, low, high = OPTION_FIELDS[label]
        value = text(raw).strip()
        match = re.fullmatch(_NUMBER+r'\s*('+_INCH+r'|mm)?', value, re.I)
        if not match or not match[2]:
            continue
        stated_unit = (match[2] or '').lower()
        if stated_unit and ((unit == 'mm' and stated_unit != 'mm') or (unit == 'in' and stated_unit == 'mm')):
            continue
        number = decimal(match[1])
        if not number or not low <= Decimal(number) <= high:
            continue
        if field == 'wheel_size_inches' and number not in WHEEL_SIZES:
            continue
        labeled.setdefault(field, set()).add(number)
    for field, values in labeled.items():
        existing = set(specs.get(field, []))
        if existing and existing != values:
            specs.pop(field, None)
            warnings.append('conflicting '+field)
        elif len(values) > 1:
            warnings.append('conflicting '+field)
        else:
            specs[field] = sorted(values, key=Decimal)
    return specs, warnings


def variant_specs(product, variant, part):
    return specifications(product.get('title',''), part, product.get('body_html',''),
                          product.get('product_type',''), option_text(product, variant))
