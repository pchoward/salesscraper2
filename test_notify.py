"""Email digest checks. No network and no scrape.

Run: python test_notify.py
"""

import datetime
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from filters import is_meaningful_drop
from notify import (
    DEFAULT_REPORT_URL,
    build_sample_digest,
    iter_sections,
    load_smtp_config,
    main,
    render_html,
    render_plain,
    send_digest,
    should_send,
    subject_line,
)
from report import Digest, build_digest, build_report_html, compare_catalogs

WHEN = datetime.date(2026, 9, 28)


def _deck(**overrides):
    item = {
        "name": "Baker Team Deck 8.25",
        "url": "https://example.com/baker",
        "price_new": "40.00",
        "price_old": "70.00",
        "part": "Decks",
        "store": "CCS",
    }
    item.update(overrides)
    return item


def _wheel(**overrides):
    item = {
        "name": "Spitfire Formula Four 53mm Wheels",
        "url": "https://example.com/spitfire",
        "price_new": "32.00",
        "price_old": "50.00",
        "part": "Wheels",
        "store": "Tactics",
    }
    item.update(overrides)
    return item


def _truck(**overrides):
    item = {
        "name": "Independent Stage 11 149 Truck",
        "url": "https://example.com/indy",
        "price_new": "20.00",
        "price_old": "30.00",
        "part": "Trucks",
        "store": "Zumiez",
    }
    item.update(overrides)
    return item


def _bearing(**overrides):
    item = {
        "name": "Bones Swiss Skateboard Bearings",
        "url": "https://example.com/bones",
        "price_new": "24.00",
        "price_old": "40.00",
        "part": "Bearings",
        "store": "Zumiez",
    }
    item.update(overrides)
    return item


def _drop(item, old="30.00", new="24.00", delta=6.0, percent=20.0):
    return {
        "type": "price_drop",
        "url": item.get("url"),
        "name": item.get("name"),
        "old": old,
        "new": new,
        "delta": delta,
        "percent_vs_prior": percent,
        "item": item,
    }


def _full_env(**overrides):
    env = {
        "SMTP_HOST": "smtp.example.com",
        "SMTP_PORT": "587",
        "SMTP_USER": "user@example.com",
        "SMTP_PASSWORD": "super-secret-password",
        "EMAIL_TO": "one@example.com, two@example.com",
        "SMTP_SECURITY": "starttls",
    }
    env.update(overrides)
    return env


def _sample_digest():
    bearing = _bearing()
    return Digest(
        new_items=[_deck(), _wheel(), _truck()],
        drops=[_drop(bearing)],
    )


class SendGateTests(unittest.TestCase):
    def test_empty_digest_does_not_send(self):
        digest = Digest()
        self.assertFalse(should_send(digest))
        with patch("notify.smtplib.SMTP") as smtp, patch("notify.smtplib.SMTP_SSL") as smtp_ssl:
            with self.assertLogs("notify", level="INFO") as logs:
                self.assertFalse(send_digest(digest, env=_full_env(), when=WHEN))
        smtp.assert_not_called()
        smtp_ssl.assert_not_called()
        self.assertTrue(any("no new items or price drops" in line for line in logs.output))

    def test_compare_with_no_changes_does_not_send(self):
        item = _wheel()
        catalog = {"Tactics_Wheels": [item]}
        digest = build_digest(compare_catalogs(catalog, catalog))
        self.assertFalse(should_send(digest))
        with patch("notify.smtplib.SMTP") as smtp:
            self.assertFalse(send_digest(digest, env=_full_env(), when=WHEN))
        smtp.assert_not_called()

    def test_removals_only_does_not_send(self):
        previous = {"Zumiez_Wheels": [_wheel(store="Zumiez")]}
        current = {"Zumiez_Wheels": []}
        digest = build_digest(compare_catalogs(previous, current))
        self.assertTrue(digest.removed)
        self.assertFalse(digest.new_items)
        self.assertFalse(digest.drops)
        self.assertFalse(should_send(digest))
        with patch("notify.smtplib.SMTP") as smtp:
            with self.assertLogs("notify", level="INFO") as logs:
                self.assertFalse(send_digest(digest, env=_full_env(), when=WHEN))
        smtp.assert_not_called()
        self.assertTrue(any("no new items or price drops" in line for line in logs.output))
        joined = "\n".join(logs.output)
        self.assertNotIn("super-secret-password", joined)

    def test_removed_rows_alone_on_a_digest_do_not_send(self):
        digest = Digest(removed=[("Zumiez_Decks", _deck())])
        self.assertFalse(should_send(digest))
        with patch("notify.smtplib.SMTP") as smtp:
            self.assertFalse(send_digest(digest, env=_full_env(), when=WHEN))
        smtp.assert_not_called()


