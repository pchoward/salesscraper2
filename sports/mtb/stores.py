"""First MTB stores from Claude's #137 collection probe; one shared feed/store."""
import logging
import re
import time
from urllib import robotparser
from urllib.error import HTTPError
from urllib.request import Request,urlopen
import sports
from sports import brands, protection
from stores import shopify
from sports.mtb.rules import PARTS,filter_reason,title_part
from sports.mtb.specs import extract

logger=logging.getLogger('stores.mtb')
MAX_STOCK_LOOKUPS=40
TYPES={}
for part,names in {
 'Bikes':('bikes','mountain bikes','mtb bikes','complete bikes'),
 'Frames':('frames','frame','framesets','mountain bike frames'),
 'Forks & Shocks':('fork','forks','suspension forks','rear shock','rear shocks','shocks','suspension','shock springs','coil springs'),
 'Wheels':('wheels','wheelsets','rims','hubs','mtb wheels'),
 'Tires':('tires','tyres','tubes','tires tubes'),
 'Drivetrain':('drivetrain','cranks','cranksets','cassettes','chains','chainrings','derailleurs','shifters'),
 'Brakes':('brakes','disc brakes','brake rotors','rotors','brake pads'),
 'Cockpit':('handlebars','stems','grips','headsets','seatposts','dropper posts','saddles'),
 'Pedals':('pedals',),
 'Protection':('helmets','pads','knee pads','elbow pads','protection','body armor','gloves','goggles','neck braces',
                'chest protectors','shin guards','arm pads'),
}.items():
    TYPES.update({name:part for name in names})

WORLDWIDE=shopify.ShopifyStore('Worldwide Cyclery','Worldwide Cyclery','https://www.worldwidecyclery.com',
    collection='deals',types=TYPES,brand_of=brands.for_sport(sports.MTB),own_vendor='worldwide',
    title_part=title_part,type_part=title_part,unknown_by_title=True)
# Protection (2026-11-03): each store's protection and helmet collections are
# read too; as everywhere, only marked-down variants are listed.
# Whole catalog too (2026-11-06): its TRP brake and drivetrain promo (20% off
# to Nov 30) and ~170 other markdowns sit in brakes-drivetrain/drivetrain,
# not the outlet; the catalog is ~18 pages, and a Black Friday collection is
# ready to fill. Only marked-down variants are listed, as everywhere.
FANATIK=shopify.ShopifyStore('Fanatik','Fanatik','https://www.fanatikbike.com',
    collection='fanatik-outlet',more_collections=('on-sale-protection','on-sale-helmets','mountain-bike-protection'),types=TYPES,brand_of=brands.for_sport(sports.MTB),own_vendor='fanatik',
    title_part=title_part,type_part=title_part,unknown_by_title=True,whole_site=True)


def mikes_part(product_type):
    """Mike's Bikes files products by path ("BIKES AND FRAMES/BIKES - MOUNTAIN/
    CROSS COUNTRY/BLUR", "COMPONENTS/PEDALS/MTB FLAT"). Mountain bikes and
    e-MTBs are Bikes; components and protection use the shared title rules on
    the path's later segments; road, gravel, active/city e-bikes, bar tape and
    accessories are out (issue #165)."""
    segments=[part.strip().lower() for part in str(product_type or '').split('/') if part.strip()]
    if not segments:return None
    text=' / '.join(segments)
    if any(word in text for word in ('road','gravel','bar tape','cyclocross')):return None
    top,rest=segments[0],' '.join(segments[1:])
    if top=='bikes and frames':
        if 'mountain' not in rest:return None
        return 'Frames' if rest.startswith('frame') else 'Bikes'
    if top in ('components','protection'):
        return title_part(rest)
    if top=='apparel':
        return 'Protection' if title_part(rest)=='Protection' else None
    return None


