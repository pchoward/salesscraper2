"""Shared technical-offer sidebar; sport modules own field definitions."""
from html import escape
import importlib
import json
from pathlib import Path

from filters import item_passes_filters


def applies(field, part):
    return not field.get('categories') or part in field['categories']


def payload(data, sport):
    definitions = importlib.import_module(sport.facets).FIELDS
    values = {field['key']: set() for field in definitions}
    items = {}
    for group in (data or {}).values():
        for item in group or []:
            if not item_passes_filters(item):
                continue
            part = item.get('part', '')
            offers = [offer for offer in item.get('technical_offers', [])
                      if offer.get('available') is not False]
            if not offers:
                continue
            items[item['url']] = {'part': part, 'offers': offers}
            for field in definitions:
                if not applies(field, part):
                    continue
                for offer in offers:
                    values[field['key']].update(str(v) for v in offer.get('specs', {}).get(field['key'], []))
    fields = [dict(field, values=sorted(values[field['key']]))
              for field in definitions if values[field['key']]]
    return {'fields': fields, 'items': items}


def sidebar(data, section, sport):
    config = payload(data, sport)
    body = '<p class="section-note">Only stated specifications are filterable. Unknown specifications are hidden when a filter is selected.</p>'
    for field in config['fields']:
        body += (f'<label class="field" data-technical-field="{escape(field["key"], quote=True)}"><span>{escape(field["label"])}</span>'
                 f'<select id="tech-{field["key"]}" aria-label="{escape(field["label"], quote=True)}"><option value="">Any</option>'
                 + ''.join(f'<option value="{escape(v, quote=True)}">{escape(v)}</option>' for v in field['values']) + '</select></label>')
    if not config['fields']:
        body = '<p class="section-note">No exact technical specifications were published for these deals.</p>'
    return '<div id="contextSpecs">' + section('technical', sport.label + ' specifications', body, open_default=True) + '</div>'


def script(data, sport):
    config = json.dumps(payload(data, sport)).replace('<', '\\u003c')
    js = (Path(__file__).resolve().parents[1] / 'previews/sport-filters.js').read_text()
    return '<script type="application/json" id="technicalCatalog">' + config + '</script><script>' + js + '</script>'