class SubjectAndRenderTests(unittest.TestCase):
    def test_subject_counts(self):
        digest = Digest(new_items=[_deck(), _wheel(), _truck()], drops=[_drop(_bearing()), _drop(_wheel())])
        self.assertEqual(subject_line(digest, WHEN), "Skate deals: 3 new, 2 price drops (Sep 28)")

    def test_subject_singular_price_drop(self):
        digest = Digest(new_items=[_deck()], drops=[_drop(_bearing())])
        self.assertEqual(subject_line(digest, WHEN), "Skate deals: 1 new, 1 price drop (Sep 28)")

    def test_rendering_groups_parts_and_shows_prices(self):
        digest = _sample_digest()
        html = render_html(digest, DEFAULT_REPORT_URL, WHEN)
        plain = render_plain(digest, DEFAULT_REPORT_URL, WHEN)
        parts = [part for part, _new, _drops in iter_sections(digest)]
        self.assertEqual(parts, ["Decks", "Wheels", "Trucks", "Bearings"])
        for earlier, later in zip(parts, parts[1:]):
            self.assertLess(html.index(f'data-part="{earlier}"'), html.index(f'data-part="{later}"'))
            self.assertLess(plain.index(earlier.upper()), plain.index(later.upper()))

        self.assertIn('href="https://example.com/baker"', html)
        self.assertIn("Baker Team Deck 8.25", html)
        self.assertIn("CCS", html)
        self.assertIn("$40.00", html)
        self.assertIn("$70.00", html)
        self.assertIn("43% off", html)
        self.assertIn('href="https://example.com/bones"', html)
        self.assertIn("Prior sale $30.00", html)
        self.assertIn("−$6.00", html)
        self.assertIn("−20.0% vs prior sale", html)
        self.assertIn("40% off", html)
        self.assertIn(DEFAULT_REPORT_URL, html)
        self.assertIn("September 28, 2026", html)
        self.assertNotIn("Sample preview", html)

        self.assertIn("https://example.com/baker", plain)
        self.assertIn("Sale $40.00 · Original $70.00 · 43% off", plain)
        self.assertIn("Sale $24.00 · Prior sale $30.00 · −$6.00 (−20.0% vs prior sale)", plain)
        self.assertIn("Original $40.00 · 40% off", plain)
        self.assertIn(DEFAULT_REPORT_URL, plain)

    def test_report_html_reuses_the_same_digest(self):
        previous = {
            "Zumiez_Bearings": [
                _bearing(price_new="30.00"),
            ]
        }
        current = {
            "Zumiez_Bearings": [_bearing()],
            "CCS_Decks": [_deck()],
        }
        changes = compare_catalogs(previous, current)
        digest = build_digest(changes)
        self.assertEqual(len(digest.new_items), 1)
        self.assertEqual(digest.new_items[0]["name"], "Baker Team Deck 8.25")
        self.assertEqual(len(digest.drops), 1)
        self.assertEqual(digest.drops[0]["delta"], 6.0)
        html = build_report_html(
            current,
            changes,
            generated_at="2026-09-28 08:00:00",
            digest=digest,
        )
        self.assertIn("Baker Team Deck 8.25", html)
        self.assertIn("−$6.00", html)


