"""Subscriber alert delivery: config, signing, journal mapping, and an end-to-end
run against the real Worker in mock mode (skipped when Node 22.5+ is missing)."""

import json
import logging
import os
import re
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path

import alerts_delivery as ad
from notification_engine import _hash, load_state

SECRET = "s" * 40
DAY = "2026-10-20"
ITEM = {
    "name": 'Heroin Egg 8.75" Skateboard Deck',
    "url": "https://www.zumiez.com/heroin-egg-8-75-skateboard-deck.html",
    "price_new": "54.99",
    "price_old": "79.95",
    "part": "Decks",
    "store": "Zumiez",
    "width": 8.75,
    "image": "https://scene7.zumiez.com/is/image/zumiez/1",
}
CATALOG = {"Zumiez_Decks": [ITEM]}
RULE = {"id": "r_" + "1" * 24, "brand": "Heroin", "part": "Decks", "min_width": 8.6, "max_price": 60, "note": "Wide Heroin decks"}

# Shared with worker/test/internal.test.js.
VECTORS = [
    ("POST", "/v1/internal/deliveries", '{"version":1,"deliveries":[]}',
     "v1=7115ad864013276f5144ac589e5e7f3a8d5019d286630fe9aa2884df9fb398cc"),
    ("GET", "/v1/internal/routes", "", "v1=d6d386510dbec0accbf2f2fcadb071d9c36006fa266db360b7bb4bf9c6508c0b"),
]


class FakeWorker:
    """Answers like the Worker: signed requests only, per-event dedup."""

    def __init__(self, routes, outcome="sent"):
        self.routes = routes
        self.outcome = outcome
        self.calls = []
        self.sent_events = set()
        self.down = False

    def __call__(self, method, url, headers, body):
        if self.down:
            raise ConnectionRefusedError("down")
        path = url.split("https://alerts.example.test", 1)[1]
        expected = ad.signature(SECRET, method, path, headers["X-SkateDeals-Timestamp"], headers["X-SkateDeals-Nonce"], body)
        assert headers["X-SkateDeals-Signature"] == expected, "request is signed"
        self.calls.append((method, path, json.loads(body) if body else None))
        if path == "/v1/internal/routes":
            return 200, json.dumps({"version": 1, "routes": self.routes}).encode()
        results = []
        for delivery in json.loads(body)["deliveries"]:
            ids = {eid for hit in delivery["hits"] for eid in hit["event_ids"]}
            if "digest" in delivery:
                ids.add(delivery["digest"]["event_id"])
            status = self.outcome
            if status == "sent":
                status = "duplicate" if ids <= self.sent_events else "sent"
                self.sent_events |= ids
            results.append({"route_id": delivery["route_id"], "delivery_id": delivery["delivery_id"], "status": status})
        return 200, json.dumps({"version": 1, "results": results}).encode()


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.env = {
            "ALERTS_DELIVERY_ENABLED": "1",
            "ALERTS_API_URL": "https://alerts.example.test",
            "ALERTS_HMAC_SECRET": SECRET,
            "ALERTS_STATE_DIR": str(self.dir / "alerts_state"),
            "ALERTS_ALLOW_BOOTSTRAP": "1",
        }

    def run_once(self, worker, catalog=CATALOG, failed=(), env=None, day=DAY):
        return ad.deliver_subscriber_alerts(catalog, {}, failed, previous={}, day=day, env=env or self.env, transport=worker)

    def route_state(self, route_id):
        return load_state(Path(self.env["ALERTS_STATE_DIR"]) / f"{_hash(route_id)}.json")


