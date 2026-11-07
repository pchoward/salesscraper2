"""Truck native sizes and conservative deck fit, separate from legacy trucksize.

Source: owner-supplied Independent/Ace table in the 2026-11-07 task discussion,
plus the owner's AF1 80 image (10-inch axle / 188mm hanger) and subsequent
owner-approved 9.75+ deck-fit guidance. These are not manufacturer claims.
This is owner-provided reference data, NOT independently verified manufacturer
charts. No other brand fit is inferred. The old part_specs parser stays intact.
"""
import re

FIT_BANDS = ('7.75', '8.0', '8.25', '8.5', '8.75', '9.0', '9.5+')
TRUCK_SIZES = {}


def _rows(brand, family, rows):
    for code, axle, ideal, maximum in rows:
        TRUCK_SIZES[(brand, family, code)] = dict(axle=axle, ideal=ideal, maximum=maximum)


for family in ('low', 'mid', 'standard'):
    _rows('independent', family, [
        ('129',7.625,(7.5,7.75),(7.375,7.875)),
        ('139',8.0,(7.875,8.125),(7.75,8.25)),
    ])
for family in ('mid', 'standard'):
    _rows('independent', family, [
        ('144',8.25,(8.125,8.375),(8.0,8.5)),
        ('149',8.5,(8.375,8.625),(8.25,8.75)),
        ('159',8.75,(8.625,8.875),(8.5,9.0)),
    ])
_rows('independent','standard',[
    ('109',7.0,(6.775,7.025),(6.65,7.15)),
    ('169',9.125,(9.0,9.25),(8.875,9.375)),
    ('215',10.0,(9.875,10.125),(9.75,10.25)),
])
_rows('independent','stage4',[
    ('146',8.375,None,(8.125,8.625)),
    ('151',8.625,(8.375,8.875),None),
    ('166',9.0,(8.75,9.25),None),
])
_rows('ace','classic',[
    ('00',6.5,(6.375,6.625),(6.25,6.75)),
    ('11',7.0,(6.875,7.125),(6.75,7.25)),
    # Owner table's ideal/max columns are inverted for Classic 22 / Low 02.
    # Preserve supplied values; do not silently swap them.
    ('22',7.625,(7.375,7.875),(7.5,7.75)),
    ('33',8.0,(7.875,8.125),(7.75,8.25)),
    ('44',8.35,(8.25,8.5),(8.125,8.625)),
    ('55',9.0,(8.875,9.125),(8.75,9.25)),
    ('66',9.35,(9.25,9.5),(9.125,9.625)),
])
_rows('ace','classic-low',[
    ('02',7.625,(7.375,7.875),(7.5,7.75)),
    ('03',8.0,(7.875,8.125),(7.75,8.25)),
])
for family in ('af1','af1-low'):
    _rows('ace',family,[
        ('22',7.75,(7.625,7.875),(7.5,8.0)),
        ('33',8.0,(7.875,8.125),(7.75,8.25)),
        ('44',8.25,(8.125,8.375),(8.0,8.5)),
        # 8.675 is retained verbatim from the owner table, not rounded to 8.625.
        ('55',8.5,(8.375,8.675),(8.25,8.75)),
        ('60',8.75,(8.625,8.875),(8.5,9.0)),
    ])
_rows('ace','af1',[
    ('66',9.0,(8.875,9.125),(8.75,9.25)),
    ('77',9.5,(9.375,9.625),(9.25,9.75)),
    ('80',10.0,None,None),
])
# Neither ideal nor maximum was supplied for this new size. Keep the owner's
# working fit guidance separate so it cannot become a manufacturer ideal claim.
TRUCK_SIZES[('ace', 'af1', '80')].update(guidance=(9.75, None), hanger_mm=188)
BRANDS = {'independent':'Independent','ace':'Ace','venture':'Venture','thunder':'Thunder',
          'krux':'Krux','royal':'Royal','tensor':'Tensor','slappy':'Slappy'}
CODES = {
    'independent': {'109','129','139','144','146','149','151','159','166','169','215'},
    'ace': {'00','02','03','11','22','33','44','55','60','66','77','80'},
    'venture': {'5.0','5.2','5.6','5.8','6.1'},
    'thunder': {'143','145','147','148','149','151','161'},
}
_INCH = re.compile(r'(?<![\d.])(\d{1,2}(?:\.\d+)?)\s*(?:["″”]|inches?\b|in\b)',re.I)


def brand_key(name, brand=''):
    text = (str(brand)+' '+str(name)).casefold()
    if re.search(r'\b(?:independent|indy)\b',text):return 'independent'
    return next((key for key in BRANDS if re.search(r'\b'+key+r'\b',text)), '')


