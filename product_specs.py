"""Additive product specifications from already-fetched listing/feed data.

No model inference, scale conversion, URL/name changes, or network access.
Variant facts win over titles, which win over an unambiguous description.
Unknown availability stays None; false availability never becomes a live size.
"""
import json
import logging
import math
import re
from bs4 import BeautifulSoup

_NUMBER = r'(?:\d{1,2}[ -]+\d/\d{1,2}|\d{1,2}(?:\.\d{1,4})?)'
_DURO = re.compile(r'\b(\d{2,3})\s*(HD|A|B|D)\b', re.I)
_MM = re.compile(r'(?<![\d.])(\d{2}(?:\.\d+)?)\s*mm\b', re.I)
_WIDTH = re.compile(r'\b(?:deck\s+)?width\s*[:=\-]?\s*('+_NUMBER+r')', re.I)
_DIMENSIONS = re.compile(r'(?<![\d.])('+_NUMBER+r')\s*["″”]?\s*[x×]\s*(?:2\d|3\d)(?:\.\d+)?', re.I)
_WIDTH_UNIT = re.compile(r'(?<![\d.])('+_NUMBER+r')\s*(?:["″”]|inches\b|inch\b|in\b)', re.I)
_SIZE = re.compile(r'^\s*('+_NUMBER+r')\s*(?:["″”]|inches|inch|in|mm)?\s*$', re.I)


def text(value):
    return BeautifulSoup(str(value or ''), 'html.parser').get_text(' ', strip=True)


def numeric(raw):
    fraction = re.fullmatch(r'(\d{1,2})[ -]+(\d)/(\d{1,2})', str(raw))
    if fraction:
        whole, top, bottom = map(int, fraction.groups())
        return whole + top / bottom if 0 < top < bottom else float('nan')
    return float(raw)


def numbers(raw, kind, option=False, description=False):
    raw = text(raw)
    if kind == 'width':
        patterns = (_WIDTH, _DIMENSIONS) if description else (_WIDTH, _DIMENSIONS, _WIDTH_UNIT)
        found = [numeric(m[1]) for p in patterns for m in p.finditer(raw)
                 if not re.match(r'\s*(?:mm|cm)\b', raw[m.end():], re.I)]
        if option and _SIZE.fullmatch(raw) and not re.search(r'\d\s*(?:mm|cm)\b', raw, re.I):
            found.append(numeric(_SIZE.fullmatch(raw)[1]))
        for match in re.finditer(r'\bwidth\s*[:=]?\s*('+_NUMBER+r')\s*[-–/]\s*('+_NUMBER+r')', raw, re.I):
            found.extend(numeric(v) for v in match.groups())
        return sorted({v for v in found if 6.5 <= v <= 12.5})
    raw = re.sub(r'\b\d{2}(?:\.\d+)?\s*[-–]\s*\d{2}(?:\.\d+)?\s*mm\b', '', raw)
    # Contact patch / wheel width are not diameter. Prefer labeled diameter.
    labeled = re.findall(r'\b(?:diameter|wheel size)\s*[:=\-]?\s*(\d{2}(?:\.\d+)?)(?![\d.])(?:\s*mm\b)?(?!\s*(?:cm|inches|inch|in)\b)', raw, re.I)
    cleaned = re.sub(r'\b(?:width|contact\s+patch)\s*[:=\-]?\s*\d+(?:\.\d+)?\s*mm\b', '', raw, flags=re.I)
    found = [float(v) for v in labeled] if labeled else [float(m[1]) for m in _MM.finditer(cleaned)]
    if option and _SIZE.fullmatch(raw):
        found.append(numeric(_SIZE.fullmatch(raw)[1]))
    return sorted({v for v in found if 40 <= v <= 90})


def durometers(raw):
    return list(dict.fromkeys(f'{int(n)}{scale.upper()}' for n, scale in _DURO.findall(text(raw))))


