"""Exact MTB specification evidence from titles, labeled text and variant axes."""
import re
from decimal import Decimal, InvalidOperation
from product_specs import option_text,text
from bs4 import BeautifulSoup

FIELDS={
 'wheel_size':'Wheel size (in)', 'travel_mm':'Suspension travel (mm)',
 'frame_size':'Frame size','tire_width':'Tire width (in)',
 'axle':'Axle / spacing','rotor_mm':'Rotor diameter (mm)','riding_type':'Riding type',
 'speed':'Drivetrain speed','casing':'Tire casing','tubeless':'Tubeless','power':'Motor',
 'suspension':'Suspension','frame_material':'Frame material',
}

# Bike filters modelled on evo's (owner, 2026-11-21): suspension and frame
# material, plus wheel size and travel from stated sources only.
FULL='Full suspension'
HARDTAIL='Hardtail'
_FULL=re.compile(r'\bfull[\s-]*susp(?:ension)?\b|\bdual[\s-]*susp(?:ension)?\b|\be-full\b|\bfull[\s-]*sus\b',re.I)
_HARDTAIL=re.compile(r'(?i:\bhard\s*tails?\b|\be-hardtail\b)|\bHT\b')  # Cannondale "Scalpel HT", "Habit HT"
MATERIALS=(('Carbon',re.compile(r'\bcarbon\b|\bfact\s*\d+m\b',re.I)),
           ('Alloy',re.compile(r'\b(?:alloy|aluminum|aluminium|alu)\b|\b(?:6061|6066|7005|6069)\b',re.I)),
           ('Steel',re.compile(r'\b(?:steel|chromoly|cro-?mo|cromo|4130|reynolds\s*\d{3})\b',re.I)),
           ('Titanium',re.compile(r'\btitanium\b|\bti\b(?=\s+(?:frame|hardtail))',re.I)))


def _labeled_tags(tags):
    """{"wheelsize": ['29"'], ...} from "key:value" tags (Fanatik's)."""
    if isinstance(tags,str):tags=tags.split(',')
    found={}
    for tag in tags or ():
        key,sep,value=str(tag).partition(':')
        if sep and value.strip():found.setdefault(key.strip().lower(),[]).append(value.strip())
    return found


def suspension(name,product_type='',tags=(),travel=None):
    """'Full suspension', 'Hardtail' or None, from the store's category,
    tags or name; a stated rear travel means full suspension."""
    if isinstance(tags,str):tags=tags.split(',')
    text=' '.join([str(product_type or ''),str(name or '')]+[str(t) for t in tags or () if ':' not in str(t)])
    if _HARDTAIL.search(text):return HARDTAIL
    if _FULL.search(text) or travel:return FULL
    return None


def frame_material(name,product_type='',tags=(),body='',vendor=''):
    """'Carbon', 'Alloy', 'Steel', 'Titanium' or None: a material tag
    (Fanatik), the description's "Frame:" line, or the name."""
    labeled=_labeled_tags(tags).get('material') or []
    candidates=[' '.join(labeled)]
    frame_line=re.search(r'\bframe(?:set)?\s*(?:material)?\s*:\s*([^.;\n]{0,80})',text(body),re.I) if body else None
    if frame_line:candidates.append(frame_line[1])
    candidates.append(str(name or ''))
    # Santa Cruz and Juliana name the material in the model: "Vala C S",
    # "Megatower 2 CC X0", "Chameleon 8 AL D".
    if re.match(r'\s*(?:santa\s+cruz|juliana)\b',str(vendor or '')+' '+str(name or ''),re.I):
        if re.search(r'\bCC?\b',str(name)):candidates.append('carbon')
        elif re.search(r'\bAL\b',str(name)):candidates.append('alloy')
    for source in candidates:
        hits=[label for label,pattern in MATERIALS if pattern.search(source)]
        if len(hits)==1:return hits[0]
        if len(hits)>1:return None
    return None

