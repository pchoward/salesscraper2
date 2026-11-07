import builtins
import unittest
from unittest import mock

import report


class WheelsWithoutParserTest(unittest.TestCase):
    """A rebuild without BeautifulSoup installed dropped every wheel."""

    def test_wheels_stay_on_the_page_when_the_parser_is_missing(self):
        real_import = builtins.__import__

        def no_parser(name, *args, **kwargs):
            if name in ("product_specs", "bs4"):
                raise ImportError(f"No module named {name!r}")
            return real_import(name, *args, **kwargs)

        data = {"TGM_Wheels": [{
            "name": "Spitfire Formula Four 53mm 99a Classic Wheels", "url": "https://shop.test/wheels-1",
            "price_new": "30.00", "price_old": "40.00", "part": "Wheels", "store": "TGM",
        }]}
        with mock.patch("builtins.__import__", side_effect=no_parser):
            html = report.build_report_html(data, {}, {}, set(), generated_at="2026-11-06T10:00:00+00:00")
        self.assertIn('data-part="Wheels" data-count="1"', html)


if __name__ == "__main__":
    unittest.main()
