"""Bounded Shopify inventory snapshots with variant-level observed history.

The adapter uses the same public collection protocol as stores.shopify, but
intentionally does not call or relax its sale-only projection. No network I/O
occurs here: callers inject a policy-checked page reader.
"""
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import re
import time
from urllib.parse import quote, urlencode, urlsplit

SCHEMA_VERSION = 1
PAGE_LIMIT = 250


def money(value):
    """Shopify collection JSON amounts are major-unit strings, never cents."""
    if not isinstance(value, str):
        raise ValueError('Expected a major-unit price string')
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError('Invalid price') from exc
    if not result.is_finite() or result < 0 or result.as_tuple().exponent < -2:
        raise ValueError('Invalid price')
    return format(result.quantize(Decimal('.01')), 'f')


def validate(scope):
    for key in ('id', 'sport', 'category', 'discipline'):
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', scope[key]):
            raise ValueError('Invalid scope ' + key)
    if not scope['sources']:
        raise ValueError('A scope needs explicit sources')
    names = set()
    for source in scope['sources']:
        if source['id'] in names:
            raise ValueError('Duplicate source')
        names.add(source['id'])
        parts = urlsplit(source['base'])
        if parts.scheme != 'https' or not parts.hostname or parts.username or parts.port or parts.path not in ('', '/') or parts.query or parts.fragment:
            raise ValueError('Expected an HTTPS retailer origin')
        if not re.fullmatch(r'[a-z0-9-]+', source['collection']):
            raise ValueError('Expected a bounded collection handle')
        if not source['product_types'] or not source['market'] or not re.fullmatch('[A-Z]{3}', source['currency']):
            raise ValueError('Missing source identity or eligibility')
        if not 1 <= source.get('max_pages', 4) <= 20:
            raise ValueError('Invalid page budget')


def identity(source, product_id, variant_id):
    """Sale state, collection, scope and display names never enter identity."""
    values = [urlsplit(source['base']).hostname, str(product_id), str(variant_id), source['market'], source['currency']]
    return sha256(json.dumps(values, separators=(',', ':')).encode()).hexdigest()


def offers_for(scope, source, product, observed):
    if not isinstance(product, dict):
        raise ValueError('Invalid product object')
    if not product.get('id') or not re.fullmatch(r'[A-Za-z0-9-]+', str(product.get('handle', ''))):
        raise ValueError('Missing stable Shopify product identity')
    product_type = str(product.get('product_type', '')).casefold().strip()
    if product_type not in {value.casefold() for value in source['product_types']}:
        return []
    # Eligibility is explicit structured evidence, not wheel diameter or title keywords.
    tags = product.get('tags', [])
    if isinstance(tags, str):
        tags = [tag.strip() for tag in tags.split(',')]
    required = source.get('required_tags', [])
    if required and not {str(tag).casefold() for tag in tags}.intersection(tag.casefold() for tag in required):
        return []
    if not isinstance(product.get('title'), str) or not product['title'].strip():
        raise ValueError('Missing product title')
    options = product.get('options', [])
    if not isinstance(options, list) or any(not isinstance(option, dict) for option in options):
        raise ValueError('Invalid variant option definitions')
    variants = product.get('variants')
    if not isinstance(variants, list) or not variants:
        raise ValueError('Missing variants')
    result = []
    for variant in variants:
        if not isinstance(variant, dict):
            raise ValueError('Invalid variant object')
        if not variant.get('id'):
            raise ValueError('Missing stable variant identity')
        price = money(variant.get('price'))
        if Decimal(price) <= 0:
            raise ValueError('Missing positive offer price')
        compare = variant.get('compare_at_price')
        compare = money(compare) if compare not in (None, '') else None
        compare = compare if compare and Decimal(compare) > Decimal(price) else None
        available = variant.get('available')
        available = available if type(available) is bool else None
        specs = {}
        for option in options:
            axis = source.get('spec_options', {}).get(str(option.get('name', '')).casefold())
            position = option.get('position')
            if axis and position in (1, 2, 3):
                value = variant.get('option' + str(position))
                if value and value != 'Default Title':
                    specs[axis] = str(value)
        result.append(dict(id=identity(source, product['id'], variant['id']),
                           product_id=str(product['id']), variant_id=str(variant['id']),
                           sport=scope['sport'], category=scope['category'], discipline=scope['discipline'],
                           title=str(product.get('title', '')), brand=str(product.get('vendor', '')),
                           store=source['id'], market=source['market'], currency=source['currency'],
                           price=price, compare_at=compare, available=available, specs=specs,
                           url=source['base'].rstrip('/') + '/products/' + quote(product['handle']) + '?' + urlencode({'variant': variant['id']}),
                           observed_at=observed, provenance={'adapter': 'shopify-collection', 'source': source['collection'],
                           'price': 'variant.price', 'compare_at': 'variant.compare_at_price' if compare else None,
                           'stock': 'variant.available' if available is not None else 'unknown'}))
    return result