# E-MTB or not (owner, 2026-11-21: "separate eMTB from regular ... a filter
# up top"). Bikes and frames only. Evidence, strongest first: the store's
# category or tags ("Electric Mountain Bikes", "Bikes - E-Full Suspension
# 29"), the name ("E-Mountain Bike", "eMTB", "Siskiu T7E", "Turbo Levo",
# "Habit Neo", "Trance X E+", "Fuel EXe", a motor brand), a battery size in
# the description ("720Wh"), then e-only model names. Everything else is
# "Regular" when the store files it as a bike or frame. Accessories filed under Frames (RideWrap protection kits,
# number plates) get no value, and so does a listing the store doesn't file
# as a bike or frame.
EMTB='E-MTB'
NOT_EMTB='Regular'
_E_TYPE=re.compile(r'electric|\be-?bikes?\b|\be-?mtb\b|\be-\s?(?:full|hardtail|mountain|enduro|trail)|\bpedelec\b|\bpedal[- ]assist',re.I)
_E_NAME=re.compile(
 r'\be-?mtb\b|\be-?\s?mountain\s*bike|\be-?bike\b|\belectric\b|\bpedal[- ]assist|\bneo\b|\be\+|\bexe\b|\bturbo\b|'
 r'\bbosch\b|\bshimano\s+(?:ep\s?\d|e\d{4}|steps)|\bsram\s+(?:eagle\s+)?powertrain\b|\bpowertrain\b|\bfazua\b|'
 r'\btq[- ]?hpr|\bavinox\b|\bdyname\b|\bbrose\b|\b\d{3}\s?wh\b|'
 # Model codes that end in E: "Siskiu T7E", "Collosus N8XE", "TE-N".
 r'\b(?:siskiu|collosus)\s+(?:[a-z]{1,2}\d{0,2}x?e|te-n)\b',re.I)
# Models sold only as e-bikes, for names that say nothing else.
_E_MODELS=re.compile(
 r'\b(?:levo|kenevo|heckler|vala|bullit|moterra|rail\s*\+?\s?\d|powerfly|decoy|amflow|wild\s+(?:fs|m-?\w+)|'
 r'rise\s+(?:h|m)\d|orbea\s+(?:wild|rise)|shuttle\s+(?:am|sl|ht)|spectral:on|neuron:on|torque:on|stereo\s+hybrid|'
 r'ransom\s+e|fathom\s+e|reign\s+e|stance\s+e|trance\s+x?\s?e|pivot\s+shuttle|ebb|e-?160|e-?170|sentinel\s+e)\b',re.I)
_NOT_A_BIKE=re.compile(r'\bprotection\b|\bridewrap\b|\bnumber\s+plate\b|\bmodule\b|\bguard\b|\bdecals?\b|\bbattery\s+(?:cover|mount)',re.I)


def power(name,product_type='',tags=(),body=''):
    """'E-MTB', 'Regular', or None when the listing isn't a bike or frame."""
    name=str(name or '')
    if _NOT_A_BIKE.search(name):return None
    if isinstance(tags,str):tags=tags.split(',')
    labels=' '.join([str(product_type or '')]+[str(t) for t in tags or ()])
    if _E_TYPE.search(labels) or _E_NAME.search(name) or _E_MODELS.search(name):return EMTB
    body=str(body or '')
    if re.search(r'\b\d{3}\s?wh\b',body,re.I) and re.search(r'\bmotor\b|\bbattery\b',body,re.I):return EMTB
    # "Regular" needs evidence too: the store files it as a bike or frame.
    # A listing with no such category gets no value rather than a guess.
    if re.search(r'bikes?\b|frames?(?:ets?)?\b|hardtail|suspension|\bmtb\b|mountain|enduro|trail|downhill|\bxc\b|dirt',
                 labels,re.I):return NOT_EMTB
    return None

