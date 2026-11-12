"""MTB equipment classification; never guesses dimensions from model names."""
import re
from filters import normalize_product_name

PARTS=('Bikes','Frames','Forks & Shocks','Wheels','Tires','Drivetrain','Brakes','Cockpit','Pedals','Protection','Packs')
_RULES=(
 ('Protection',r'\b(?:helmets?|knee\s*(?:pads?|guards?)|elbow\s*(?:pads?|guards?)|body\s*(?:armor|armour)|chest\s*protectors?)\b'),
 ('Forks & Shocks',r'\b(?:suspension\s+forks?|forks?|rear\s+shocks?|shocks?|shock\s+springs?)\b'),
 ('Frames',r'\b(?:frames?|framesets?)\b'),
 ('Tires',r'\b(?:tires?|tyres?|inner\s+tubes?)\b'),
 ('Wheels',r'\b(?:wheelsets?|wheels?|rims?|hubs?)\b'),
 ('Brakes',r'\b(?:brakes?|rotors?|brake\s+pads?)\b'),
 ('Pedals',r'\bpedals?\b'),
 ('Drivetrain',r'\b(?:cranks?|cranksets?|cassettes?|chainrings?|chains?|derailleurs?|shifters?)\b'),
 ('Cockpit',r'\b(?:handlebars?|stems?|grips?|headsets?|dropper\s*posts?|seatposts?|saddles?)\b'),
 ('Bikes',r'\b(?:mountain\s*bikes?|mtb\s*bikes?|complete\s*bikes?|hardtails?|enduro\s*bikes?|downhill\s*bikes?|dirt\s*jump\s*bikes?)\b'),
)

# Road/gravel groupsets, for parts filed under a shared MTB/Road type.
# Road groups and tires named without the word "road" (2026-11-11, Bike Mart's
# parts sale): Campagnolo and its groups, Shimano 105, GP5000, Schwalbe One.
_NOT_MTB=(r'\b(?:campagnolo|campy|super\s+record|chorus|centaur|ekar|shimano\s+105|gp\s*5000|grand\s+prix|gatorskin|'
          r'schwalbe\s+one|pro\s+one|corsa|aero\s+(?:bars?|wheels?)|time\s+trial|tt\s+bars?)\b|'
          r'\b(?:road|gravel|cyclocross|triathlon|bmx|commuter|ultegra|dura[- ]?ace|tiagra|sora|claris|grx|'
          r'rival|(?:force|red)\s+(?:axs|etap|22)|xplr|sram\s+red)\b|\b700\s*(?:c\b|x\s*\d)|(?<![\d.])\d{2}(?:-\d{2})?c\b|\bdrop[- ]bars?\b|\b(?:bar|handlebar)\s+tape\b')


def title_part(title):
    value=normalize_product_name(title)
    # Helmets, pads, armor, gloves, goggles, neck braces (sports/protection.py).
    from sports.protection import protects
    if protects(value):return 'Protection'

    for part,pattern in _RULES:
        if re.search(pattern,value,re.I):return part
    return None


def filter_reason(name,part,url='',price_new=None,price_old=None,description='',product_type=''):
    if not normalize_product_name(name):return 'missing name'
    if part not in PARTS:return 'not an MTB equipment category'
    # Backpacks and hydration packs (sports/packs.py): another sport's own
    # brands stay on that sport; apparel and road words don't apply.
    if part=='Packs':
        from sports import packs
        return packs.rule_reason('mtb',name)
    value=' '+str(name)+' '+str(product_type)+' '
    from sports.protection import protects
    armor=part=='Protection' and protects(str(name),str(product_type))
    if not armor and re.search(r'\b(?:t[- ]?shirts?|hoodies?|sweatshirts?|jerseys?|shorts|pants|socks|beanies?|caps|vests?|jackets?|gift\s*cards?|stickers?|bottles?|bottle\s*cages?)\b',value,re.I):
        return 'apparel or unrelated merchandise'
    # A helmet's bag, liner or visor is not protection itself.
    if part=='Protection' and re.search(r'\bhelmet\s+bags?\b|\bheadliner\b|\bvisors?\b|\bcheek\s*pads?\b|\breplacement\b',str(name),re.I):
        return 'spare or accessory'
    # A type shared by both ("MTB/Road Chains", "Road & MTB Saddles", Cambria)
    # is not a road part by itself; the name still decides.
    kind=str(product_type)
    if re.search(r'\b(?:mtb|mountain)\b',kind,re.I):kind=''
    text=' '+str(name)+' '+kind+' '
    # Dirt jump riders wear BMX lids and pads ("Bell Local BMX Helmet").
    if part=='Protection':text=re.sub(r'\bbmx\b',' ',text,flags=re.I)
    if re.search(_NOT_MTB,text,re.I):
        return 'explicit non-MTB equipment'
    return None