class ConfigAndDeliveryTests(unittest.TestCase):
    def test_missing_config_skips_in_one_line(self):
        env = {"SMTP_PASSWORD": "super-secret-password", "EMAIL_TO": ""}
        config = load_smtp_config(env)
        self.assertIn("SMTP_HOST", config.missing)
        self.assertIn("SMTP_USER", config.missing)
        self.assertIn("EMAIL_TO", config.missing)
        with patch("notify.smtplib.SMTP") as smtp:
            with self.assertLogs("notify", level="WARNING") as logs:
                self.assertFalse(send_digest(_sample_digest(), env=env, when=WHEN))
        smtp.assert_not_called()
        skipped = [line for line in logs.output if "Email skipped: missing" in line]
        self.assertEqual(len(skipped), 1)
        self.assertNotIn("super-secret-password", skipped[0])

    def test_invalid_port_skips(self):
        env = _full_env(SMTP_PORT="not-a-port")
        with patch("notify.smtplib.SMTP") as smtp:
            with self.assertLogs("notify", level="WARNING") as logs:
                self.assertFalse(send_digest(_sample_digest(), env=env, when=WHEN))
        smtp.assert_not_called()
        self.assertIn("SMTP_PORT", "\n".join(logs.output))

    def test_dry_run_writes_preview_without_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "email_preview.html")
            with patch("notify.smtplib.SMTP") as smtp, patch("notify.smtplib.SMTP_SSL") as smtp_ssl:
                wrote = send_digest(
                    _sample_digest(),
                    env={"EMAIL_DRY_RUN": "1", "REPORT_URL": "https://example.com/deals.html"},
                    preview_path=path,
                    when=WHEN,
                )
            self.assertTrue(wrote)
            smtp.assert_not_called()
            smtp_ssl.assert_not_called()
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
        self.assertIn("Subject: Skate deals: 3 new, 1 price drop (Sep 28)", text)
        self.assertIn("https://example.com/deals.html", text)
        self.assertNotIn(DEFAULT_REPORT_URL, text)
        self.assertIn("Baker Team Deck 8.25", text)

    def test_dry_run_flag_skips_smtp_even_when_configured(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "email_preview.html")
            with patch("notify.smtplib.SMTP") as smtp:
                self.assertTrue(
                    send_digest(
                        _sample_digest(),
                        env=_full_env(),
                        dry_run=True,
                        preview_path=path,
                        when=WHEN,
                    )
                )
            smtp.assert_not_called()
            self.assertTrue(os.path.isfile(path))

    def test_starttls_send_uses_stdlib_and_default_from(self):
        env = _full_env()
        env.pop("EMAIL_FROM", None)
        with patch("notify.smtplib.SMTP") as smtp_cls:
            server = smtp_cls.return_value.__enter__.return_value
            self.assertTrue(send_digest(_sample_digest(), env=env, when=WHEN))
        smtp_cls.assert_called_once()
        args, kwargs = smtp_cls.call_args
        self.assertEqual(args[:2], ("smtp.example.com", 587))
        self.assertEqual(kwargs.get("timeout"), 30)
        server.starttls.assert_called_once()
        server.login.assert_called_once_with("user@example.com", "super-secret-password")
        message = server.send_message.call_args[0][0]
        self.assertEqual(message["Subject"], "Skate deals: 3 new, 1 price drop (Sep 28)")
        self.assertEqual(message["From"], "user@example.com")
        self.assertEqual(message["To"], "one@example.com, two@example.com")
        self.assertEqual(message.get_content_type(), "multipart/alternative")
        payloads = message.get_payload()
        self.assertEqual(payloads[0].get_content_type(), "text/plain")
        self.assertEqual(payloads[1].get_content_type(), "text/html")
        self.assertIn("Baker Team Deck 8.25", payloads[1].get_content())

    def test_ssl_uses_smtp_ssl(self):
        env = _full_env(SMTP_PORT="465", SMTP_SECURITY="ssl", EMAIL_FROM="deals@example.com")
        with patch("notify.smtplib.SMTP_SSL") as smtp_ssl, patch("notify.smtplib.SMTP") as smtp:
            server = smtp_ssl.return_value.__enter__.return_value
            self.assertTrue(send_digest(Digest(new_items=[_deck()]), env=env, when=WHEN))
        smtp.assert_not_called()
        smtp_ssl.assert_called_once()
        self.assertEqual(smtp_ssl.call_args[0][:2], ("smtp.example.com", 465))
        server.starttls.assert_not_called()
        message = server.send_message.call_args[0][0]
        self.assertEqual(message["From"], "deals@example.com")
        self.assertEqual(message["Subject"], "Skate deals: 1 new, 0 price drops (Sep 28)")

    def test_smtp_error_is_logged_and_does_not_raise(self):
        with patch("notify.smtplib.SMTP") as smtp_cls:
            smtp_cls.return_value.__enter__.side_effect = OSError("connection refused")
            with self.assertLogs("notify", level="ERROR") as logs:
                result = send_digest(_sample_digest(), env=_full_env(), when=WHEN)
        self.assertFalse(result)
        self.assertTrue(any("Email failed" in line for line in logs.output))
        self.assertNotIn("super-secret-password", "\n".join(logs.output))


class SamplePreviewTests(unittest.TestCase):
    def test_sample_from_catalog_is_labeled_and_meaningful(self):
        with open("previous_data.json", "r", encoding="utf-8") as handle:
            catalog = json.load(handle)
        digest = build_sample_digest(catalog)
        self.assertTrue(should_send(digest))
        self.assertTrue(digest.new_items)
        self.assertTrue(digest.drops)
        self.assertFalse(digest.removed)
        for item in digest.new_items:
            self.assertTrue(item["name"].startswith("[SAMPLE] "))
            self.assertNotIn("Clearance", item["name"])
        for change in digest.drops:
            self.assertTrue(change["name"].startswith("[SAMPLE] "))
            self.assertNotIn("Clearance", change["name"])
            self.assertTrue(is_meaningful_drop(change["old"], change["new"]))
        parts = {part for part, _new, _drops in iter_sections(digest)}
        self.assertIn("Decks", parts)
        self.assertIn("Wheels", parts)
        self.assertIn("Trucks", parts)

    def test_sample_cli_writes_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "email_preview.html")
            with patch("notify.smtplib.SMTP") as smtp:
                code = main(
                    [
                        "--sample",
                        "--dry-run",
                        "--catalog",
                        "previous_data.json",
                        "--preview-path",
                        path,
                    ]
                )
            smtp.assert_not_called()
            self.assertEqual(code, 0)
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
        self.assertIn("Sample preview, not a live alert", text)
        self.assertIn("[SAMPLE]", text)
        self.assertIn(DEFAULT_REPORT_URL, text)
        self.assertIn("Subject: Skate deals:", text)


