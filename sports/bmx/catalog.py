"""BMX-only enrichment atop the shared Shopify parser; never extra requests."""
import logging

from stores.shopify import ShopifyScraper
from product_specs import text
from sports.bmx.quality import ELIGIBLE_WHEELS, decimal, scope_reason, variant_specs

logger = logging.getLogger('stores.bmx')


class BmxShopifyScraper(ShopifyScraper):
    def __init__(self, store, part):
        super().__init__(store, part)
        self.catalog_scope_exclusions = {}

    def _item(self, product, name, url, variants):
        self.catalog_scope_exclusions.pop(url, None)
        reason = scope_reason(name, self.part, text(product.get('body_html','')), product.get('product_type',''))
        if reason:
            self.catalog_scope_exclusions[url] = 'catalog scope: ' + reason
            return None
        offers = []
        eligible = []
        warnings = set()
        for variant in variants:
            try:
                specs, conflicts = variant_specs(product, variant, self.part)
            except (AttributeError, TypeError, ValueError) as exc:
                logger.warning('Optional BMX specifications skipped for %s (%s)', url, type(exc).__name__)
                specs, conflicts = {}, ['unreadable variant specifications']
            if conflicts:
                warnings.update(conflicts)
                # A spec conflict withholds fit fields, not the whole listing.
            sizes = specs.get('wheel_size_inches', [])
            if sizes and not set(sizes) & ELIGIBLE_WHEELS:
                continue
            eligible.append(variant)
            offer = {'variant_id': variant.get('id'), 'price': decimal(variant.get('price')),
                     'compare_at': decimal(variant.get('compare_at_price')),
                     'availability': 'In stock' if variant.get('available') is True else 'Check store',
                     'specs': specs}
            offers.append(offer)
        if not eligible:
            self.catalog_scope_exclusions[url] = 'catalog scope: no eligible 20/22-inch variants'
            if warnings:
                logger.warning('BMX specification conflict; omitted %s: %s', url, ', '.join(sorted(warnings)))
            return None
        item = super()._item(product, name, url, eligible)
        if item is None:
            return None
        item['bmx_offers'] = offers
        specs = {}
        for offer in offers:
            for field, values in offer['specs'].items():
                specs.setdefault(field, set()).update(values)
        item['bmx_specs'] = {field: sorted(values, key=float) for field, values in specs.items()}
        item['price_basis'] = 'retailer_compare_at'
        # A single listing can have unknown-stock variants; do not promote it
        # to a blanket in-stock assertion. Prices/offers remain size-specific.
        if warnings:
            item['bmx_spec_warnings'] = sorted(warnings)
        return item
