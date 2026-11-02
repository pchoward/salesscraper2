"""First MTB stores from Claude's #137 collection probe; one shared feed/store."""
import logging
import time
from urllib import robotparser
from urllib.error import HTTPError
from urllib.request import Request,urlopen
import sports
from sports import brands
from stores import shopify
from sports.mtb.rules import PARTS,title_part
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
 'Protection':('helmets','pads','knee pads','elbow pads','protection','body armor'),
}.items():
    TYPES.update({name:part for name in names})

WORLDWIDE=shopify.ShopifyStore('Worldwide Cyclery','Worldwide Cyclery','https://www.worldwidecyclery.com',
    collection='deals',types=TYPES,brand_of=brands.for_sport(sports.MTB),own_vendor='worldwide',
    title_part=title_part,unknown_by_title=True)
FANATIK=shopify.ShopifyStore('Fanatik','Fanatik','https://www.fanatikbike.com',
    collection='fanatik-outlet',types=TYPES,brand_of=brands.for_sport(sports.MTB),own_vendor='fanatik',
    title_part=title_part,unknown_by_title=True)
STORES=(WORLDWIDE,FANATIK)


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