def option_text(product, variant):
    """Only dimension/size options may supply bare numbers; never a color/code."""
    result = []
    options = product.get('options') or []
    for index, option in enumerate(options):
        label = option.get('name', '') if isinstance(option, dict) else str(option)
        value = variant.get(f'option{index+1}')
        if value is not None:
            result.append((label, str(value)))
    for label, value in (variant.get('attributes') or {}).items():
        result.append((str(label), str(value)))
    if not result:
        # Default Shopify variant titles are often the sole size source.
        value = variant.get('title') or variant.get('option1')
        if value and str(value).lower() != 'default title':
            result.append(('Size', str(value)))
    return result


def _variant_specs(product, variant, part):
    values = []
    duros = []
    kind = 'width' if part in ('Decks', 'Completes') else 'diameter'
    for label, value in option_text(product, variant):
        if (kind == 'width' and re.search(r'\b(?:mm|cm)\b', label, re.I)) or (kind == 'diameter' and re.search(r'\b(?:cm|inches|inch|in)\b', label, re.I)):
            continue
        if re.search(r'width|diameter|size|dimension', label, re.I) and not re.search(r'base|length|patch', label, re.I):
            values.extend(numbers(value, kind, option=True))
            if kind == 'width' and '/' in value:
                values.extend(v for token in re.split(r'\s+/\s+', value) for v in numbers(token, kind, option=True))
        # Explicit unit/scale tokens are safe even when the option is unnamed.
        elif not re.search(r'color|colour|sku|code|length|base|patch', label, re.I):
            values.extend(numbers(value, kind))
        if not re.search(r'color|colour|sku|code|length|base|patch', label, re.I):
            duros.extend(durometers(value))
            scale = re.search(r'\b([ABD])\b', label, re.I)
            if scale and re.fullmatch(r'\d{2,3}', value.strip()):
                duros.extend(durometers(value + scale[1]))
    return sorted(set(values)), list(dict.fromkeys(duros))


def _enrich(item, description='', product=None, variants=None):
    """Attach exact fields and per-variant offers, leaving identity/prices alone."""
    if item.get('part') not in ('Decks', 'Completes', 'Wheels'):
        return item
    product = product or {}
    part = item['part']
    kind = 'diameter' if part == 'Wheels' else 'width'
    singular, plural = ('diameter_mm', 'diameters_mm') if kind == 'diameter' else ('width', 'widths')
    name = item.get('name', '')
    named = numbers(name, kind)
    if kind == 'diameter' and not named and not re.search(r'width|patch|\d\s*[-–]\s*\d', name, re.I):
        from part_specs import wheel_specs
        diameter = wheel_specs(name)['diameter_mm']
        named = [diameter] if diameter is not None else []
    if kind == 'width' and not named:
        # The established title-only deck parser accepts bare decimal widths.
        from filters import extract_deck_dimensions
        width = extract_deck_dimensions(name)[0]
        named = [width] if width is not None else []
    described = numbers(description, kind, description=True)
    # A product's marketing paragraph can list a whole range/model family.
    fallback = named if len(named) == 1 else described if not named and len(described) == 1 else []
    named_duros = durometers(name) if part == 'Wheels' else []
    desc_duros = durometers(description) if part == 'Wheels' else []
    explicit_dual = re.search(r'\b(?:durometer|hardness)\s*[:=]?\s*\d{2,3}\s*(?:HD|A|B|D)\s*[/&+]\s*\d{2,3}\s*(?:HD|A|B|D)\b', text(description), re.I)
    fallback_duros = desc_duros if explicit_dual and set(named_duros).issubset(desc_duros) else named_duros or (desc_duros if len(desc_duros) == 1 else [])
    offers, conflicts = [], []
    if len(described) > 1 and not named:
        conflicts.append('ambiguous description size')
    elif len(described) == 1 and named and named != described:
        conflicts.append('description size differs from title; title used')
    for variant in variants or []:
        if not isinstance(variant, dict):
            continue
        sizes, hardness = _variant_specs(product, variant, part)
        if len(sizes) > 1:
            conflicts.append('ambiguous variant size')
            sizes = []
            chosen = []
        else:
            chosen = sizes or fallback
        if hardness and named_duros and set(hardness) != set(named_duros):
            conflicts.append('variant hardness differs from title; explicit option used')
        if sizes and named and sizes != named:
            conflicts.append('variant size differs from title; explicit option used')
        offer = {singular: chosen[0] if len(chosen) == 1 else None,
                 'durometers': hardness or fallback_duros,
                 'variant_id': str(variant.get('id') or ''),
                 'available': variant.get('available') if isinstance(variant.get('available'), bool) else None}
        for src, dst in (('price', 'price'), ('compare_at_price', 'compare_at_price')):
            try:
                amount = float(variant[src])
                if math.isfinite(amount) and amount > 0:
                    offer[dst] = amount
            except (KeyError, TypeError, ValueError):
                pass
        if offer not in offers:
            offers.append(offer)
    eligible = [offer for offer in offers if offer['available'] is not False]
    sizes = sorted({offer[singular] for offer in eligible if offer[singular] is not None}) if offers else fallback
    if offers:
        item.pop(singular, None)
        item.pop(plural, None)
        if part == 'Wheels':
            item.pop('durometers', None)
    if sizes:
        item[plural] = sizes
        if len(sizes) == 1:
            item[singular] = sizes[0]
        else:
            item.pop(singular, None)
    if part == 'Wheels':
        hardness = list(dict.fromkeys(token for offer in eligible for token in offer['durometers'])) if offers else fallback_duros
        if hardness:
            item['durometers'] = hardness
    if offers:
        item['spec_offers'] = offers
    if conflicts:
        item['spec_conflicts'] = sorted(set(conflicts))
    return item