# Owner, 2026-11-07 (menus and filters proposal): read from the name what
# shops print there. Speed: "12-Speed", "12sp", and drivetrains that only
# come in one ("Eagle", "T-Type", Shimano's M6100 series).
_SPEED=re.compile(r'(?<![\d.])(\d{1,2})\s*-?\s*(?:speed|spd|sp)\b',re.I)
_ONE_SPEED=(
 (re.compile(r'\beagle\b|\bt-?type\b|\btransmission\b',re.I),'12'),
 (re.compile(r'\b[MU][5-9]1\d\d\b'),None),          # Shimano 12-speed MTB families, checked below
 (re.compile(r'\bM(?:7|8|9)0\d\d\b'),'11'),
 (re.compile(r'\bM6000\b|\bM4100\b'),'10'),
)
_CASINGS=(
 ('EXO+',re.compile(r'\bexo\s*\+|\bexo\s*plus\b',re.I)),
 ('EXO',re.compile(r'\bexo\b(?!\s*(?:\+|plus))',re.I)),
 ('DoubleDown',re.compile(r'(?i:\bdouble\s*down\b)|\bDD\b')),
 ('DH',re.compile(r'\bDH\b(?!\s*(?:[FR]\b|tires?\b))',re.I)),
 ('Super Trail',re.compile(r'\bsuper\s*trail\b',re.I)),
 ('Super Gravity',re.compile(r'\bsuper\s*gravity\b',re.I)),
 ('Super Downhill',re.compile(r'\bsuper\s*downhill\b',re.I)),
 ('Super Ground',re.compile(r'\bsuper\s*ground\b',re.I)),
 ('Super Race',re.compile(r'\bsuper\s*race\b',re.I)),
 ('Radial',re.compile(r'\bradial\b',re.I)),
 ('Grid Gravity',re.compile(r'\bgrid\s*gravity\b',re.I)),
 ('Grid Trail',re.compile(r'\bgrid\s*trail\b',re.I)),
 ('Grid',re.compile(r'\bgrid\b(?!\s*(?:gravity|trail))',re.I)),
 ('Tough',re.compile(r'\btough\b',re.I)),
 ('Trail casing',re.compile(r'\btrail\s+casing\b',re.I)),
 ('Enduro casing',re.compile(r'\benduro\s+casing\b|\benduro\s*core\b',re.I)),
 ('Downhill casing',re.compile(r'\b(?:downhill|gravity)\s+casing\b',re.I)),
)
_TUBELESS=re.compile(r'\btubeless\b|\bTLR\b|\bTR\b|\bTLE\b|\bTCS\b|\b2Bliss\b|\bTL[- ]?ready\b|\bTL\b',re.I)
_NOT_A_TIRE=re.compile(r'\binserts?\b|\bsealant\b|\bvalves?\b|\bplugs?\b|\brepair\b|\btubes?\b|\brim\s*tape\b|\bliner\b',re.I)


def speeds(name):
    """Drivetrain speeds a part's name states: "12-Speed", "12sp", or a
    family that only comes in one ("SRAM GX Eagle", "Shimano XT M8100")."""
    found={m[1] for m in _SPEED.finditer(name) if 7<=int(m[1])<=13}
    if found:return found
    for pattern,speed in _ONE_SPEED:
        match=pattern.search(name)
        if not match:continue
        if speed is None:
            # M5100 is 11-speed; M6100-M9100 (and U-series) are 12.
            speed='11' if match.group(0)[1:3]=='51' else '12'
        return {speed}
    return set()


def casings(name):
    return {label for label,pattern in _CASINGS if pattern.search(name)}


def tubeless(name):
    return bool(_TUBELESS.search(name)) and not _NOT_A_TIRE.search(name)
WHEELS={'26','27.5','29'}
NUMBER=r'(\d+(?:\.\d+)?)'
INCH=r'(?:["″”]|inches\b|inch\b|in\b)'


def number(value):
    try:
        result=Decimal(str(value))
        return format(result.normalize(),'f') if result.is_finite() and result>0 else None
    except (InvalidOperation,ValueError):return None


