"""First MTB stores from Claude's #137 collection probe; one shared feed/store."""
import logging
import sports
from sports import brands
from stores import shopify
from sports.mtb.rules import PARTS,title_part
from sports.mtb.specs import extract

logger=logging.getLogger('stores.mtb')
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


class MtbShopifyScraper(shopify.ShopifyScraper):
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
            offers.append({'variant_id':variant.get('id'),'price':float(variant['price']),
                           'compare':float(variant['compare_at_price']),
                           'available':variant.get('available') if isinstance(variant.get('available'),bool) else None,
                           'specs':specs})
        item['technical_offers']=offers
        aggregate={}
        for offer in offers:
            for key,values in offer['specs'].items():aggregate.setdefault(key,set()).update(values)
        item['technical_specs']={k:sorted(v) for k,v in aggregate.items()}
        if warnings:item['spec_warnings']=sorted(warnings)
        cheapest=min(offers,key=lambda v:v['price'])
        item['availability']='In stock' if cheapest['available'] is True else 'Check store'
        return item


def scrapers():
    return [MtbShopifyScraper(store,part) for store in STORES for part in PARTS]