# Mike's Bikes (issue #165; store probe 2026-11-02): Shopify. Its clearance and
# sale collection (~669) covers bikes and parts; the mountain and Santa Cruz
# sale collections catch bikes listed only there. A product in several
# collections is kept once (Shopify product id).
MIKES=shopify.ShopifyStore("Mike's Bikes","Mike's Bikes",'https://mikesbikes.com',
    collection='clearance-and-sale',
    more_collections=('clearance-and-sale-bikes','mountain-bikes','santa-cruz-bikes-on-sale',
                      'protective-gear','clearance-and-sale-helmets','mountain-bike-helmets'),
    types={},brand_of=brands.for_sport(sports.MTB),own_vendor="mike's bikes",
    title_part=None,type_part=mikes_part,raw_type_part=True,track_exclusions=True,
    # Whole catalog too: 18 listable markdowns sat outside these collections (audit 2026-11-06).
    whole_site=True,
)
# Cambria (issue #165): one sale collection per part. Types name the
# discipline ("MTB Cassettes", "Road Cassettes", "MTB/Road Chains"); the MTB
# rules drop road/gravel/BMX ones and road groupsets filed under shared types.
CAMBRIA_TYPES={'hardtail':'Bikes','full suspension':'Bikes','electric mountain bikes':'Bikes','ex-demo mtb bikes':'Bikes',
    'full suspension frames':'Frames','hardtail frames':'Frames',
    'mtb/road bottom brackets':'Drivetrain','bottom bracket parts':'Drivetrain','electronic gear shifting':'Drivetrain',
    'mtb groupsets':'Drivetrain','tubes':'Tires'}
def cambria_part(product_type):
    kind=' '.join(str(product_type or '').lower().split())
    if 'helmet' not in kind and protection.protects('',kind):return 'Protection'
    if not kind or re.search(r'\b(?:bags?|tape|tools?|lubricants?|cleaners?|cruiser|comfort|wheelchair|kids)\b|\b(?:helmet|goggle)\s+parts\b',kind):return None
    return CAMBRIA_TYPES.get(kind) or title_part(kind)

def _tag_values(product,name):
    prefix='F'+name+'_'
    return [t[len(prefix):] for t in product.get('tags') or [] if isinstance(t,str) and t.startswith(prefix)]

def cambria_specs(product,variant,part):
    """Wheel size and fork travel from Cambria's filter tags ("Fwheelsize_27.5\" (650b)",
    "Fforktravel_130mm"). A product tagged with several wheel sizes gives each
    variant only the size its own options name."""
    found={}
    if part in ('Bikes','Frames','Forks & Shocks','Wheels','Tires'):
        wheels={m[1] for v in _tag_values(product,'wheelsize') for m in [re.match(r'(26|27\.5|29)"',v.strip())] if m}
        if len(wheels)>1:
            own=' '.join(str(variant.get(k) or '') for k in ('title','option1','option2','option3'))
            wheels={w for w in wheels if re.search(r'(?<![\d.])'+re.escape(w)+r'(?![\d])',own)}
        if wheels:found['wheel_size']=wheels
    if part in ('Bikes','Frames','Forks & Shocks'):
        travel={m[1] for v in _tag_values(product,'forktravel') for m in [re.fullmatch(r'(\d{2,3})\s*mm',v.strip())] if m and 50<=int(m[1])<=250}
        if len(travel)==1:found['travel_mm']=travel
    return found

CAMBRIA=shopify.ShopifyStore('Cambria','Cambria Bike','https://cambriabike.com',
    collection='sale-components',more_collections=('sale-frames-forks','sale-wheels','sale-tires','sale-bikes',
                                                   'body-armor','goggles','neck-braces'),
    types={},brand_of=brands.for_sport(sports.MTB),own_vendor='cambria',
    title_part=title_part,type_part=cambria_part,raw_type_part=True,track_exclusions=True)
CAMBRIA.extra_specs=cambria_specs
# Bikes Online (issue #165): coarse types ("Bikes", "Parts", "Clothing &
# Protective Gear", "Accessories"), so the part comes from the title. Kids'
# bikes and accessories (lights, racks, lube, computers) stay out.
def bikes_online_part(kind):
    return shopify.BY_TITLE if kind in ('bikes','parts','clothing protective gear') else None

