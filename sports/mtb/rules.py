"""MTB equipment classification; never guesses dimensions from model names."""
import re
from filters import normalize_product_name

PARTS=('Bikes','Frames','Forks & Shocks','Wheels','Tires','Drivetrain','Brakes','Cockpit','Pedals','Protection')
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


def title_part(title):
    value=normalize_product_name(title)
    for part,pattern in _RULES:
        if re.search(pattern,value,re.I):return part
    return None


def filter_reason(name,part,url='',price_new=None,price_old=None,description='',product_type=''):
    if not normalize_product_name(name):return 'missing name'
    if part not in PARTS:return 'not an MTB equipment category'
    value=' '+str(name)+' '+str(product_type)+' '
    if re.search(r'\b(?:t[- ]?shirts?|hoodies?|sweatshirts?|jerseys?|shorts|pants|socks|beanies?|caps|gift\s*cards?|stickers?|bottles?|bottle\s*cages?)\b',value,re.I):
        return 'apparel or unrelated merchandise'
    if re.search(r'\b(?:road|gravel|cyclocross|triathlon|bmx|commuter)\b|\b700\s*c\b|\bdrop[- ]bars?\b',value,re.I):
        return 'explicit non-MTB equipment'
    return None
