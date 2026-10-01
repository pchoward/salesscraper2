"""Product image and spec extraction for listing cards.

Image problems are logged by the caller. This module returns an empty image
instead of raising on odd markup.
"""

import logging
from urllib.parse import urljoin

from dimensions import extract_specs

logger = logging.getLogger("media")

_SKIP_TOKENS = (
    "placeholder",
    "spacer",
    "blank.gif",
    "pixel.gif",
    "loading.gif",
    "data:image",
    "base64",
    "sprite",
    "1x1",
)
_ATTRS = ("data-src", "data-original", "data-lazy-src", "data-zoom-image", "data-image", "src")


def _clean_image_url(raw, base):
    if not raw:
        return ""
    text = str(raw).strip().split(",")[0].strip().split()[0]
    if not text or text.startswith("data:"):
        return ""
    if text.startswith("//"):
        text = "https:" + text
    elif text.startswith("/") and base:
        text = urljoin(base if base.endswith("/") else base + "/", text)
    if not text.startswith("http"):
        return ""
    lowered = text.lower()
    if any(token in lowered for token in _SKIP_TOKENS):
        return ""
    return text


def _best_srcset(srcset, base):
    best_url = ""
    best_width = -1
    for part in str(srcset or "").split(","):
        bits = part.strip().split()
        if not bits:
            continue
        url = _clean_image_url(bits[0], base)
        width = 0
        if len(bits) > 1 and bits[1].endswith("w"):
            try:
                width = int(float(bits[1][:-1]))
            except ValueError:
                width = 0
        elif len(bits) > 1 and bits[1].endswith("x"):
            try:
                width = int(float(bits[1][:-1]) * 1000)
            except ValueError:
                width = 0
        if url and width >= best_width:
            best_url = url
            best_width = width
    return best_url


def _images(node):
    if node is None:
        return []
    name = getattr(node, "name", None)
    if name == "img":
        return [node]
    finder = getattr(node, "find_all", None)
    if not finder:
        return []
    return node.find_all("img")


def extract_image_url(node, base=""):
    """First usable image URL under ``node``, or ``""``."""
    try:
        for img in _images(node):
            for attr in _ATTRS:
                if attr == "src":
                    continue
                found = _clean_image_url(img.get(attr), base)
                if found:
                    return found
            srcset = img.get("data-srcset") or img.get("srcset") or ""
            found = _best_srcset(srcset, base)
            if found:
                return found
            found = _clean_image_url(img.get("src"), base)
            if found:
                return found
    except Exception as exc:
        logger.error("Image extract failed: %s", exc)
    return ""


def _nearby_image(node, base):
    image = extract_image_url(node, base)
    if image or node is None:
        return image
    parent = getattr(node, "parent", None)
    parent_name = getattr(parent, "name", None)
    if parent is None or parent_name in {None, "[document]", "html", "body"}:
        return ""
    return extract_image_url(parent, base)


def _node_text(node):
    if node is None:
        return ""
    getter = getattr(node, "get_text", None)
    if not getter:
        return ""
    try:
        return getter(" ", strip=True)
    except Exception:
        return ""


def attach_listing_media(item, node, base):
    """Set ``image``, ``width``, ``length``, and ``wheelbase`` when found.

    Leaves the item unchanged when nothing is there. Does not raise.
    """
    if not isinstance(item, dict):
        return item
    try:
        image = _nearby_image(node, base)
        if image:
            item["image"] = image
        specs = extract_specs(item.get("name") or "", _node_text(node))
        for field in ("width", "length", "wheelbase"):
            if specs.get(field) is not None:
                item[field] = specs[field]
    except Exception as exc:
        logger.error("Listing media failed: %s", exc)
    return item
