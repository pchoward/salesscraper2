"""Append explicitly synthetic UI cases to an isolated ci/build_preview output.

No extractor, retailer, delivery, or source state is invoked or modified.
"""
import argparse
import copy
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import page
import sports
from ci.build_preview import mark_preview
from report import build_report_html


def _fixture_promos(sport_id):
    if sport_id != 'mtb':
        return []
    base = {'url': 'https://example.test/sale', 'ends': '', 'sports': ['mtb']}
    return [
        dict(base, store='GeneralFixture', code='SPORTS10', percent=10),
        dict(base, store='Zebra', code='', auto=True, percent=25,
             tiers=[{'percent': 25, 'on': 'gear'}]),
        dict(base, store='AuditFixture', code='FIXTURE40', percent=40),
        dict(base, store='Alpine', code='', auto=True, percent=25,
             tiers=[{'percent': 25, 'on': 'gear'}]),
    ]


@patch('promos.for_sport', new=_fixture_promos)
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
        products = {'AuditFixture_' + part: items}
        if sport is sports.SKI:
            for heading, specs in (
                ('Boots', {'mondo': ['26–26.5'], 'gender': ['Men'], 'flex': ['100'], 'last': ['100 mm']}),
                ('Bindings', {'din': ['12'], 'brake': ['95 mm'], 'gender': ['Unisex']}),
                ('Goggles', {'gender': ['Women'], 'goggle_size': ['Medium']}),
            ):
                stored_part = 'Protection' if heading == 'Goggles' else heading
                products[f'AuditFixture_{stored_part}'] = [
                    {'name': f'SYNTHETIC UI {heading}', 'part': stored_part, 'store': 'AuditFixture',
                     'brand': 'Smith' if heading == 'Goggles' else 'Audit',
                     'url': f'https://example.test/ski/{heading.lower()}',
                     'price_new': '100.00', 'price_old': '400.00', 'availability': 'In stock',
                     'technical_offers': [offer('item', specs)]}
                ]
        if sport is sports.MTB:
            products['AuditFixture_Bikes'] = [
                {'name': f'SYNTHETIC UI {power} Bike', 'part': 'Bikes', 'store': 'AuditFixture',
                 'brand': 'Audit', 'url': f'https://example.test/mtb/bike-{index}',
                 'price_new': '100.00', 'price_old': '400.00', 'availability': 'In stock',
                 'technical_offers': [offer('bike', {'power': [power]})]}
                for index, power in enumerate(('E-MTB', 'Regular'))
            ]
        with sport.active():
            html = build_report_html(products, {}, {}, sport=sport,
                                     generated_at='2026-11-02T00:00:00+00:00')
        path = output / 'audit-fixtures' / sport.id / 'sale_items_chart.html'
        path.parent.mkdir(parents=True, exist_ok=True)
        page.write_page(mark_preview(html, 'SYNTHETIC UI QA — NOT LIVE INVENTORY'), str(path))
        manifest[sport.id] = {'path': str(path.relative_to(output)), 'part': part, 'selected': target,
                             'match': items[0]['url'], 'price': 250, 'synthetic': True}
        if sport is sports.MTB:
            type_case = ('Forks & Shocks', (
                ('RockShox Pike Suspension Fork', 'Forks'),
                ('Fox Float Rear Shock', 'Rear Shocks'),
                ('RockShox Fork Seal Kit', 'Fork Parts'),
            ))
        elif sport is sports.BMX:
            type_case = ('Braking', (
                ('Odyssey Springfield Brake', 'Brakes'),
                ('Odyssey Springfield Brake Kit', 'Brake Kits'),
                ('Odyssey Monolever', 'Brake Levers'),
                ('Odyssey Slic Cable', 'Brake Cables'),
                ('Odyssey Brake Pads', 'Brake Pads'),
                ('Odyssey Brake Mount Parts', 'Brake Parts'),
            ))
        else:
            continue
        stored_part, typed = type_case
        type_items = [
            {'name': name, 'part': stored_part, 'store': 'AuditFixture', 'brand': 'Audit',
             'url': f'https://example.test/{sport.id}/kind-{index}',
             'price_new': '100.00', 'price_old': '400.00', 'availability': 'In stock',
             'kind': 'Brakes & Accessories',
             'technical_offers': [offer('item', {'kind': ['Brakes & Accessories']})]}
            for index, (name, _) in enumerate(typed)
        ]
        # A single-type heading must leave the quick row collapsed.
        type_items.append(dict(type_items[0], name='Single Type Helmet', part='Protection',
                               url=f'https://example.test/{sport.id}/single'))
        type_html = build_report_html({'AuditFixture': type_items}, {}, {}, sport=sport,
                                      generated_at='2026-11-02T00:00:00+00:00')
        type_path = path.with_name('types.html')
        type_path.write_text(mark_preview(type_html, 'SYNTHETIC UI QA — NOT LIVE INVENTORY'))
        manifest[sport.id]['types'] = {
            'path': str(type_path.relative_to(output)),
            'slug': 'suspension' if sport is sports.MTB else 'brakes',
            'param': 'mtb_type' if sport is sports.MTB else 'bmx_kind',
            'values': [value for _, value in typed],
        }

    (output / 'audit-fixtures' / 'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output')
    print(json.dumps(build(parser.parse_args().output), indent=2))