class ConfigTests(Base):
    def test_signature_matches_the_worker_vectors(self):
        for method, path, body, expected in VECTORS:
            self.assertEqual(ad.signature("vector-secret-".ljust(40, "x"), method, path, 1790000000, "nonce_0123456789abcdef", body), expected)

    def test_disabled_by_default(self):
        worker = FakeWorker([])
        self.assertEqual(ad.deliver_subscriber_alerts(CATALOG, {}, env={}, transport=worker)["status"], "disabled")
        self.assertEqual(worker.calls, [])

    def test_misconfiguration_fails_closed_and_logs_names_only(self):
        for override, problem in [({"ALERTS_API_URL": "http://alerts.example.test"}, "ALERTS_API_URL"),
                                  ({"ALERTS_API_URL": "https://alerts.example.test/v1"}, "ALERTS_API_URL"),
                                  ({"ALERTS_HMAC_SECRET": "short-secret-value"}, "ALERTS_HMAC_SECRET")]:
            worker = FakeWorker([])
            with self.assertLogs("alerts_delivery", level="ERROR") as logs:
                summary = self.run_once(worker, env=dict(self.env, **override))
            self.assertEqual(summary["status"], "misconfigured")
            self.assertEqual(worker.calls, [])
            self.assertIn(problem, logs.output[0])
            self.assertNotIn("short-secret-value", "".join(logs.output))

    def test_missing_journal_needs_explicit_bootstrap(self):
        worker = FakeWorker([{"route_id": "route_a", "rules": [RULE]}])
        env = dict(self.env, ALERTS_ALLOW_BOOTSTRAP="")
        self.assertEqual(self.run_once(worker, env=env)["status"], "state_missing")
        self.assertEqual(worker.calls, [])


class DeliveryTests(Base):
    def test_sends_once_and_never_repeats(self):
        worker = FakeWorker([{"route_id": "route_a", "rules": [RULE]}])
        summary = self.run_once(worker)
        self.assertEqual((summary["status"], summary["deliveries"], summary["results"]), ("ok", 1, {"sent": 1}))
        post = worker.calls[-1][2]
        self.assertEqual(post["version"], 1)
        [delivery] = post["deliveries"]
        self.assertEqual(delivery["route_id"], "route_a")
        [hit] = delivery["hits"]
        self.assertEqual(hit["reasons"], ["Maximum price reached"])
        self.assertEqual(hit["note"], "Wide Heroin decks")
        self.assertEqual(set(hit["item"]), {"name", "store", "part", "url", "price_new", "price_old"})
        self.assertEqual(delivery["delivery_id"], _hash(sorted(hit["event_ids"])))
        self.assertEqual({e["status"] for e in self.route_state("route_a")["events"].values()}, {"delivered"})

        again = self.run_once(worker, day="2026-10-21")
        self.assertEqual(again["deliveries"], 0, "a condition that stays true does not alert again")
        self.assertEqual([call[1] for call in worker.calls].count("/v1/internal/deliveries"), 1)

    def test_failed_or_unreachable_stays_queued_and_retries_the_same_events(self):
        worker = FakeWorker([{"route_id": "route_a", "rules": [RULE]}], outcome="failed")
        self.run_once(worker)
        first_ids = worker.calls[-1][2]["deliveries"][0]["hits"][0]["event_ids"]
        self.assertEqual({e["status"] for e in self.route_state("route_a")["events"].values()}, {"pending"})

        worker.outcome = "sent"
        original = worker.__call__

        def drop_post(method, url, headers, body):
            if method == "POST":
                raise TimeoutError("timed out")
            return original(method, url, headers, body)

        with self.assertLogs("alerts_delivery", level="ERROR"):
            self.run_once(drop_post, day="2026-10-21")
        self.assertEqual({e["status"] for e in self.route_state("route_a")["events"].values()}, {"pending"})

        self.run_once(worker, day="2026-10-22")
        retried = worker.calls[-1][2]["deliveries"][0]["hits"][0]["event_ids"]
        self.assertEqual(retried, first_ids, "the retry carries the same event ids, so the Worker can dedup")
        self.assertEqual({e["status"] for e in self.route_state("route_a")["events"].values()}, {"delivered"})

    def test_uncertain_holds_the_watch(self):
        worker = FakeWorker([{"route_id": "route_a", "rules": [RULE]}], outcome="uncertain")
        self.run_once(worker)
        state = self.route_state("route_a")
        self.assertEqual({e["status"] for e in state["events"].values()}, {"uncertain"})
        self.assertTrue(all(record.get("blocked") for record in state["records"].values()))

    def test_routes_api_down_changes_nothing(self):
        worker = FakeWorker([{"route_id": "route_a", "rules": [RULE]}])
        worker.down = True
        with self.assertLogs("alerts_delivery", level="ERROR"):
            self.assertEqual(self.run_once(worker)["status"], "api_unavailable")
        self.assertFalse((Path(self.env["ALERTS_STATE_DIR"]) / f"{_hash('route_a')}.json").exists())

    def test_failed_scrape_produces_no_alert(self):
        worker = FakeWorker([{"route_id": "route_a", "rules": [RULE]}])
        self.assertEqual(self.run_once(worker, failed=("Zumiez_Decks",))["deliveries"], 0)

    def test_subscribers_are_isolated_and_departures_are_forgotten(self):
        worker = FakeWorker([{"route_id": "route_a", "rules": [RULE]}, {"route_id": "route_b", "rules": [dict(RULE, max_price=50)]}])
        summary = self.run_once(worker)
        self.assertEqual(summary["deliveries"], 1, "route_b's $50 ceiling is not met")
        state_dir = Path(self.env["ALERTS_STATE_DIR"])
        self.assertTrue((state_dir / f"{_hash('route_b')}.json").exists())
        worker.routes = [{"route_id": "route_a", "rules": [RULE]}]
        self.run_once(worker, day="2026-10-21")
        self.assertFalse((state_dir / f"{_hash('route_b')}.json").exists(), "an unsubscribed route's journal is deleted")
        manifest = json.loads((state_dir / "manifest.json").read_text())
        self.assertEqual(manifest["routes"], [_hash("route_a")])

    def test_lost_journal_for_a_known_route_skips_it(self):
        worker = FakeWorker([{"route_id": "route_a", "rules": [RULE]}])
        self.run_once(worker)
        (Path(self.env["ALERTS_STATE_DIR"]) / f"{_hash('route_a')}.json").unlink()
        with self.assertLogs("alerts_delivery", level="WARNING"):
            summary = self.run_once(worker, catalog={"Zumiez_Decks": [dict(ITEM, price_new="44.99")]}, day="2026-10-21")
        self.assertEqual(summary["deliveries"], 0)

    def test_invalid_rules_are_dropped_and_bad_payloads_rejected(self):
        bad_rules = [{"brand": "Heroin", "part": "Skis"}, {"brand": "<b>"}, {"brand": "Heroin", "email": "x@y.z"}, RULE]
        self.assertEqual(ad.parse_routes({"version": 1, "routes": [{"route_id": "route_a", "rules": bad_rules}]}), {"route_a": [RULE]})
        for payload in [{"version": 2, "routes": []}, {"version": 1, "routes": [{"route_id": "has space", "rules": []}]}, []]:
            with self.assertRaises(ValueError):
                ad.parse_routes(payload)

    def test_payload_carries_no_private_fields(self):
        worker = FakeWorker([{"route_id": "route_a", "rules": [RULE]}])
        private = dict(ITEM, email="someone@example.com", description="x")
        self.run_once(worker, catalog={"Zumiez_Decks": [private]})
        sent = json.dumps(worker.calls[-1][2])
        self.assertNotIn("someone@example.com", sent)
        self.assertNotIn("image", sent)


