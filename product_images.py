"""Store placeholder images aren't product photos (owner, 2026-11-18: the
email's Top deal showed The House's "Image coming soon").

* The House: ``.../images/noimage-hou.png`` when a product has no photo.
* Zumiez: a "store app" badge (``product-flag-store-app...png``) saved as the
  first image; the product photo is the next one.

A listing whose image is a placeholder takes its next real image, or none.
Real file names that merely contain "placeholder" (Fanatik's
"ibis-ripley-v3_green_side_placeholder_....jpg" are bike photos) are kept.
"""

import re

_PLACEHOLDER = re.compile(
    r"/noimage[-_.]|/no[-_]image[-_.]|image[-_]coming[-_]soon|coming[-_]soon[-_.][a-z]*\.(?:png|jpe?g|gif|svg)|"
    r"/product-flag-[^/]*\.(?:png|svg)",
    re.I)


def is_placeholder(url):
    return bool(_PLACEHOLDER.search(str(url or "")))


def clean(item):
    """Drop placeholder images from one listing in place; True when it changed."""
    if not isinstance(item, dict):
        return False
    changed = False
    images = item.get("images")
    if isinstance(images, list):
        real = [url for url in images if url and not is_placeholder(url)]
        if real != images:
            changed = True
            if real:
                item["images"] = real
            else:
                item.pop("images", None)
    if is_placeholder(item.get("image")):
        changed = True
        replacement = next((url for url in item.get("images") or [] if url), "")
        if replacement:
            item["image"] = replacement
        else:
            item.pop("image", None)
    return changed


def clean_items(data):
    """Clean every listing in a catalog in place; returns how many changed."""
    return sum(1 for items in (data or {}).values() for item in items or [] if clean(item))