def capture(scope, read_page, observed, previous=None):
    """All configured sources must terminate. A partial run keeps last-good data.

    read_page(source, page, limit) -> Shopify JSON dict. It must raise for
    denied/unverified policy, timeout, HTTP failure, or invalid JSON.
    """
    validate(scope)
    if previous and (previous.get('schema_version') != SCHEMA_VERSION or previous.get('scope') != scope['id']):
        raise ValueError('Incompatible previous state')
    started = time.monotonic()
    manifests, offers = [], {}
    for source in scope['sources']:
        manifest = dict(source=source['id'], collection=source['collection'], pages=0, products=0,
                        complete=False, error=None)
        seen = set()
        try:
            for number in range(1, source.get('max_pages', 4) + 1):
                payload = read_page(source, number, PAGE_LIMIT)
                manifest['pages'] += 1
                if not isinstance(payload, dict):
                    raise ValueError('Invalid collection object')
                rows = payload.get('products')
                if not isinstance(rows, list) or len(rows) > PAGE_LIMIT:
                    raise ValueError('Invalid collection payload')
                for product in rows:
                    if not isinstance(product, dict):
                        raise ValueError('Invalid product object')
                    pid = str(product.get('id', ''))
                    if not pid or pid in seen:
                        raise ValueError('Repeated or missing product identity; pagination unverified')
                    seen.add(pid)
                    manifest['products'] += 1
                    for offer in offers_for(scope, source, product, observed):
                        old = offers.get(offer['id'])
                        if old and any(old[key] != offer[key] for key in ('price', 'compare_at', 'available', 'specs')):
                            raise ValueError('Conflicting duplicate offer')
                        offers.setdefault(offer['id'], offer)
                if len(rows) < PAGE_LIMIT:
                    manifest['complete'] = True
                    break
            if not manifest['complete']:
                raise ValueError('Page budget reached before terminal page')
        except (ValueError, OSError, RuntimeError) as exc:
            manifest['error'] = str(exc)[:300]
        manifests.append(manifest)
    complete = all(item['complete'] for item in manifests)
    if complete:
        history = deepcopy((previous or {}).get('history', {}))
        day = observed[:10]
        for offer in offers.values():
            # Sold-out and unknown-stock prices do not represent purchasable observations.
            if offer['available'] is not True:
                continue
            series = history.setdefault(offer['id'], {'currency': offer['currency'], 'market': offer['market'], 'points': []})
            points = [point for point in series['points'] if point['day'] != day]
            points.append({'day': day, 'price': offer['price']})
            series['points'] = sorted(points, key=lambda point: point['day'])[-90:]
            series['last_observed_at'] = observed
            series['observed_low'] = min(series.get('observed_low', offer['price']), offer['price'], key=Decimal)
            series['observed_high'] = max(series.get('observed_high', offer['price']), offer['price'], key=Decimal)
        # Bound identities as well as observations: retain absent offers for 180 days.
        from datetime import date
        history = {key: value for key, value in history.items()
                   if (date.fromisoformat(day) - date.fromisoformat(value['last_observed_at'][:10])).days <= 180}
        state = dict(schema_version=SCHEMA_VERSION, scope=scope['id'], offers=list(offers.values()), history=history,
                     last_success=observed, stale=False)
    else:
        state = deepcopy(previous) if previous else dict(schema_version=SCHEMA_VERSION, scope=scope['id'], offers=[], history={}, last_success=None)
        state['stale'] = True
    state['attempted_at'] = observed
    state['manifest'] = manifests
    state['metrics'] = {'pages': sum(item['pages'] for item in manifests),
                        'products_read': sum(item['products'] for item in manifests),
                        'offers': len(state['offers']), 'elapsed_seconds': round(time.monotonic() - started, 3)}
    state['metrics']['serialized_bytes'] = 0
    # Include the size field itself in the metric.
    for _ in range(4):
        state['metrics']['serialized_bytes'] = len(json.dumps(state, sort_keys=True, separators=(',', ':')).encode())
    return state


def available_offers(state, **specs):
    """Every selected specification must match the same verified in-stock offer."""
    return [offer for offer in state['offers'] if offer['available'] is True
            and all(offer['specs'].get(key) == value for key, value in specs.items())]