def table_rows(product):
    """(label, value) pairs from a description's two-cell table rows."""
    soup=BeautifulSoup(str(product.get('body_html') or ''),'html.parser')
    rows=[]
    for row in soup.select('tr'):
        cells=row.find_all(['th','td'],recursive=False)
        if len(cells)==2:rows.append((cells[0].get_text(' ',strip=True),cells[1].get_text(' ',strip=True)))
    return rows


def extract(product,variant,part):
    name=text(product.get('title',''))
    body=text(product.get('body_html',''))
    specs={}
    warnings=[]
    travel_allowed=part in ('Bikes','Frames') or (part=='Forks & Shocks' and re.search(r'\bforks?\b',name+' '+str(product.get('product_type','')),re.I))
    def add(key,values):
        values={str(v) for v in values if v is not None}
        if values:specs.setdefault(key,set()).update(values)
    # Explicit tire dimensions: left is nominal wheel size, right is tire width.
    if part in ('Tires','Wheels'):
        for m in re.finditer(r'(?<![\d.])'+NUMBER+r'\s*["″”]?\s*[x×]\s*'+NUMBER+r'\s*["″”]?',name,re.I):
            if number(m[1]) in WHEELS:
                add('wheel_size',[number(m[1])])
                if part=='Tires' and 1.5<=float(m[2])<=5:add('tire_width',[number(m[2])])
    for m in re.finditer(r'\bwheel\s*(?:size|diameter)\s*[:=]\s*'+NUMBER+r'\s*'+INCH,name+'; '+body,re.I):
        if number(m[1]) in WHEELS:add('wheel_size',[number(m[1])])
    if part in ('Wheels','Tires','Forks & Shocks','Bikes','Frames'):
        for m in re.finditer(r'(?<![\d.])'+NUMBER+r'\s*'+INCH,name,re.I):
            if (number(m[1]) in WHEELS and not re.search(r'(?:frame size|top tube|seat tube|width)\s*[:=]?\s*$',name[:m.start()],re.I)):
                add('wheel_size',[number(m[1])])
    for m in re.finditer(r'\b(?:suspension\s+)?travel\s*[:=]\s*'+NUMBER+r'\s*mm\b',name+'; '+body,re.I):
        if travel_allowed and 50<=float(m[1])<=250:add('travel_mm',[number(m[1])])
    if part=='Forks & Shocks' and re.search(r'\bforks?\b',name,re.I):
        for m in re.finditer(r'(?<![\d.])'+NUMBER+r'\s*mm\b',name,re.I):
            if 50<=float(m[1])<=250 and not re.search(r'\boffset\s*[:=]?\s*$',name[:m.start()],re.I) and not re.match(r'\s*offset\b',name[m.end():],re.I):add('travel_mm',[number(m[1])])
    if part in ('Drivetrain','Bikes'):add('speed',[s+'-speed' for s in speeds(name)])
    if part in ('Bikes','Frames'):
        add('power',[power(name,product.get('product_type',''),product.get('tags') or (),body)])
        labeled_tags=_labeled_tags(product.get('tags') or ())
        # Fanatik's labeled tags: wheelsize:29", susptravel:150mm, axlesize:12x148mm Boost.
        for value in labeled_tags.get('wheelsize',[]):
            m=re.fullmatch(NUMBER+r'\s*["″”]?',value.strip())
            if m and number(m[1]) in WHEELS:add('wheel_size',[number(m[1])])
        for value in labeled_tags.get('susptravel',[]):
            m=re.fullmatch(NUMBER+r'\s*mm',value.strip(),re.I)
            if m and 50<=float(m[1])<=250:add('travel_mm',[number(m[1])])
        for value in labeled_tags.get('axlesize',[]):
            m=re.match(r'(\d{1,2})\s*[x×]\s*(\d{3})',value)
            if m and m[2] in ('142','148','150','157'):add('axle',[m[1]+'x'+m[2]+'mm'])
        # A store category like "Bikes - Full Suspension 29" states the wheel size.
        kind=str(product.get('product_type',''))
        m=re.search(r'(?<![\d.])(27\.5|29|26)(?![\d.])',kind)
        if m and re.search(r'bike|frame|suspension|hardtail',kind,re.I):add('wheel_size',[m[1]])
        # "Rear travel: 150mm", "150mm of rear travel" in the description. A
        # bare "160mm of travel" is often the fork's, so it isn't used.
        for m in re.finditer(r'\brear\s+(?:wheel\s+)?travel\s*[:\-]?\s*'+NUMBER+r'\s*mm\b|'+NUMBER+r'\s*mm\s+(?:of\s+)?rear\s+(?:wheel\s+)?travel\b',body,re.I):
            value=m[1] or m[2]
            if 50<=float(value)<=250:add('travel_mm',[number(value)])
        # Spec-table rows (Mike's Bikes): "Rear Shock | FOX Float X, 205x60",
        # "Frame | ... carbon ...", "Tires | Maxxis ... 29 x 2.5".
        rear_shock=frame_row=None
        fork_row=False
        for label,raw in table_rows(product):
            low=' '.join(re.sub(r'[^a-z0-9 ]',' ',str(label).lower()).split())
            value=text(raw).strip()
            if low in ('rear shock','shock') and value and not re.fullmatch(r'(?i)n\s*/?\s*a|none|-+|rigid',value):
                rear_shock=value
                m=re.search(NUMBER+r'\s*mm\s+travel\b',value,re.I)
                if m and 50<=float(m[1])<=250:add('travel_mm',[number(m[1])])
            elif low in ('frame','frameset','frame material'):frame_row=value
            elif low in ('fork','suspension fork','front suspension') and value:fork_row=True
            elif low in ('tires','tire','front tire','rear tire','tyres'):
                for m in re.finditer(r'(?<![\d.])'+NUMBER+r'\s*["″”]?\s*[x×]\s*'+NUMBER,value):
                    if number(m[1]) in WHEELS:add('wheel_size',[number(m[1])])
        kind_of=suspension(name,kind,product.get('tags') or (),specs.get('travel_mm') or rear_shock)
        # A spec table with a fork and no rear shock is a hardtail's.
        if kind_of is None and fork_row and not rear_shock:kind_of=HARDTAIL
        add('suspension',[kind_of])
        # Travel means rear-wheel travel; a hardtail's numbers are its fork's.
        if kind_of==HARDTAIL:specs.pop('travel_mm',None)
        add('frame_material',[frame_material(name,kind,product.get('tags') or (),
                                             ('Frame: '+frame_row) if frame_row else product.get('body_html',''),
                                             product.get('vendor',''))])
    if part=='Tires' and not _NOT_A_TIRE.search(name):
        add('casing',casings(name))
        if tubeless(name):add('tubeless',['Tubeless ready'])
    # A fork's or frame's wheel size printed bare: "Fox 36 Float 29", "Hightower 4 CC 29 Frame".
    if part in ('Forks & Shocks','Frames','Bikes'):
        for m in re.finditer(r'(?<![\d.\-/])(27\.5|29)(?:er)?(?![\d.]|\s*(?:mm|t\b|x\b|tooth))',name,re.I):
            if not re.search(r'(?:frame size|top tube|seat tube|size|width|reach)\s*[:=]?\s*$',name[:m.start()],re.I):
                add('wheel_size',[m[1]])
    if part=='Brakes' and re.search(r'\brotors?\b',name,re.I):
        add('rotor_mm',[number(v) for v in re.findall(NUMBER+r'\s*mm\b',name,re.I) if 140<=float(v)<=240])
    axes=option_text(product,variant)
    # Feed descriptions often contain actual manufacturer spec tables. Read
    # labeled cells rather than treating arbitrary body numbers as dimensions.
    soup=BeautifulSoup(str(product.get('body_html') or ''),'html.parser')
    for row in soup.select('tr'):
        cells=row.find_all(['th','td'],recursive=False)
        if len(cells)==2:axes.append((cells[0].get_text(' ',strip=True),cells[1].get_text(' ',strip=True)))
    for term in soup.select('dt'):
        value=term.find_next_sibling('dd')
        if value is not None:axes.append((term.get_text(' ',strip=True),value.get_text(' ',strip=True)))
    labeled={}
    for label,raw in axes:
        label=re.sub(r'[^a-z0-9 ]',' ',str(label).lower())
        label=' '.join(label.split())
        value=text(raw).strip()
        key=None;values=[]
        if part=='Tires' and label in ('size','tire size'):
            m=re.fullmatch(NUMBER+r'\s*["″”]?\s*[x×]\s*'+NUMBER+r'\s*(?:'+INCH+r')?',value,re.I)
            if m and number(m[1]) in WHEELS and 1.5<=float(m[2])<=5:
                labeled.setdefault('wheel_size',set()).add(number(m[1]))
                labeled.setdefault('tire_width',set()).add(number(m[2]))
                continue
        if (('wheel' in label and 'width' not in label) or label=='diameter' or (label=='size' and part in ('Wheels','Tires'))):
            m=re.fullmatch(NUMBER+r'\s*(?:'+INCH+r')?',value,re.I)
            if m and number(m[1]) in WHEELS:key='wheel_size';values=[number(m[1])]
        elif 'travel' in label and travel_allowed:
            m=re.fullmatch(NUMBER+r'\s*(?:mm)?',value,re.I)
            if m and 50<=float(m[1])<=250:key='travel_mm';values=[number(m[1])]
        elif ('frame size' in label or label=='size') and part in ('Bikes','Frames'):
            sizes={'extra small':'XS','x small':'XS','small':'S','medium':'M','large':'L','extra large':'XL','x large':'XL','xx large':'XXL',
                   'extra extra large':'XXL','2x large':'XXL','xxl':'XXL','xl':'XL','xs':'XS'}
            # Stores spell sizes out ("X-Large", "XX-Large"; Mike's Bikes, #165).
            val=sizes.get(' '.join(value.lower().replace('-',' ').split()),value.upper())
            if val in ('XS','S','M','L','XL','XXL') or re.fullmatch(r'S[1-6]',val):key='frame_size';values=[val]
        elif ('width' in label or label=='size') and part=='Tires':
            m=re.fullmatch(NUMBER+r'\s*(?:'+INCH+r')?',value,re.I)
            if m and 1.5<=float(m[1])<=5:key='tire_width';values=[number(m[1])]
        elif 'axle' in label or 'spacing' in label:
            m=re.fullmatch(r'(\d{1,2})\s*[x×]\s*(\d{3})\s*(?:mm)?',value,re.I)
            if m:key='axle';values=[m[1]+'x'+m[2]+'mm']
        elif 'rotor' in label and ('size' in label or 'diameter' in label):
            m=re.fullmatch(NUMBER+r'\s*(?:mm)?',value,re.I)
            if m and 140<=float(m[1])<=240:key='rotor_mm';values=[number(m[1])]
        if key:labeled.setdefault(key,set()).update(values)
    for key,values in labeled.items():
        if key in specs and not values.issubset(specs[key]):
            specs.pop(key,None);warnings.append('conflicting '+key)
        elif len(values)>1:
            specs.pop(key,None);warnings.append('conflicting '+key)
        else:specs[key]=values
    # Only an explicit riding-style tag or labeled manufacturer field, not a
    # guessed model/brand-to-discipline classification.
    tags=product.get('tags') or []
    if isinstance(tags,str):tags=tags.split(',')
    for tag in tags:
        token=str(tag).strip().lower().replace('_',' ').replace('-',' ')
        if token in ('trail','enduro','downhill','dirt jump'):add('riding_type',[token])
    return {k:sorted(v) for k,v in specs.items()},warnings
