"""Build the ordered list of store/part scrapers for one run."""

import logging

from stores.ccs import scrapers as ccs_scrapers
from stores.muirskate import DISABLED_REASON, ENABLED as MUIR_ENABLED
from stores.muirskate import scrapers as muir_scrapers
from stores.skatedeluxe import scrapers as skatedeluxe_scrapers
from stores.skatewarehouse import scrapers as skatewarehouse_scrapers
from stores.tactics import scrapers as tactics_scrapers
from stores.zumiez import scrapers as zumiez_scrapers

logger = logging.getLogger("stores.registry")


def build_scrapers():
    scrapers = []
    scrapers.extend(zumiez_scrapers())
    scrapers.extend(skatewarehouse_scrapers())
    scrapers.extend(ccs_scrapers())
    scrapers.extend(tactics_scrapers())
    scrapers.extend(skatedeluxe_scrapers())
    if MUIR_ENABLED:
        scrapers.extend(muir_scrapers())
    else:
        logger.warning("Muir Skate disabled: %s", DISABLED_REASON)
    return scrapers
