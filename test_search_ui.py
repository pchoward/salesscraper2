"""The search box in a real browser: chips, suggestions, keyboard, highlights,
close matches, and a search restored from the URL (tasks/search-upgrade.md)."""

import json
import os
import signal
import subprocess
import tempfile
import unittest
from pathlib import Path

from report import build_report_html


def _item(name, store, part, price, old="59.99", **extra):
    slug = "".join(ch if ch.isalnum() else "-" for ch in name.lower()).strip("-")
    item = {"name": name, "url": f"https://www.zumiez.com/{slug}.html", "price_new": price, "price_old": old,
            "part": part, "store": store}
    item.update(extra)
    return item


CATALOG = {
    "Zumiez_Wheels": [
        _item("Spitfire Formula Four Classic 54mm 99a Wheels", "Zumiez", "Wheels", "24.99"),
        _item("Spitfire Formula Four Conical Full 54mm 99a Wheels", "Zumiez", "Wheels", "39.99"),
        _item("Spitfire Formula Four Classic 56mm 99a Wheels", "Zumiez", "Wheels", "22.99"),
        _item("Spitfire Formula Four Classic 54mm 97a Wheels", "Zumiez", "Wheels", "21.99"),
        _item("OJ Elite Mini Combo 54mm 99a Wheels", "Zumiez", "Wheels", "19.99"),
    ],
    "Zumiez_Decks": [
        _item("Baker Brand Logo 8.25\" Skateboard Deck", "Zumiez", "Decks", "44.99", old="69.95"),
        _item("Baker Team Deck 8.5\" Skateboard Deck", "Zumiez", "Decks", "49.99", old="69.95"),
    ],
}

DRIVER = r"""
<script>
window.addEventListener("load", () => {
  const out = {};
  const input = document.getElementById("searchInput");
  const live = () => Array.from(document.querySelectorAll("#cardGrid .deal-card"))
    .filter(card => !card.classList.contains("filtered-out") && !card.classList.contains("grouped-hide"))
    .map(card => card.dataset.name);
  const chips = () => Array.from(document.querySelectorAll("#searchChips .search-chip")).map(chip => chip.textContent);
  function type(text) {
    input.focus();
    input.value = text;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    clearTimeout(filterTimer);
    applyFilters();
  }
  function key(name, target) {
    (target || input).dispatchEvent(new KeyboardEvent("keydown", { key: name, bubbles: true, cancelable: true }));
  }
  try {
    out.restored = { value: input.value, chips: chips(), deals: live() };

    type("spitfire 54mm 99a under 30");
    out.acceptance = { chips: chips(), deals: live(), sort: document.getElementById("sortSelect").value,
      marks: Array.from(document.querySelectorAll("#cardGrid .deal-card:not(.filtered-out) mark.search-hit")).map(mark => mark.textContent) };

    Array.from(document.querySelectorAll("#searchChips .search-chip")).find(chip => chip.textContent.startsWith("<")).click();
    out.removed = { value: input.value, deals: live().length };

    type("spitfire 54mm 99a under 20");
    const rescue = document.getElementById("searchRescue");
    out.rescue = rescue ? rescue.innerText : "";

    type("spi");
    out.suggest = { expanded: input.getAttribute("aria-expanded"),
      groups: Array.from(document.querySelectorAll("#searchSuggest .search-suggest-head")).map(head => head.textContent),
      options: document.querySelectorAll("#searchSuggest [role=option]").length };
    key("ArrowDown");
    out.activeOption = (document.getElementById(input.getAttribute("aria-activedescendant")) || {}).textContent || "";
    key("Enter");
    out.picked = { value: input.value, brand: document.getElementById("brandSelect").value, part: state.part, deals: live().length };
    setSelect("brandSelect", "all");

    type("oj");
    key("Escape");
    out.escape = input.getAttribute("aria-expanded");

    input.blur();
    key("/", document.body);
    out.slash = document.activeElement === input;

    type("bakr 7.5 under 10");
    out.didYouMean = (document.getElementById("searchRescue") || {}).innerText || "";
  } catch (err) {
    out.error = String(err && err.stack || err);
  }
  document.documentElement.dataset.result = JSON.stringify(out);
});
</script>
"""