CCS_COLLECTION = "https://shop.ccs.com/collections/sale/products/baker-brand-logo-deck-8-25"
CCS_PRODUCT = "https://shop.ccs.com/products/baker-brand-logo-deck-8-25"
WATCH = {"id": "r_" + "2" * 24, "kind": "watch", "product_url": ITEM["url"], "product_key": ITEM["url"], "max_price": 60}
DIGEST = {"id": "r_" + "3" * 24, "kind": "digest"}


def _deck(name, url, price, store="Zumiez", old="79.95", width=None):
    return {"name": name, "url": url, "price_new": price, "price_old": old, "part": "Decks", "store": store,
            **({"width": width} if width is not None else {})}


def _filler(store, count):
    return [_deck(f"Filler Brand Logo {n} 8.0 Skateboard Deck", f"https://www.zumiez.com/filler-{store}-{n}.html", "49.99", width=8.0)
            for n in range(count)]


class KindsTests(Base):
    """Issue #70: product watches by identity, and the general daily digest."""

    def run_day(self, worker, catalog, previous, day, history=None, failed=()):
        return ad.deliver_subscriber_alerts(catalog, history or {}, failed, previous=previous, day=day, env=self.env, transport=worker)

    def deliveries(self, worker):
        return [call[2]["deliveries"] for call in worker.calls if call[1] == "/v1/internal/deliveries"]

    def test_product_keys_match_the_worker_vectors(self):
        vectors = json.loads((Path(__file__).resolve().parent / "worker" / "contract" / "product-keys.json").read_text())
        for row in vectors["keys"]:
            self.assertEqual(ad.watch_key(row["url"]), row["key"], row["why"])
        email_js = (Path(__file__).resolve().parent / "worker" / "src" / "email.js").read_text()
        block = email_js[email_js.index("STORE_HOSTS = new Set(["):email_js.index("]);")]
        self.assertEqual(set(re.findall(r'"([^"]+)"', block)), set(ad.STORE_HOSTS))

    def test_routes_validate_each_kind(self):
        good = [RULE, WATCH, DIGEST, {"kind": "digest", "parts": ["Wheels"], "events": ["drop"], "max_price": 40}]
        bad = [
            dict(WATCH, product_key="https://www.zumiez.com/other.html"),  # the two sides disagree
            dict(WATCH, product_url="https://example.com/deck", product_key="https://example.com/deck"),
            dict(WATCH, brand="Heroin"),
            {"kind": "digest", "events": ["restock"]},
            {"kind": "digest", "parts": ["Wheels"], "min_width": 8.5},
            {"kind": "telepathy"},
        ]
        routes = ad.parse_routes({"version": 1, "routes": [{"route_id": "route_a", "rules": good + bad}]})
        self.assertEqual([rule.get("kind", "search") for rule in routes["route_a"]], ["search", "watch", "digest", "digest"])

    def test_a_watch_alerts_on_its_listing_only(self):
        catalog = {
            "Zumiez_Decks": [ITEM, _deck('Heroin Egg 8.75" Skateboard Deck', "https://www.zumiez.com/heroin-egg-8-75-skateboard-deck-1.html", "39.99")],
            "Tactics_Decks": [_deck('Heroin Egg 8.75" Skateboard Deck', "https://www.tactics.com/heroin/egg-skateboard-deck/8-75", "39.99", "Tactics")],
        }
        worker = FakeWorker([{"route_id": "route_a", "rules": [WATCH]}])
        summary = self.run_day(worker, catalog, {}, DAY)
        self.assertEqual(summary["results"], {"sent": 1})
        [[delivery]] = self.deliveries(worker)
        [hit] = delivery["hits"]
        self.assertEqual(hit["item"]["url"], ITEM["url"], "same-named listings elsewhere never match")
        self.assertEqual(hit["item"]["part"], "Decks", "the email shows the real part")
        self.assertEqual(hit["reasons"], ["Maximum price reached"])

    def test_a_default_watch_waits_for_a_real_drop(self):
        watch = {"id": WATCH["id"], "kind": "watch", "product_url": ITEM["url"], "product_key": ITEM["url"], "alert_on_drop": True}
        worker = FakeWorker([{"route_id": "route_a", "rules": [watch]}])
        self.assertEqual(self.run_day(worker, CATALOG, {}, DAY)["deliveries"], 0, "no 'new match' email for a watch")
        self.assertEqual(self.run_day(worker, {"Zumiez_Decks": [dict(ITEM, price_new="53.99")]}, CATALOG, "2026-10-21")["deliveries"], 0,
                         "a $1 move is not meaningful")
        drop = {"Zumiez_Decks": [dict(ITEM, price_new="44.99")]}
        self.assertEqual(self.run_day(worker, drop, CATALOG, "2026-10-22")["results"], {"sent": 1})
        self.assertEqual(self.deliveries(worker)[-1][0]["hits"][0]["reasons"], ["Meaningful price drop"])

    def test_a_watch_follows_its_product_across_shopify_url_churn(self):
        watch = {"id": WATCH["id"], "kind": "watch", "product_url": CCS_COLLECTION,
                 "product_key": "shopify:shop.ccs.com:baker-brand-logo-deck-8-25", "alert_on_drop": True, "max_price": 55}
        worker = FakeWorker([{"route_id": "route_a", "rules": [watch]}])
        day1 = {"CCS_Decks": [_deck("Baker Brand Logo Deck 8.25", CCS_COLLECTION, "54.99", "CCS")]}
        self.assertEqual(self.run_day(worker, day1, {}, DAY)["results"], {"sent": 1})
        # Same product, new URL, same price: no repeat of the price alert.
        day2 = {"CCS_Decks": [_deck("Baker Brand Logo Deck 8.25", CCS_PRODUCT, "54.99", "CCS")]}
        self.assertEqual(self.run_day(worker, day2, day1, "2026-10-21")["deliveries"], 0)
        # A real drop under the new URL is measured against the old URL's price.
        day3 = {"CCS_Decks": [_deck("Baker Brand Logo Deck 8.25", CCS_PRODUCT, "44.99", "CCS")]}
        self.assertEqual(self.run_day(worker, day3, day2, "2026-10-22")["results"], {"sent": 1})
        hit = self.deliveries(worker)[-1][0]["hits"][0]
        self.assertEqual(hit["reasons"], ["Meaningful price drop"])
        self.assertEqual(hit["item"]["url"], CCS_PRODUCT, "the email links today's real listing")

    def test_watch_and_search_state_are_independent(self):
        worker = FakeWorker([{"route_id": "route_a", "rules": [RULE, WATCH]}])
        self.run_day(worker, CATALOG, {}, DAY)
        records = len(self.route_state("route_a")["records"])
        self.assertEqual(records, 2)
        worker.routes = [{"route_id": "route_a", "rules": [RULE]}]
        self.run_day(worker, CATALOG, CATALOG, "2026-10-21")
        self.assertEqual(len(self.route_state("route_a")["records"]), 1, "a removed watch is forgotten")
        worker.routes = [{"route_id": "route_a", "rules": [WATCH]}]
        self.run_day(worker, CATALOG, CATALOG, "2026-10-22")
        self.assertEqual(len(self.route_state("route_a")["records"]), 1)

    def test_digest_picks_real_news_from_clean_scrapes(self):
        previous = {
            "Zumiez_Decks": [ITEM, _deck("Baker Brand Logo 8.25 Skateboard Deck", "https://www.zumiez.com/baker.html", "59.99", width=8.25)]
            + _filler("z", 5),
            "Tactics_Decks": _filler("t", 5),
            "CCS_Decks": [],
        }
        catalog = {
            "Zumiez_Decks": [
                dict(ITEM, price_new="44.99"),  # drop
                _deck("Baker Brand Logo 8.25 Skateboard Deck", "https://www.zumiez.com/baker.html", "58.99", width=8.25),  # $1: not news
                _deck("Real Ripper 8.5 Skateboard Deck", "https://www.zumiez.com/ripper.html", "39.99", width=8.5),  # new
                _deck("Carried Over 8.0 Skateboard Deck", "https://www.zumiez.com/carried.html", "39.99"),  # new but carried
            ] + _filler("z", 5),
            "Tactics_Decks": [_deck("Failed Store 8.0 Skateboard Deck", "https://www.tactics.com/failed/8", "19.99", "Tactics")] + _filler("t", 5),
            # A category with no earlier rows is a first listing, not news.
            "CCS_Decks": [_deck(f"Fresh CCS Deck {n} 8.0", f"https://shop.ccs.com/products/fresh-{n}", "39.99", "CCS") for n in range(3)],
        }
        entries = ad.digest_candidates(catalog, previous, {}, failed_keys=("Tactics_Decks",),
                                       skip_urls=("https://www.zumiez.com/carried.html",))
        self.assertEqual([(e["kind"], e["item"]["url"]) for e in entries],
                         [("drop", ITEM["url"]), ("new", "https://www.zumiez.com/ripper.html")])
        self.assertEqual(entries[0]["price_before"], "54.99")
        self.assertEqual(ad.digest_candidates(catalog, {}, {}), [], "no baseline, no news")

    def test_digest_skips_mass_relistings_and_flags_new_lows(self):
        previous = {"Zumiez_Decks": _filler("z", 10)}
        relisted = _filler("z", 10) + [_deck(f"Relisted {n} 8.0 Skateboard Deck", f"https://www.zumiez.com/re-{n}.html", "39.99") for n in range(30)]
        self.assertEqual(ad.digest_candidates({"Zumiez_Decks": relisted}, previous, {}), [])
        url = "https://www.zumiez.com/filler-z-0.html"
        history = {url: {"prices": {"2026-10-01": 49.99, "2026-10-10": 49.99, "2026-10-19": 49.99}}}
        lowered = [dict(_filler("z", 1)[0], price_new="47.99")] + _filler("z", 10)[1:]
        history[url]["prices"][DAY] = 47.99
        [entry] = ad.digest_candidates({"Zumiez_Decks": lowered}, previous, history)
        self.assertEqual((entry["kind"], entry["item"]["url"], entry["price_before"]), ("low", url, 49.99))

    def test_digest_filters_cap_and_once_a_day(self):
        previous = {"Zumiez_Decks": _filler("z", 60), "Zumiez_Wheels": [{"name": "Spitfire Formula Four 54mm 99a Wheels", "url": "https://www.zumiez.com/sf.html",
                                                                         "price_new": "44.99", "price_old": "44.99", "part": "Wheels", "store": "Zumiez"}]}
        news = [_deck(f"New Deck {n} 8.{n % 10} Skateboard Deck", f"https://www.zumiez.com/new-{n}.html", f"{30 + n // 2}.99", width=8 + (n % 10) / 10)
                for n in range(40)]
        catalog = {"Zumiez_Decks": _filler("z", 60) + news, "Zumiez_Wheels": [dict(previous["Zumiez_Wheels"][0], price_new="34.99")]}
        routes = [
            {"route_id": "route_all", "rules": [DIGEST]},
            {"route_id": "route_wheels", "rules": [dict(DIGEST, parts=["Wheels"])]},
            {"route_id": "route_wide_cheap", "rules": [dict(DIGEST, events=["new"], min_width=8.5, max_price=50)]},
            {"route_id": "route_drops", "rules": [dict(DIGEST, parts=["Decks"], events=["drop"])]},
        ]
        worker = FakeWorker(routes)
        summary = self.run_day(worker, catalog, previous, DAY)
        self.assertEqual(summary["deliveries"], 3, "route_drops has nothing today and gets no email")
        by_route = {d["route_id"]: d for d in self.deliveries(worker)[-1]}
        everything = by_route["route_all"]["digest"]
        self.assertEqual((everything["total"], len(everything["items"])), (41, ad.MAX_DIGEST_ITEMS))
        self.assertEqual(everything["items"][0]["kind"], "drop", "drops lead")
        self.assertEqual(by_route["route_all"]["hits"], [])
        self.assertEqual([i["item"]["part"] for i in by_route["route_wheels"]["digest"]["items"]], ["Wheels"])
        wide = by_route["route_wide_cheap"]["digest"]["items"]
        self.assertTrue(wide and all(float(i["item"]["price_new"]) <= 50 and i["kind"] == "new" for i in wide))
        self.assertEqual(len(wide), 20, "8.5 to 8.9 wide, $50 and under")
        self.assertEqual(by_route["route_all"]["digest"]["event_id"], _hash(["digest", "route_all", DAY]))

        # A second run the same day sends no second digest.
        again = self.run_day(worker, catalog, previous, DAY)
        self.assertEqual(again["results"], {"duplicate": 3})

    def test_watch_hits_and_digest_share_one_email(self):
        worker = FakeWorker([{"route_id": "route_a", "rules": [WATCH, DIGEST]}])
        previous = {"Zumiez_Decks": [dict(ITEM, price_new="64.99")] + _filler("z", 5)}
        catalog = {"Zumiez_Decks": [ITEM] + _filler("z", 5)}
        self.assertEqual(self.run_day(worker, catalog, previous, DAY)["results"], {"sent": 1})
        [[delivery]] = self.deliveries(worker)
        self.assertEqual(len(delivery["hits"]), 1)
        self.assertEqual([i["kind"] for i in delivery["digest"]["items"]], ["drop"])
        ids = sorted(delivery["hits"][0]["event_ids"] + [delivery["digest"]["event_id"]])
        self.assertEqual(delivery["delivery_id"], _hash(ids))


