"""Exact MTB specification evidence from titles, labeled text and variant axes."""
import re
from decimal import Decimal, InvalidOperation
from product_specs import option_text,text

FIELDS={
 'wheel_size':'Wheel size (in)', 'travel_mm':'Suspension travel (mm)',
 'frame_size':'Frame size','tire_width':'Tire width (in)',
 'axle':'Axle / spacing','rotor_mm':'Rotor diameter (mm)','riding_type':'Riding type',
}
WHEELS={'26','27.5','29'}
NUMBER=r'(\d+(?:\.\d+)?)'
INCH=r'(?:["″”]|inches\b|inch\b|in\b)'


def number(value):
    try:
        result=Decimal(str(value))
        return format(result.normalize(),'f') if result.is_finite() and result>0 else None
    except (InvalidOperation,ValueError):return None


def extract(product,variant,part):
    name=text(product.get('title',''))
    body=text(product.get('body_html',''))
    specs={}
    warnings=[]
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
        if 50<=float(m[1])<=250:add('travel_mm',[number(m[1])])
    if part=='Forks & Shocks' and re.search(r'\bforks?\b',name,re.I):
        for m in re.finditer(r'(?<![\d.])'+NUMBER+r'\s*mm\b',name,re.I):
            if 50<=float(m[1])<=250 and not re.search(r'\boffset\s*[:=]?\s*$',name[:m.start()],re.I) and not re.match(r'\s*offset\b',name[m.end():],re.I):add('travel_mm',[number(m[1])])
    if part=='Brakes' and re.search(r'\brotors?\b',name,re.I):
        add('rotor_mm',[number(v) for v in re.findall(NUMBER+r'\s*mm\b',name,re.I) if 140<=float(v)<=240])
    axes=option_text(product,variant)
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
        elif 'travel' in label:
            m=re.fullmatch(NUMBER+r'\s*(?:mm)?',value,re.I)
            if m and 50<=float(m[1])<=250:key='travel_mm';values=[number(m[1])]
        elif ('frame size' in label or label=='size') and part in ('Bikes','Frames'):
            sizes={'extra small':'XS','x small':'XS','small':'S','medium':'M','large':'L','extra large':'XL','x large':'XL','xx large':'XXL'}
            val=sizes.get(value.lower(),value.upper())
            if val in ('XS','S','M','L','XL','XXL'):key='frame_size';values=[val]
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