def enrich(item, description='', product=None, variants=None):
    """Optional extraction failures never fail a retailer or partially stamp facts."""
    try:
        enriched = _enrich(dict(item), description, product, variants)
        item.update(enriched)
        # Explicit multi-size results must not retain a misleading scalar.
        for scalar, plural in (('width', 'widths'), ('diameter_mm', 'diameters_mm')):
            if len(enriched.get(plural) or []) > 1 or (enriched.get('spec_offers') and scalar not in enriched):
                item.pop(scalar, None)
            if enriched.get('spec_offers') and plural not in enriched:
                item.pop(plural, None)
        if enriched.get('spec_offers') and 'durometers' not in enriched:
            item.pop('durometers', None)
    except Exception as exc:
        logging.getLogger(__name__).warning('Optional specification extraction skipped (%s)', type(exc).__name__)
    return item


def listing(item, node):
    """Read card-scoped descriptions/options/embedded product data, no requests."""
    if node is None:
        return enrich(item)
    product = {}
    if getattr(node, 'name', None) == 'a':
        parent = node.parent
        if getattr(parent, 'name', None) not in (None, '[document]', 'html', 'body'):
            links = {a.get('href') for a in parent.select('a[href]')}
            if len(links) <= 1:
                node = parent
    if hasattr(node, 'get'):
        raw = node.get('data-product')
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    product = parsed
            except (ValueError, TypeError):
                pass
    description = text(product.get('body_html') or product.get('description') or node.get_text(' ', strip=True))
    variants = product.get('variants') or []
    if not variants and hasattr(node, 'select'):
        # Only actual option selectors, not arbitrary card numbers.
        for select in node.select('select'):
            label = select.get('data-option-name') or select.get('name') or 'Size'
            for option in select.select('option'):
                if option.has_attr('disabled') or not option.get('value') or re.search(r'\b(?:sold out|out of stock|unavailable)\b', option.get_text(' ', strip=True), re.I):
                    continue
                variants.append({'attributes': {label: option.get_text(' ', strip=True)}})
    # Known sold-out or non-sale variants cannot advertise eligible sizes.
    if product.get('variants'):
        variants = [v for v in variants if v.get('available') is not False]
        variants = [v for v in variants if _sale(v)]
    if item.get('store') == 'CCS':
        from stores.ccs import _amount
        variants = [dict(v, **{key: _amount(v[key]) for key in ('price', 'compare_at_price') if key in v}) for v in variants]
    if item.get('part') in ('Decks', 'Completes'):
        item.pop('width', None)  # recompute from scoped, labeled facts rather than nose/tail text
    return enrich(item, description, product, variants)


def _sale(variant):
    try:
        return 0 < float(variant['price']) < float(variant['compare_at_price'])
    except (KeyError, TypeError, ValueError):
        return False
