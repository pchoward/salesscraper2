"""Cloudflare Web Analytics beacon on the generated deal page."""

import unittest

from report import build_report_html


BEACON = (
    "<!-- Cloudflare Web Analytics -->"
    "<script defer src='https://static.cloudflareinsights.com/beacon.min.js' "
    'data-cf-beacon=\'{"token": "542cbf4d24534b70be3715cefe0e6a8e"}\'></script>'
    "<!-- End Cloudflare Web Analytics -->"
)
TOKEN = "542cbf4d24534b70be3715cefe0e6a8e"


class CloudflareAnalyticsTests(unittest.TestCase):
    def test_beacon_script_with_token_appears_once_before_body_close(self):
        html = build_report_html({}, {}, generated_at="2026-10-25T12:00:00+00:00")
        self.assertEqual(html.count(BEACON), 1)
        self.assertEqual(html.count(TOKEN), 1)
        snippet_at = html.index(BEACON)
        body_at = html.index("</body>")
        self.assertLess(snippet_at, body_at)
        self.assertEqual(html[snippet_at + len(BEACON):body_at].strip(), "")


if __name__ == "__main__":
    unittest.main()