def family_key(name, brand):
    text = str(name).casefold()
    if brand == 'independent':
        if re.search(r'\bstage[ -]*4\b',text):return 'stage4'
        if re.search(r'\blow\b',text):return 'low'
        if re.search(r'\bmid\b',text):return 'mid'
        if re.search(r'\b(?:stage[ -]*11|s11|standard|t-hanger)\b',text):return 'standard'
    if brand == 'ace':
        if re.search(r'\baf[ -]*1\b',text):return 'af1-low' if re.search(r'\blow\b',text) else 'af1'
        if re.search(r'\blow\b',text):return 'classic-low'
        if re.search(r'\bclassic\b',text):return 'classic'
    return ''


def native_size(name, brand='', option=None):
    """Native code first; explicit inches retained as an independent cross-check.

    An option is authoritative when supplied; never fill an unknown variant
    from the product title and accidentally ascribe another variant's size.
    """
    key = brand_key(name,brand)
    text = str(name if option is None else option)
    inches = sorted({float(x) for x in _INCH.findall(text)})
    tokens = re.findall(r'(?<![\w.])(?:\d{2,3}|\d\.\d+)(?![\w.])', text)
    codes = list(dict.fromkeys(token for token in tokens if token in CODES.get(key,set())))
    code = codes[0] if len(codes)==1 else ''
    if not code and len(inches)==1:
        code = str(inches[0])
    if not code and key and len(tokens) == 1 and '.' in tokens[0] and 7 <= float(tokens[0]) <= 14:
        code = tokens[0]  # Printed inch-style size, with no family fit inferred.
    # Unknown suppliers can still expose one explicit option, without a fit claim.
    if not code and option is not None:
        raw = re.fullmatch(r'\s*(\d{2,3}|\d\.\d+)(?:\s+(?:hi|high|low|mid))?\s*',text,re.I)
        if raw:code=raw[1]
    family = family_key(name+' '+(text if option is not None else ''),key)
    entry = TRUCK_SIZES.get((key,family,code))
    if not family:
        candidates=[v for (b,_,c),v in TRUCK_SIZES.items() if b==key and c==code]
        # Only dimensions explicitly shared across known families are safe.
        if len(candidates)>1 and all(v==candidates[0] for v in candidates):entry=candidates[0]
    conflict = bool(entry and (len(inches)>1 or (len(inches)==1 and abs(entry['axle']-inches[0])>.04)))
    if conflict:entry=None
    ideal = entry.get('ideal') if entry else None
    maximum = entry.get('maximum') if entry else None
    guidance = entry.get('guidance') if entry else None
    selected_range = ideal or maximum or guidance
    fits = [band for band in FIT_BANDS if selected_range and
            (((selected_range[1] is None or selected_range[1]>=9.5)) if band=='9.5+' else selected_range[0]<=float(band)<=(selected_range[1] if selected_range[1] is not None else float('inf')))]
    return {'brand':key,'brand_label':BRANDS.get(key,str(brand) or 'Unlisted brand'),
            'family':family,'native':code,'key':key+':'+code if key and code else '',
            'printed_inches':inches,'axle':entry['axle'] if entry else (inches[0] if len(inches)==1 else None),
            'ideal':ideal,'maximum':maximum,'guidance':guidance,
            'hanger_mm':entry.get('hanger_mm') if entry else None,
            'fits':fits,'fit_basis':'ideal' if ideal else 'maximum only' if maximum else 'owner guidance' if guidance else '',
            'conflict':conflict}


def offers_for(item):
    rows = item.get('spec_offers') or []
    variant_data = bool(rows)
    if not rows:
        rows=[{'price':item.get('price_new'),'compare_at_price':item.get('price_old'),
               'available':False if item.get('stock')=='out_of_stock' else None}]
    result=[]
    for row in rows:
        spec=native_size(item.get('name',''),item.get('brand',''), row.get('truck_size','') if variant_data else None)
        def number(value):
            try:
                n=float(value)
                return n if n>0 and n<float('inf') else None
            except (ValueError,TypeError):return None
        result.append({**spec,'price':number(row.get('price')),'compare':number(row.get('compare_at_price')),
                       'available':row.get('available'),'variant_id':str(row.get('variant_id') or ''),
                       'variant_data':variant_data})
    return result


def range_text(offer):
    bounds=offer.get('ideal') or offer.get('maximum') or offer.get('guidance')
    if not bounds:return 'fit not verified'
    text=f'{bounds[0]:g}+″' if bounds[1] is None else f'{bounds[0]:g}–{bounds[1]:g}″'
    prefix='fits ' if offer.get('ideal') else 'maximum range ' if offer.get('maximum') else 'owner guidance '
    return prefix+text


def ordered_fits(values):
    return [v for v in FIT_BANDS if v in (values or [])]


def ordered_natives(values):
    return sorted({str(v) for v in (values or []) if re.fullmatch(r'[a-z]+:(?:\d{2,3}|\d{1,2}\.\d+)', str(v))})