def bikes_online_title(title):
    value=' '.join(str(title or '').split())
    # Polygon's road/gravel lines, and the store's "Raod" spelling.
    if re.search(r'\b(?:kids?|tools?|lube|bleed\s+kit|tambora|strattos|bend|path|raod)\b',value,re.I):return None
    if re.search(r'\bfox\s+3[468]\b|\bfloat\b.*\b(?:fork|grip)\b',value,re.I):return 'Forks & Shocks'
    part=title_part(value)
    if part is None and re.search(r'\bbar\b',value,re.I):return 'Cockpit'
    return part

BIKES_ONLINE=shopify.ShopifyStore('Bikes Online','Bikes Online','https://www.bikesonline.com',
    collection='mountain-bikes-sale',more_collections=('mountain-gear-sale','sale','clothing-protection-on-sale',
                                                       'helmets-on-sale','cycling-body-armor','cycling-goggles'),
    types={},brand_of=brands.for_sport(sports.MTB),own_vendor='bikes online',
    title_part=bikes_online_title,type_part=bikes_online_part,track_exclusions=True)
# Colorado Cyclist (issue #165): the same platform and tags as Cambria. Its
# sale bikes and frames are largely Cambria's listings at Cambria's prices, so
# only helmets, tires and wheels are read. Road, kids' helmets and helmet
# parts (visors, liners) stay out.
COLORADO_HELMETS=('mtb helmets','full face helmets','dirt jump helmets')
# Commuter, touring and gravel tire lines that come in MTB wheel sizes.
_NOT_MTB_TIRES=r'\b(?:marathon|big\s+ben|big\s+apple|super\s+moto|fat\s+frank|g-one|hurricane|kojak|energizer|land\s+cruiser|road\s+cruiser|smart\s+sam|citizen|delta\s+cruiser)\b'
def colorado_part(product_type):
    kind=' '.join(str(product_type or '').lower().split())
    if 'helmet' in kind:return 'Protection' if kind in COLORADO_HELMETS else None
    if protection.protects('',kind):return 'Protection'  # pads, armor, goggles, roost guards
    if kind in ('tires','wheels'):return shopify.BY_TITLE  # one generic type: the title decides
    part=cambria_part(product_type)
    return part if part in ('Tires','Wheels') else None

def colorado_title(title):
    """Tires: 26/27.5/29 x 1.9 in or wider, not commuter lines. Wheels: MTB sizes."""
    value=' '.join(str(title or '').split())
    part=title_part(value)
    if part=='Tires':
        if re.search(r'\btubes?\b',value,re.I):return 'Tires'
        size=re.search(r'(?<![\d.])(26|27\.5|29)\s*["″]?\s*x\s*(\d(?:\.\d+)?)',value,re.I)
        if not size or float(size[2])<1.9 or re.search(_NOT_MTB_TIRES,value,re.I):return None
        return 'Tires'
    if part=='Wheels':
        return 'Wheels' if re.search(r'(?<![\d.])(?:26|27\.5|29)(?:["″]|er\b|\b)|\b(?:mtb|mountain|boost|enduro|trail|xc)\b',value,re.I) else None
    return None

COLORADO=shopify.ShopifyStore('Colorado Cyclist','Colorado Cyclist','https://www.coloradocyclist.com',
    collection='sale-helmets',more_collections=('sale-tires','sale-wheels','sale-body-armor','goggles-1','roost-guards'),
    types={},brand_of=brands.for_sport(sports.MTB),own_vendor='colorado cyclist',
    title_part=colorado_title,type_part=colorado_part,raw_type_part=True,track_exclusions=True)
COLORADO.extra_specs=cambria_specs
# Brand-direct stores (owner, 2026-11-03: "a LOT more protective gear ... all
# the main brands"). Their sale collections also hold jerseys and shorts (the
# MTB rules leave those out) and other sports' gear, which the title filter
# leaves out: baseball/soccer guards (G-Form), moto (Troy Lee), snow (Demon).
# Leatt's and Fox's own stores can't be read (empty feed / not Shopify); their
# gear comes through the retailers. iXS prices in euros, so it isn't used.
_OTHER_SPORTS=r'\b(?:baseball|softball|soccer|football|lacrosse|hockey|batter\'?s?|catcher|snow|ski|winter|snowboard|moto|mx|motocross|motorcycle)\b'
def brand_title(title):
    if re.search(_OTHER_SPORTS,str(title or ''),re.I):return None
    if re.search(r'\b(?:tailgate|straps?|racks?|bags?|backpacks?)\b',str(title or ''),re.I):return None
    return title_part(title)

