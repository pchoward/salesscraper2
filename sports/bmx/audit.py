"""Offline classification and price-evidence audit for a saved BMX catalog."""
from copy import deepcopy
from decimal import Decimal

from history import summarize_entry
from sports.bmx.quality import decimal, scope_reason, specifications


def price_evidence(item, history):
    """Compare-at is retailer metadata, never an earlier observed sale price."""
    current, compare = decimal(item.get('price_new')), decimal(item.get('price_old'))
    points = summarize_entry((history or {}).get(item.get('url'), {}))['prices']
    observed = sorted(points.items())
    prior = decimal(observed[-2][1]) if len(observed) > 1 else None
    latest = decimal(observed[-1][1]) if observed else None
    drop = prior is not None and latest is not None and Decimal(latest) < Decimal(prior)
    percent = None
    if current and compare and Decimal(compare) > Decimal(current):
        percent = round(float((Decimal(compare)-Decimal(current))/Decimal(compare)*100), 2)
    return {'retailer_compare_at': compare, 'current_price': current,
            'retailer_markdown_percent': percent, 'observations': len(points),
            'previous_observed_price': prior, 'observed_price_drop': drop,
            'history_matches_current': current is not None and latest == current}


def classify(data, history=None):
    kept = {}
    excluded = []
    for key, items in data.items():
        kept[key] = []
        for original in items:
            item = deepcopy(original)
            reason = scope_reason(item.get('name',''), item.get('part',''), item.get('description',''), item.get('product_type',''))
            if reason:
                excluded.append({'url': item.get('url'), 'name': item.get('name'), 'category': item.get('part'), 'reason': reason})
                continue
            specs, conflicts = specifications(item.get('name',''), item.get('part',''), item.get('description',''), item.get('product_type',''))
            item['bmx_specs'] = specs
            item['price_basis'] = 'retailer_compare_at'
            if conflicts:
                item['bmx_spec_warnings'] = conflicts
            kept[key].append(item)
    report = {'before': {k: len(v) for k,v in data.items()}, 'after': {k:len(v) for k,v in kept.items()},
              'excluded': excluded,
              'price_evidence': {i['url']: price_evidence(i, history or {}) for values in kept.values() for i in values},
              'specs_known': sum(bool(i['bmx_specs']) for values in kept.values() for i in values),
              'specs_unknown': sum(not i['bmx_specs'] for values in kept.values() for i in values)}
    return kept, report