class StoreWarningTests(unittest.TestCase):
    def _warning(self, kind="empty"):
        return {
            "key": "Zumiez_Decks",
            "store": "Zumiez",
            "part": "Decks",
            "kind": kind,
            "dates": ["2026-09-29", "2026-09-30"],
            "last_positive_date": "2026-09-28",
            "last_positive_count": 12,
        }

    def test_warning_alone_sends_mail(self):
        digest = Digest(warnings=[self._warning()])
        self.assertTrue(should_send(digest))
        self.assertEqual(subject_line(digest, WHEN), "Skate deals: 1 store warning (Sep 28)")
        with patch("notify.smtplib.SMTP") as smtp:
            server = smtp.return_value.__enter__.return_value
            self.assertTrue(send_digest(digest, env=_full_env(), when=WHEN))
        smtp.assert_called_once()
        message = server.send_message.call_args[0][0]
        self.assertEqual(message["Subject"], "Skate deals: 1 store warning (Sep 28)")
        html = message.get_payload()[1].get_content()
        plain = message.get_payload()[0].get_content()
        self.assertIn("Store check failed", html)
        self.assertIn("came back with no items two runs in a row", html)
        self.assertIn("STORE CHECK FAILED", plain)
        self.assertIn("Zumiez Decks", plain)

    def test_warning_with_a_deal_is_included_in_the_subject(self):
        digest = Digest(new_items=[_deck()], warnings=[self._warning()])
        self.assertEqual(
            subject_line(digest, WHEN),
            "Skate deals: 1 new, 0 price drops, 1 store warning (Sep 28)",
        )

    def test_all_time_low_and_cross_store_render_when_present(self):
        item = _deck()
        item["at_all_time_low"] = True
        digest = Digest(new_items=[item], all_time_lows=[item])
        digest.cross_store = [
            {
                "label": "Baker Figgy Divine Evil 8.25\"",
                "part": "Decks",
                "cheapest_price": 50.0,
                "offers": [
                    {"store": "SkateWarehouse", "price": 50.0, "url": "https://example.com/cheap", "name": "Baker Figgy"},
                    {"store": "Zumiez", "price": 64.99, "url": "https://example.com/pricey", "name": "Baker Figgy"},
                ],
            },
            {
                "label": "Almost the same",
                "part": "Decks",
                "cheapest_price": 40.0,
                "offers": [
                    {"store": "CCS", "price": 40.0, "url": "https://example.com/a", "name": "Close"},
                    {"store": "Tactics", "price": 40.5, "url": "https://example.com/b", "name": "Close"},
                ],
            },
        ]
        html = render_html(digest, DEFAULT_REPORT_URL, WHEN)
        plain = render_plain(digest, DEFAULT_REPORT_URL, WHEN)
        self.assertIn("ALL-TIME LOW", html)
        self.assertIn("1 tracked deal is at an all-time low", html)
        self.assertIn('data-section="across-stores"', html)
        self.assertIn("SkateWarehouse", html)
        self.assertIn("$50.00", html)
        self.assertNotIn("Almost the same", html)
        self.assertIn("all-time low", plain)
        self.assertIn("ACROSS STORES", plain)
        self.assertIn("(lowest)", plain)
        self.assertNotIn("Almost the same", plain)


class WiringTests(unittest.TestCase):
    def test_workflow_passes_secrets_and_keeps_cron(self):
        with open(".github/workflows/scrape.yml", encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("cron: '0 8 * * *'", text)
        for name in (
            "SMTP_HOST",
            "SMTP_PORT",
            "SMTP_USER",
            "SMTP_PASSWORD",
            "EMAIL_FROM",
            "EMAIL_TO",
        ):
            self.assertIn(f"{name}: ${{{{ secrets.{name} }}}}", text)
        self.assertNotIn("you@gmail.com", text)
        self.assertNotIn("smtp.gmail.com", text)

    def test_scraper_sends_after_digest(self):
        with open("scraper.py", encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("digest = build_digest(changes, failed_keys)", text)
        self.assertLess(text.index("digest = build_digest"), text.index("send_digest(digest"))
        self.assertIn('dry_run = True if "--email-dry-run" in sys.argv[1:] else None', text)


if __name__ == "__main__":
    unittest.main()
