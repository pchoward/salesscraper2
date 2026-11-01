"""Read-only specification coverage, optionally replaying already-saved text.

Never fetches retailer pages, invokes scrapers, or writes catalog/history data.
"""
import argparse
import copy
import json
from collections import defaultdict
from pathlib import Path

from filters import item_passes_filters
from dimensions import extract_specs
from part_specs import wheel_specs
from product_specs import enrich


def coverage(catalog, replay_text=False):
    counts = defaultdict(lambda: {'decks': 0, 'wheels': 0, 'missing_width': 0,
                                  'missing_diameter': 0, 'missing_durometer': 0})
    missing = []
    for key, items in catalog.items():
        if not isinstance(items, list):
            continue
        for original in items:
            if not isinstance(original, dict) or original.get('part') not in ('Decks', 'Wheels') or not item_passes_filters(original):
                continue
            item = copy.deepcopy(original)
            if replay_text and not item.get('spec_offers'):
                enrich(item, item.get('description', ''))
            row = counts[item.get('store') or key.rsplit('_', 1)[0]]
            absent = []
            if item['part'] == 'Decks':
                row['decks'] += 1
                if not (item.get('widths') or item.get('width') or extract_specs(item.get('name', ''))['width']):
                    absent.append('width')
            else:
                row['wheels'] += 1
                named = wheel_specs(item.get('name', ''))
                if not (item.get('diameters_mm') or item.get('diameter_mm') or named['diameter_mm']):
                    absent.append('diameter')
                if not (item.get('durometers') or named['durometers']):
                    absent.append('durometer')
            for attribute in absent:
                row['missing_'+attribute] += 1
            if absent:
                missing.append({'retailer': item.get('store'), 'name': item.get('name'),
                                'url': item.get('url'), 'missing': absent})
    return {'replayed_saved_text': replay_text, 'retailers': dict(sorted(counts.items())), 'missing': missing}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', type=Path, default=Path('previous_data.json'))
    parser.add_argument('--replay-saved-text', action='store_true')
    args = parser.parse_args(argv)
    catalog = json.loads(args.catalog.read_text())
    if not isinstance(catalog, dict):
        parser.error('catalog must be an object')
    print(json.dumps(coverage(catalog, args.replay_saved_text), indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
