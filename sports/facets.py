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
    def ordered(field, found):
        # A field's own order ("XS".."XXL", Adult/Youth/Kids), then the rest A-Z.
        order = list(field.get('order') or ())
        return sorted(found, key=lambda value: (order.index(value) if value in order else len(order), value))
    fields = [dict(field, values=ordered(field, values[field['key']]))
              for field in definitions if values[field['key']]]
    return {'fields': fields, 'items': items}


def counts(config):
    """{field key: {value: listings}} among listings the field applies to."""
    found = {field['key']: {} for field in config['fields']}
    for item in config['items'].values():
        for field in config['fields']:
            if not applies(field, item['part']):
                continue
            values = set()
            for offer in item['offers']:
                values.update(str(v) for v in offer.get('specs', {}).get(field['key'], []))
            for value in values:
                found[field['key']][value] = found[field['key']].get(value, 0) + 1
    return found


def sidebar(data, section, sport):
    """One collapsible section per field with count chips, like Skate's
    Deck Width / Deck Length sections; several values can be picked."""
    config = payload(data, sport)
    tally = counts(config)
    sections = []
    for field in config['fields']:
        key = escape(field['key'], quote=True)
        label = escape(field['label'], quote=True)
        total = sum(1 for item in config['items'].values()
                    if applies(field, item['part']) and any(offer.get('specs', {}).get(field['key']) for offer in item['offers']))
        chips = ['<button type="button" class="chip spec-chip tech-chip active" data-tech-key="' + key + '" data-value="" '
                 f'data-count="{total}" aria-pressed="true"><span class="spec-label">All</span>'
                 f'<span class="spec-count">{total}</span></button>']
        for value in field['values']:
            count = tally[field['key']].get(value, 0)
            chips.append(f'<button type="button" class="chip spec-chip tech-chip" data-tech-key="{key}" '
                         f'data-value="{escape(value, quote=True)}" data-count="{count}" aria-pressed="false">'
                         f'<span class="spec-label">{escape(value)}</span><span class="spec-count">{count}</span></button>')
        body = (f'<div class="filter-group spec-ranges" id="tech-{key}" role="group" aria-label="{label}">'
                + ''.join(chips) + '</div>')
        sections.append(f'<div data-technical-field="{key}">'
                        + section('tech-' + field['key'], field['label'], body, open_default=True) + '</div>')
    if not sections:
        return '<div id="contextSpecs"></div>'
    return '<div id="contextSpecs">' + ''.join(sections) + '</div>'


def script(data, sport):
    config = json.dumps(payload(data, sport)).replace('<', '\\u003c')
    js = (Path(__file__).resolve().parents[1] / 'previews/sport-filters.js').read_text()
    return '<script type="application/json" id="technicalCatalog">' + config + '</script><script>' + js + '</script>'
