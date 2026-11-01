"""The read-only store probe (audit/store_probe.py): robots.txt first,
platform detection, sale sections, and what a Shopify sale collection says
about filters. All offline, with canned responses."""

import json
import unittest
from pathlib import Path

import yaml

from audit import store_probe

SHOPIFY_HOME = """<html><head><script src="https://cdn.shopify.com/s/files/theme.js"></script></head><body>
<a href="/collections/clearance">Clearance</a> <a href="/collections/frames">Frames</a>
<a href="/pages/scratch-and-dent">Scratch &amp; Dent</a> <a href="https://elsewhere.com/sale">Partner sale</a>
</body></html>"""

PRODUCTS = {"products": [
    {"product_type": "Frames", "vendor": "Cult", "tags": ["frames", "chromoly"],
     "options": [{"name": "Top Tube"}, {"name": "Color"}],
     "variants": [{"price": "299.99", "compare_at_price": "399.99"}]},
    {"product_type": "Hubs", "vendor": "Odyssey", "tags": ["freecoaster"],
     "options": [{"name": "Drive Side"}],
     "variants": [{"price": "150.00", "compare_at_price": None}]},
    {"product_type": "Frames", "vendor": "Kink", "tags": ["frames"],
     "options": [{"name": "Top Tube"}],
     "variants": [{"price": "250.00", "compare_at_price": "260.00"}]},
]}


class FakeSite:
    def __init__(self, pages):
        self.pages = pages
        self.asked = []

    def __call__(self, url, accept):
        self.asked.append(url)
        return self.pages.get(url, (404, ""))


class ProbeTests(unittest.TestCase):
    def test_a_shopify_store_reports_platform_sale_sections_and_filter_fields(self):
        base = "https://shop.example"
        site = FakeSite({
            base + "/robots.txt": (200, "User-agent: *\nDisallow: /cart\nCrawl-delay: 5\n"),
            base + "/": (200, SHOPIFY_HOME),
            base + "/collections.json?limit=250": (200, json.dumps({"collections": [
                {"handle": "clearance", "title": "Clearance", "products_count": 3},
                {"handle": "frames", "title": "Frames", "products_count": 40},
                {"handle": "on-sale", "title": "On Sale", "products_count": 1}]})),
            base + "/collections/clearance/products.json?limit=250": (200, json.dumps(PRODUCTS)),
        })
        waits = []
        report = store_probe.probe({"name": "Shop", "url": base}, fetch=site, sleep=waits.append)
        self.assertEqual(report["platform"], ["Shopify"])
        self.assertEqual(report["robots"], {"status": 200, "crawl_delay": 5})
        self.assertEqual([link["text"] for link in report["sale_links"]], ["Clearance", "Scratch & Dent"],
                         "same-site sale links only")
        shop = report["shopify"]
        self.assertEqual([c["handle"] for c in shop["sale_collections"]], ["clearance", "on-sale"])
        self.assertEqual(shop["sampled"], "clearance", "the biggest sale collection is sampled")
        self.assertEqual((shop["products"], shop["marked_down"]), (3, 2))
        self.assertEqual(shop["product_types"][0], ("Frames", 2))
        self.assertIn(("Top Tube", 2), shop["variant_options"])
        self.assertIn(("Drive Side", 1), shop["variant_options"])
        self.assertEqual(len(site.asked), 4, "a handful of requests per store")
        self.assertTrue(all(wait >= store_probe.DELAY for wait in waits), "spaced out")
        table = store_probe.markdown([report])
        self.assertIn("| [Shop](https://shop.example/) | Shopify | 200, crawl-delay 5 |", table)
        self.assertIn("**Variant options (filter candidates):** Top Tube (2)", table)

    def test_robots_txt_is_obeyed(self):
        base = "https://closed.example"
        site = FakeSite({base + "/robots.txt": (200, "User-agent: *\nDisallow: /\n")})
        report = store_probe.probe({"url": base}, fetch=site, sleep=lambda seconds: None)
        self.assertEqual(site.asked, [base + "/robots.txt"], "nothing else is fetched")
        self.assertIn("robots.txt disallows /", report["notes"])

    def test_other_platforms_and_failures_are_reported_not_raised(self):
        base = "https://big.example"
        site = FakeSite({base + "/robots.txt": (404, ""),
                         base + "/": (200, '<script src="https://cdn11.bigcommerce.com/s-1/x.js"></script><a href="/sale/">Sale</a>')})
        report = store_probe.probe({"url": base}, fetch=site, sleep=lambda seconds: None)
        self.assertEqual(report["platform"], ["BigCommerce"])
        self.assertIsNone(report["shopify"], "Shopify feeds are only read on Shopify stores")
        self.assertEqual(report["sale_links"][0]["url"], base + "/sale/")
        down = FakeSite({"https://down.example/robots.txt": ("URLError", "")})
        report = store_probe.probe({"url": "https://down.example"}, fetch=down, sleep=lambda seconds: None)
        self.assertEqual(report["home_status"], 404)

    def test_candidates_and_workflow_are_read_only(self):
        candidates = json.loads(Path("audit/store_candidates.json").read_text(encoding="utf-8"))
        for sport in ("bmx", "mtb", "ski"):
            self.assertTrue(candidates[sport])
            for store in candidates[sport]:
                self.assertTrue(store["url"].startswith("https://"), store)
        self.assertIn("https://www.danscomp.com", [store["url"] for store in candidates["bmx"]])
        workflow = yaml.safe_load(Path(".github/workflows/store-probe.yml").read_text(encoding="utf-8"))
        triggers = workflow.get("on", workflow.get(True))
        self.assertEqual(list(triggers), ["workflow_dispatch"], "only run by hand")
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        text = Path(".github/workflows/store-probe.yml").read_text(encoding="utf-8")
        self.assertNotIn("${{ secrets.", text)
        self.assertNotIn("git push", text)


if __name__ == "__main__":
    unittest.main()
