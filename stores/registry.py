"""Build the ordered list of store/part scrapers for one run."""

import logging

from stores.ccs import scrapers as ccs_scrapers
from stores.muirskate import DISABLED_REASON as MUIR_REASON
from stores.muirskate import ENABLED as MUIR_ENABLED
from stores.muirskate import scrapers as muir_scrapers
from stores.skatedeluxe import DISABLED_REASON as DELUXE_REASON
from stores.skatedeluxe import ENABLED as DELUXE_ENABLED
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
    if DELUXE_ENABLED:
        scrapers.extend(skatedeluxe_scrapers())
    else:
        logger.warning("Skate Deluxe disabled: %s", DELUXE_REASON)
    if MUIR_ENABLED:
        scrapers.extend(muir_scrapers())
    else:
        logger.warning("Muir Skate disabled: %s", MUIR_REASON)
    return scrapers