def brand_store(name,base,handles):
    return shopify.ShopifyStore(name,name,base,collection=handles[0],more_collections=tuple(handles[1:]),
        types=TYPES,brand_of=brands.for_sport(sports.MTB),title_part=brand_title,type_part=brand_title,
        unknown_by_title=True,track_exclusions=True)

TROY_LEE=brand_store('Troy Lee Designs','https://www.troyleedesigns.com',('troys-garage-bike-sale','sale-bike-womens'))
ALPINESTARS=brand_store('Alpinestars','https://www.alpinestars.com',('sale-all-mtb',))
DEMON=brand_store('Demon','https://www.demonunited.com',('sale','discount-eligible'))
SEVEN_IDP=brand_store('7iDP','https://7idp.com',('sale',))
G_FORM=brand_store('G-Form','https://www.g-form.com',('sale-m2','sale-included-products'))
RACE_FACE=brand_store('Race Face','https://www.raceface.com',
    ('outlet-sale','protection-sale','fall-sale','sale','on-sale','clearance-week'))
KALI=brand_store('Kali','https://www.kaliprotectives.com',('all',))
BERN=brand_store('Bern','https://www.bernunlimited.com',('bern-barn','bern-outlet'))
SMITH=brand_store('Smith','https://www.smithoptics.com',('bike-sale',))  # bike helmets, MTB goggles
BRAND_STORES=(TROY_LEE,ALPINESTARS,DEMON,SEVEN_IDP,G_FORM,RACE_FACE,KALI,BERN,SMITH)
# The Lost Co. (owner, 2026-11-03): an MTB parts shop with ~650 marked-down
# parts. Its types are clean ("Fork Parts", "Rear Shocks", "Chainrings");
# tools, lubes, fluids, cleaners, sealant and fenders are left out.
LOST_CO_TYPES={'bottom brackets':'Drivetrain','groupsets':'Drivetrain','dropper parts':'Cockpit','dropper posts':'Cockpit',
    'full suspension bikes':'Bikes','hardtail bikes':'Bikes','tire inserts':'Tires','seatpost':'Cockpit','headsets':'Cockpit'}
def lost_co_part(product_type):
    kind=' '.join(str(product_type or '').lower().split())
    if not kind or re.search(r'\b(?:tools?|lubes?|lubricants?|fluid|greases?|oil|cleaners?|polish|pumps?|pliers|hammers?|sealant'
                             r'|number\s+plates?|fenders?|exclude|flat\s+fixers?|valves?|binders?|bearings?|geometry)\b',kind):
        return None
    return LOST_CO_TYPES.get(kind) or title_part(kind)

LOST_CO=shopify.ShopifyStore('The Lost Co.','The Lost Co.','https://www.thelostco.com',
    collection='mtb-parts-on-sale',more_collections=('clearance-mountain-bike-parts',),
    types={},brand_of=brands.for_sport(sports.MTB),own_vendor='the lost co',
    title_part=title_part,type_part=lost_co_part,raw_type_part=True,track_exclusions=True)
STORES=(WORLDWIDE,FANATIK,MIKES,CAMBRIA,BIKES_ONLINE,COLORADO,)+BRAND_STORES+(LOST_CO,)


def robots_policy(store):
    """Fail closed on unreadable policy; the same UA as the shared JSON fetch."""
    try:
        request=Request(store.base+'/robots.txt',headers={'User-Agent':shopify._USER_AGENT})
        with urlopen(request,timeout=20) as response:
            raw=response.read(256_001)
            if len(raw)>256_000:return None
            body=raw.decode('utf-8','replace')
            if 'user-agent:' not in body.lower():return None
    except HTTPError as exc:
        if exc.code!=404:return None
        body=''
    except Exception as exc:
        logger.warning('%s: robots policy unavailable (%s)',store.store,type(exc).__name__)
        return None
    parser=robotparser.RobotFileParser()
    parser.parse(body.splitlines())
    delay=max(shopify.PAGE_DELAY,parser.crawl_delay(shopify._USER_AGENT) or 0)
    rate=parser.request_rate(shopify._USER_AGENT)
    if rate and rate.requests:delay=max(delay,rate.seconds/rate.requests)
    return parser,delay


