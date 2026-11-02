"""MTB facet configuration/markup atop the existing sidebar and query owner."""
from html import escape
import json
from filters import item_passes_filters
from pathlib import Path

from sports.mtb.specs import FIELDS

PARAMS={'wheel_size':'mtb_wheel','travel_mm':'mtb_travel','frame_size':'mtb_frame',
        'tire_width':'mtb_tirewidth','axle':'mtb_axle','rotor_mm':'mtb_rotor','riding_type':'mtb_ride'}


def payload(data):
    fields=[];items={};values={k:set() for k in FIELDS}
    for group in (data or {}).values():
        for item in group or []:
            if not item_passes_filters(item):continue
            offers=[offer for offer in item.get('technical_offers',[]) if offer.get('available') is not False]
            if not offers:continue
            items[item['url']]={'offers':offers}
            for offer in offers:
                for key,tokens in offer.get('specs',{}).items():
                    if key in values:values[key].update(str(v) for v in tokens)
    for key,label in FIELDS.items():
        if values[key]:fields.append({'key':key,'label':label,'param':PARAMS[key],'values':sorted(values[key])})
    return {'fields':fields,'items':items}


def sidebar(data,section):
    config=payload(data)
    body='<p class="section-note">Only stated specifications are filterable. Unknown specifications are hidden when a filter is selected.</p>'
    for field in config['fields']:
        body+=(f'<label class="field"><span>{escape(field["label"])}</span>'
               f'<select id="tech-{field["key"]}" aria-label="{escape(field["label"],quote=True)}"><option value="">Any</option>'
               +''.join(f'<option value="{escape(v,quote=True)}">{escape(v)}</option>' for v in field['values'])+'</select></label>')
    if not config['fields']:body='<p class="section-note">No exact technical specifications were published for these deals.</p>'
    return '<div id="contextSpecs">'+section('technical','MTB specifications',body,open_default=True)+'</div>'


def script(data):
    config=json.dumps(payload(data)).replace('<','\\u003c')
    js=(Path(__file__).resolve().parents[2]/'previews/sport-filters.js').read_text()
    return '<script type="application/json" id="technicalCatalog">'+config+'</script><script>'+js+'</script>'