def _node_ok():
    node = shutil.which("node")
    if not node:
        return False
    out = subprocess.run([node, "-e", "require('node:sqlite')"], capture_output=True)
    return out.returncode == 0


@unittest.skipUnless(_node_ok(), "Node 22.5+ with node:sqlite is needed for the end-to-end test")
class EndToEndWithWorkerMockTests(Base):
    """Real Worker (mock mode, local SQLite) + real engine. No network, no email."""

    def setUp(self):
        super().setUp()
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            self.port = probe.getsockname()[1]
        root = Path(__file__).resolve().parent / "worker"
        self.server = subprocess.Popen(["node", "dev/mock-server.js"], cwd=root, env=dict(os.environ, PORT=str(self.port)),
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(self.server.wait, 5)
        self.addCleanup(self.server.kill)
        for _ in range(100):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{self.port}/v1/health", timeout=1)
                break
            except OSError:
                time.sleep(0.05)
        self.env.update(ALERTS_HMAC_SECRET="mock-hmac-secret-not-for-production-000")

    def http(self, method, path, body=None):
        request = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", method=method,
                                         data=json.dumps(body).encode() if body is not None else None,
                                         headers={"Content-Type": "application/json"} if body is not None else {})
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())

    def transport(self, method, url, headers, body):
        # The client requires https; the local mock speaks http on localhost.
        local = url.replace("https://alerts.example.test", f"http://127.0.0.1:{self.port}")
        return ad._urllib_transport(method, local, headers, body)

    def test_subscriber_gets_exactly_one_email(self):
        status, _ = self.http("POST", "/v1/subscribe", {
            "email": "rider@example.com", "consent": True, "consent_version": "2026-10",
            "turnstile_token": "mock-turnstile-pass",
            "rules": [{"brand": "Heroin", "part": "Decks", "min_width": 8.6, "max_price": 60, "note": "Wide Heroin decks"}],
        })
        self.assertEqual(status, 202)
        _, outbox = self.http("GET", "/v1/mock/outbox")
        token = re.search(r"#verify=([\w-]+)", outbox["messages"][0]["text"]).group(1)
        self.assertEqual(self.http("POST", "/v1/verify", {"token": token})[0], 200)
        self.http("DELETE", "/v1/mock/outbox")

        summary = ad.deliver_subscriber_alerts(CATALOG, {}, previous={}, day=DAY, env=self.env, transport=self.transport)
        self.assertEqual(summary["results"], {"sent": 1})
        _, outbox = self.http("GET", "/v1/mock/outbox")
        [mail] = outbox["messages"]
        self.assertEqual(mail["to"], "rider@example.com")
        self.assertEqual(mail["subject"], 'SkateDeals alert: Heroin Egg 8.75" Skateboard Deck')
        self.assertIn("Maximum price reached · Wide Heroin decks", mail["text"])
        self.assertIn("List-Unsubscribe=One-Click", mail["headers"]["List-Unsubscribe-Post"])

        again = ad.deliver_subscriber_alerts(CATALOG, {}, previous={}, day="2026-10-21", env=self.env, transport=self.transport)
        self.assertEqual(again["deliveries"], 0)
        self.assertEqual(len(self.http("GET", "/v1/mock/outbox")[1]["messages"]), 1, "no second email")

    def test_digest_and_watch_subscriber_gets_one_combined_email(self):
        status, _ = self.http("POST", "/v1/subscribe", {
            "email": "rider@example.com", "consent": True, "consent_version": "2026-10",
            "turnstile_token": "mock-turnstile-pass",
            "rules": [{"kind": "digest"}, {"kind": "watch", "product_url": ITEM["url"], "max_price": 60, "label": ITEM["name"]}],
        })
        self.assertEqual(status, 202)
        _, outbox = self.http("GET", "/v1/mock/outbox")
        token = re.search(r"#verify=([\w-]+)", outbox["messages"][0]["text"]).group(1)
        self.assertEqual(self.http("POST", "/v1/verify", {"token": token})[0], 200)
        self.http("DELETE", "/v1/mock/outbox")

        previous = {"Zumiez_Decks": [dict(ITEM, price_new="64.99")]}
        summary = ad.deliver_subscriber_alerts(CATALOG, {}, previous=previous, day=DAY, env=self.env, transport=self.transport)
        self.assertEqual(summary["results"], {"sent": 1})
        [mail] = self.http("GET", "/v1/mock/outbox")[1]["messages"]
        self.assertEqual(mail["subject"], "SkateDeals: 1 alert and 1 deal today")
        self.assertIn("Maximum price reached", mail["text"])
        self.assertIn("Today's deals", mail["text"])
        self.assertIn("Price drop", mail["text"])

        rerun = ad.deliver_subscriber_alerts(CATALOG, {}, previous=previous, day=DAY, env=self.env, transport=self.transport)
        self.assertEqual(rerun["results"], {"duplicate": 1})
        self.assertEqual(len(self.http("GET", "/v1/mock/outbox")[1]["messages"]), 1, "no second email the same day")


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    unittest.main()
