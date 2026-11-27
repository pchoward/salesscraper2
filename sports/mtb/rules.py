"""MTB equipment classification; never guesses dimensions from model names."""
import re
from filters import normalize_product_name

PARTS=('Bikes','Frames','Forks & Shocks','Wheels','Tires','Drivetrain','Brakes','Cockpit','Pedals','Tools & Care','Protection','Packs')
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
          r'schwalbe\s+one|pro\s+one|corsa|aero\s+(?:bars?|wheels?)|time\s+trial|tt\s+bars?|shiv|tt\s+(?:disc\s+)?module)\b|'
          # Road and gravel leftovers the specialist check found (owner, 2026-11-27):
          # Zipp road wheels, Reserve's gravel (GR) and aero wheels, eTap Blips,
          # Shimano's road series (R610 Sprinter, RS910 junction, PD-R550). AXS/eTap
          # batteries and chargers fit MTB AXS too, so they stay.
          r'\bzipp\b[^;]*\b(?:202|303|353|404|454|808|858)\b|\bnsw\b|\bturbulent\b|\b\d{2}\|\d{2}\s+gr\b|'
          r'\bblips?\b|\bsprinter\b|(?<!alfine )\bR[S]?\d{3,4}\b|'
          r'\b(?:road|gravel|cyclocross|triathlon|bmx|commuter|ultegra|dura[- ]?ace|tiagra|sora|claris|grx|'
          r'rival|(?:force|red)\s+(?:axs|etap|22)|xplr|sram\s+red)\b|\b700\s*(?:c\b|x\s*\d)|(?<![\d.])\d{2}(?:-\d{2})?c\b|\bdrop[- ]bars?\b|\b(?:bar|handlebar)\s+tape\b')


_TRIPLE=r'\btriple\b|\bmiddle\s+chainring\b|\b3\s*x\s*\d{1,2}\b|\b(?:22|24)/(?:32|34)/(?:42|44)\b'
_RIM_BRAKE=(r'\bv-?\s?brakes?\b|\blinear[\s-]+pull\b|\bcantilevers?\b|\brim\s+(?:brakes?|pads?)\b|\brim\s+brake\s+parts\b|'
            r'\bBR-?T\d{3}\b|\btangente\b')
_FRONT_SHIFTING=r'\bfront\s+derail+eurs?\b|\bfront\s+shifters?\b|\bE-?type\b.*\bderail+eur|\bderail+eur\b.*\bE-?type\b'
_SHIFT=re.compile(r'\bshift(?:er|ers|ing)?\b|\bshift\s*/\s*brake\b|\bdual\s+control\b|\btriggers?\b|\btwist\b',re.I)
# Mounts, AXS pods (dropper or shifting on 1x bikes) and e-bike switches
# aren't front shifters, and a set or pair holds the rear one too.
_NOT_A_LEFT_SHIFTER=re.compile(r'\bclamps?\b|\bbrackets?\b|\bmounts?\b|\bmatch\s*maker\b|\bpods?\b|\bcontrollers?\b|'
                               r'\bswitch(?:es)?\b|\bremotes?\b|\bdropper\b|\bpairs?\b|\bsets?\b|\bright\b|\bcables?\b|\bhousing\b',re.I)


def _left_shifter(name,product_type=''):
    """A left-hand (front) shifter alone: "Saint M800 Shift/Brake Dual Control
    - Left Hand", "Alivio M4050 Brake/Shift Lever (Left)", a store's "FLAT BAR
    LEFT" shifter type."""
    if not _SHIFT.search(name) or _NOT_A_LEFT_SHIFTER.search(name):
        return False
    return bool(re.search(r'\bleft\b',name,re.I) or re.search(r'\bleft\b',product_type,re.I) and
                re.search(r'shifter',product_type,re.I))


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
    # A helmet's bag, liner, visor or light mount is not protection itself.
    if part=='Protection' and re.search(r'\bhelmet\s+bags?\b|\bheadliner\b|\bvisors?\b|\bcheek\s*pads?\b|\breplacement\b|\bhelmet\s+mounts?\b',str(name),re.I):
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
    # Front shifting (owner, 2026-11-26): mountain bikes are 1x now, and
    # Fanatik, an MTB-only shop, carries no front derailleur at all. The old
    # 2x/3x stock is deep clearance, so it filled the top of "% off".
    if re.search(_FRONT_SHIFTING,str(name)+' '+str(product_type),re.I) or _left_shifter(str(name),str(product_type)):
        return 'front derailleur or front shifter'
    # Triples and rim brakes (owner, 2026-11-26), the same story: modern
    # mountain bikes are 1x and disc. Triple cranks, a triple's middle ring
    # and 3x shifter sets; V-brakes, cantilevers, their levers and rim pads.
    both=str(name)+' '+str(product_type)
    if part in ('Drivetrain','Brakes') and re.search(_TRIPLE,both,re.I):
        return 'triple crankset or 3x part'
    if part!='Bikes' and re.search(_RIM_BRAKE,both,re.I) and not re.search(r'\bdisc\b',str(name),re.I):
        return 'V-brake or rim brake part'
    # Frame protection kits, number plates and other frame add-ons are filed
    # under Frames by some shops (Fanatik's "Frame Protection" type, RideWrap
    # kits; The Lost Co.'s ODI number plate). They aren't frames, and MTB has
    # no accessories heading, so they stay out (owner, 2026-11-21).
    if part=='Frames' and re.search(
            r'\bframe\s+protection\b|\bridewrap\b|\bprotection\s+kit\b|\bnumber\s+plates?\b|\bframe\s+(?:guards?|tape|wraps?|'
            r'decals?|stickers?)\b|\bdown\s*tube\s+(?:guards?|protectors?)\b|\bchain\s*stay\s+(?:guards?|protectors?)\b',
            str(name)+' '+str(product_type),re.I):
        return 'frame accessory, not a frame'
    return None