def _render(html, query=""):
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
        path = Path(directory) / "page.html"
        path.write_text(html.replace("</body>", DRIVER + "</body>"), encoding="utf-8")
        command = [
            "google-chrome", "--headless=new", "--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage",
            f"--user-data-dir={directory}/chrome", "--window-size=1280,900", "--virtual-time-budget=4000",
            "--dump-dom", path.as_uri() + query,
        ]
        # Headless Chrome prints the DOM and then lingers on DBus.
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, start_new_session=True)
        try:
            rendered, _err = proc.communicate(timeout=40)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            rendered, _err = proc.communicate()
    marker = 'data-result="'
    start = (rendered or "").find(marker)
    if start < 0:
        raise AssertionError("no result: " + (rendered or "")[-600:])
    raw = rendered[start + len(marker):rendered.index('"', start + len(marker))]
    from html import unescape
    return json.loads(unescape(raw))


class SearchUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = build_report_html(CATALOG, {}, {}, generated_at="2026-11-01T12:00:00+00:00")
        cls.result = _render(cls.html)

    def test_no_errors(self):
        self.assertNotIn("error", self.result, self.result.get("error"))

    def test_the_acceptance_query(self):
        acceptance = self.result["acceptance"]
        self.assertEqual(acceptance["deals"], ["Spitfire Formula Four Classic 54mm 99a Wheels"],
                         "only Spitfire 54mm 99a at $30 or less, from the Decks view")
        self.assertEqual(acceptance["chips"], ["54mm ×", "99a ×", "< $30 ×", "Showing Wheels"])
        self.assertEqual(acceptance["sort"], "relevance")
        self.assertIn("Spitfire", acceptance["marks"])
        self.assertIn("54mm", acceptance["marks"])

    def test_removing_a_chip_removes_its_words(self):
        self.assertEqual(self.result["removed"]["value"], "spitfire 54mm 99a")
        self.assertEqual(self.result["removed"]["deals"], 2)

    def test_nothing_matches_offers_close_matches(self):
        rescue = self.result["rescue"]
        self.assertIn("Close matches without < $20 (2)", rescue)
        self.assertIn("Spitfire Formula Four Classic 54mm 99a Wheels", rescue)
        self.assertIn("Did you mean Baker?", self.result["didYouMean"])

    def test_suggestions_and_keyboard(self):
        suggest = self.result["suggest"]
        self.assertEqual(suggest["expanded"], "true")
        self.assertEqual(suggest["groups"][0], "Brands")
        self.assertIn("Products", suggest["groups"])
        self.assertLessEqual(suggest["options"], 8)
        self.assertTrue(self.result["activeOption"].startswith("Spitfire"))
        picked = self.result["picked"]
        self.assertEqual((picked["value"], picked["brand"], picked["part"]), ("", "Spitfire", "Wheels"),
                         "a brand applies as a filter and opens the category it is in")
        self.assertEqual(picked["deals"], 4)
        self.assertEqual(self.result["escape"], "false")
        self.assertTrue(self.result["slash"], "/ focuses the search box")

    def test_a_search_in_the_url_is_restored(self):
        restored = _render(self.html, "?q=spitfire+54mm")["restored"]
        self.assertEqual(restored["value"], "spitfire 54mm")
        self.assertEqual(restored["chips"], ["54mm ×", "Showing Wheels"])
        self.assertEqual(sorted(restored["deals"]), ["Spitfire Formula Four Classic 54mm 97a Wheels",
                                                     "Spitfire Formula Four Classic 54mm 99a Wheels",
                                                     "Spitfire Formula Four Conical Full 54mm 99a Wheels"])

    def test_the_combobox_markup(self):
        self.assertIn('role="combobox"', self.html)
        self.assertIn('aria-controls="searchSuggest"', self.html)
        self.assertIn('id="searchSuggest" class="search-suggest" role="listbox"', self.html)
        self.assertIn('id="searchChips"', self.html)
        self.assertIn("SkateSearch.configure(", self.html)


if __name__ == "__main__":
    unittest.main()
