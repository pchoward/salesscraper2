"""Append explicitly synthetic UI cases to an isolated ci/build_preview output.

No extractor, retailer, delivery, or source state is invoked or modified.
"""
import argparse
import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import page
import sports
from ci.build_preview import mark_preview
from report import build_report_html


def build(output):
    output = Path(output).resolve()
    if output.is_relative_to(ROOT):
        raise ValueError('Use a preview outside the checkout')
    manifest = {}
    cases = (
        (sports.BMX, 'Frames & Forks', {'wheel_size': ['22'], 'kind': ['Frames']}, {'wheel_size': ['20'], 'kind': ['Forks']}),
        (sports.SKI, 'Skis', {'length': ['170–179 cm'], 'gender': ['Women']}, {'length': ['180–189 cm'], 'gender': ['Men']}),
        (sports.MTB, 'Forks & Shocks', {'wheel_size': ['29'], 'travel_mm': ['160']}, {'wheel_size': ['27.5'], 'travel_mm': ['140']}),
    )
    page.ALERTS_UI_CONFIG = {}
    for sport, part, target, other in cases:
        items = []
        for name in ('match', 'split', 'missing', 'sold-out'):
            item = {'name': 'SYNTHETIC UI ' + name + ' ' + part, 'part': part, 'store': 'AuditFixture',
                    'brand': 'Audit', 'url': 'https://example.test/' + sport.id + '/' + name,
                    'price_new': '100.00', 'price_old': '400.00', 'availability': 'In stock'}
            def offer(key, specs, price=100, available=True):
                return {'variant_id': key, 'price': price, 'compare': 400,
                        'available': available, 'specs': copy.deepcopy(specs)}
            if name == 'match':
                item['technical_offers'] = [offer('other', other), offer('target', target, 250), offer('target-expensive', target, 300)]
            elif name == 'split':
                keys = list(target)
                a, b = copy.deepcopy(other), copy.deepcopy(target)
                a[keys[0]], b[keys[0]] = target[keys[0]], other[keys[0]]
                item['technical_offers'] = [offer('split-a', a), offer('split-b', b, 200)]
            elif name == 'missing':
                item['technical_offers'] = [offer('unknown', {})]
            else:
                item['technical_offers'] = [offer('sold', target, 50, False), offer('available', other)]
            items.append(item)
        with sport.active():
            html = build_report_html({'AuditFixture_' + part: items}, {}, {}, sport=sport,
                                     generated_at='2026-11-02T00:00:00+00:00')
        path = output / 'audit-fixtures' / sport.id / 'sale_items_chart.html'
        path.parent.mkdir(parents=True, exist_ok=True)
        page.write_page(mark_preview(html, 'SYNTHETIC UI QA — NOT LIVE INVENTORY'), str(path))
        manifest[sport.id] = {'path': str(path.relative_to(output)), 'part': part, 'selected': target,
                             'match': items[0]['url'], 'price': 250, 'synthetic': True}
    (output / 'audit-fixtures' / 'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output')
    print(json.dumps(build(parser.parse_args().output), indent=2))
