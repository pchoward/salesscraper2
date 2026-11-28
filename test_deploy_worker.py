"""The "Alerts - Deploy Worker" workflow and its config writer (owner,
2026-11-28: deploy from GitHub Actions, not a codespace)."""

import importlib.util
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parent
spec = importlib.util.spec_from_file_location("write_wrangler_toml", ROOT / "worker/write_wrangler_toml.py")
writer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(writer)

ENV = {"ALERTS_API_URL": "https://skatedeals-alerts.example.workers.dev/", "WORKER_D1_ID": "0c3db810-aaaa-bbbb"}


class ConfigTests(unittest.TestCase):
    def test_defaults_and_overrides(self):
        text = writer.render(ENV)
        self.assertIn('PUBLIC_API_URL = "https://skatedeals-alerts.example.workers.dev"', text)
        self.assertIn('database_id = "0c3db810-aaaa-bbbb"', text)
        self.assertIn('NEWSLETTER_INBOX = "deals@shreddeals.com"', text)
        self.assertIn('MODE = "staging"', text)
        text = writer.render({**ENV, "WORKER_MODE": "production", "WORKER_EMAIL_FROM": 'A "B" <a@b.c>'})
        self.assertIn('MODE = "production"', text)
        self.assertIn('EMAIL_FROM = "A \\"B\\" <a@b.c>"', text)

    def test_every_example_var_is_written(self):
        example = (ROOT / "worker/wrangler.toml.example").read_text(encoding="utf-8")
        section = example.split("[vars]", 1)[1].split("[[", 1)[0]
        names = {line.split("=", 1)[0].strip() for line in section.splitlines() if "=" in line and not line.lstrip().startswith("#")}
        text = writer.render(ENV)
        for name in names:
            self.assertIn(f"\n{name} = ", text, name)

    def test_bad_settings_refuse(self):
        for env in ({}, {**ENV, "ALERTS_API_URL": "http://x"}, {**ENV, "WORKER_D1_ID": "x; rm"},
                    {**ENV, "WORKER_MODE": "mock"}, {**ENV, "WORKER_EMAIL_FROM": "a\nb"}):
            with self.assertRaises(writer.ConfigError):
                writer.render(env)

    def test_no_secret_names_in_config(self):
        text = writer.render(ENV)
        for secret in ("HMAC_SECRET", "TOKEN_PEPPER", "RESEND_API_KEY", "TURNSTILE_SECRET"):
            self.assertNotIn(secret, text)


class WorkflowTests(unittest.TestCase):
    def test_manual_main_only_and_dry_run_first(self):
        text = (ROOT / ".github/workflows/deploy-worker.yml").read_text(encoding="utf-8")
        flow = yaml.safe_load(text)
        triggers = flow[True]  # YAML reads "on" as True
        self.assertEqual(list(triggers), ["workflow_dispatch"])
        self.assertIs(triggers["workflow_dispatch"]["inputs"]["dry_run"]["default"], True)
        steps = flow["jobs"]["deploy"]["steps"]
        self.assertIn("refs/heads/main", steps[0]["if"])
        with_token = [step["name"] for step in steps if "CLOUDFLARE_API_TOKEN" in str(step.get("env", {}))]
        self.assertEqual(with_token, ["Apply D1 migrations", "Deploy"])
        self.assertTrue(all("!inputs.dry_run" in step["if"] for step in steps if step["name"] in with_token))


if __name__ == "__main__":
    unittest.main()