class MtbShopifyScraper(shopify.ShopifyScraper):
    def scrape(self):
        if 'mtb_products' not in self.shop.cache:
            policy=robots_policy(self.shop)
            products=None
            if policy is not None:
                robots,delay=policy
                last=[time.monotonic()]
                stock_reads=[0]
                def fetch(url):
                    if not robots.can_fetch(shopify._USER_AGENT,url):
                        logger.warning('%s: robots disallows collection feed',self.shop.store)
                        return None
                    if url.endswith('.js'):
                        if stock_reads[0]>=MAX_STOCK_LOOKUPS:return None
                        stock_reads[0]+=1
                    remaining=delay-(time.monotonic()-last[0])
                    if remaining>0:time.sleep(remaining)
                    result=shopify._fetch_json(url)
                    if url.endswith('.js') and isinstance(result,dict) and isinstance(result.get('variants'),list):
                        result={**result,'variants':[v for v in result['variants'] if isinstance(v,dict) and isinstance(v.get('available'),bool)]}
                    last[0]=time.monotonic()
                    return result
                products=shopify.load_sale_products(self.shop,fetch=fetch)
                if products is not None:
                    relevant=[p for p in products if isinstance(p,dict) and shopify.sale_variants(p)
                              and not filter_reason(
                                  shopify.title_with_brand(p),PARTS[0],product_type=p.get('product_type',''))]
                    if relevant and not any(shopify.part_for(self.shop,p.get('product_type'),p.get('title','')) for p in relevant):
                        logger.error('%s: sale products exist but none map to MTB equipment; not reporting empty success',self.shop.store)
                        self.shop.cache['mtb_products']=None
                        return None
                    for part in PARTS:
                        shopify.enrich_stock(self.shop,products,part,fetch=fetch)
                    shopify.log_feed_summary(self.shop,products)
                    logger.info('%s: %s bounded stock lookups (maximum %s)',self.shop.store,stock_reads[0],MAX_STOCK_LOOKUPS)
            self.shop.cache['mtb_products']=products
        products=self.shop.cache['mtb_products']
        return None if products is None else self.products_from(products)

    def _item(self,product,name,url,variants):
        item=super()._item(product,name,url,variants)
        if item is None:return None
        offers=[];warnings=set()
        for variant in variants:
            try:specs,conflicts=extract(product,variant,self.part)
            except (TypeError,ValueError,AttributeError) as exc:
                logger.warning('Optional MTB specs unavailable for %s (%s)',url,type(exc).__name__)
                specs,conflicts={},['unreadable specifications']
            warnings.update(conflicts)
            # Store-tagged facts (Cambria's filter tags) fill keys the title/options left empty.
            for key,values in (getattr(self.shop,'extra_specs',None) or (lambda *a:{}))(product,variant,self.part).items():
                if values and key not in specs:specs[key]=sorted(values)
            if self.part=='Protection':
                specs.update(protection.fields(product.get('title',''),product.get('product_type',''),
                                               shopify._plain(product.get('body_html') or ''),'mtb'))
                size=protection.variant_size(product,variant)
                if size:specs['prot_size']=size
            offers.append({'variant_id':variant.get('id'),'price':float(shopify._amount(variant['price'])),
                           'compare':float(shopify._amount(variant['compare_at_price'])),
                           'available':variant.get('available') if isinstance(variant.get('available'),bool) else None,
                           'specs':specs})
        item['technical_offers']=offers
        aggregate={}
        for offer in offers:
            for key,values in offer['specs'].items():aggregate.setdefault(key,set()).update(values)
        item['technical_specs']={k:sorted(v) for k,v in aggregate.items()}
        if warnings:item['spec_warnings']=sorted(warnings)
        item['availability']='In stock' if all(o['available'] is True for o in offers) else 'Check store'
        return item


def scrapers():
    return [MtbShopifyScraper(store,part) for store in STORES for part in PARTS]
