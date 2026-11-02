"""PR previews (issue #113): the preview build is inert, the artifact check
refuses anything unexpected, the comment escapes untrusted text, and the
workflows keep PR code away from secrets and production."""

import json
import os
import tempfile
import unittest
from pathlib import Path

import yaml

from ci import build_preview, check_artifact, pr_comment

ROOT = Path(__file__).resolve().parent
WORKFLOWS = ROOT / ".github" / "workflows"
PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 32


def _workflow(name):
    data = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
    data["on"] = data.pop(True, data.get("on"))
    return data


class PreviewBuildTests(unittest.TestCase):
    def test_mark_preview_removes_production_hooks_and_labels_the_page(self):
        html = ("<html><head><title>SkateDeals | 2026-11-01</title></head><body class=\"x\"><main></main>"
                "<!-- Cloudflare Web Analytics --><script type='module' src='https://static.cloudflareinsights.com/beacon.min.js' "
                "data-cf-beacon='{\"token\": \"t\"}'></script><!-- End Cloudflare Web Analytics --></body></html>")
        out = build_preview.mark_preview(html, "PR #7 <abc>")
        self.assertNotIn("cloudflareinsights", out)
        self.assertIn("<title>PREVIEW · SkateDeals", out)
        self.assertIn('<meta name="robots" content="noindex,nofollow">', out)
        self.assertIn('<body class="x"><div id="previewBanner"', out)
        self.assertIn("PR #7 &lt;abc&gt;", out, "the label is escaped")

    def test_the_built_preview_has_no_live_alerts_or_analytics(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as data_root:
            files = build_preview.build(directory, "PR #1 test", data_root=data_root)
            self.assertEqual(files, ["_headers", "history.json", "index.html", "navigation", "sale_items_chart.html"])
            home = (Path(directory) / "index.html").read_text(encoding="utf-8")
            self.assertIn("ShredDeals", home)
            self.assertNotIn("http-equiv=\"refresh\"", home)
            self.assertIn('id="previewBanner"', home)
            self.assertTrue((Path(directory) / "navigation/navigation.js").is_file())
            html = (Path(directory) / "sale_items_chart.html").read_text(encoding="utf-8")
            self.assertNotIn("window.SKATEDEALS_ALERTS = ", html, "no alerts config: page.js keeps alerts off")
            self.assertNotIn("skatedeals-alerts.pchoward.workers.dev", html)
            self.assertNotIn("0x4AAAAAAFjwOIPFNNUHi29X", html, "no Turnstile site key")
            self.assertNotIn("cloudflareinsights.com/beacon", html)
            self.assertEqual(html.count('id="previewBanner"'), 1)
            self.assertIn("X-Robots-Tag: noindex", (Path(directory) / "_headers").read_text())
        # Building a preview never touches the published page.
        self.assertIn("window.SKATEDEALS_ALERTS = ", (ROOT / "sale_items_chart.html").read_text(encoding="utf-8"))


class ArtifactCheckTests(unittest.TestCase):
    def make(self, root, number=12, sha="a" * 40, shots=None, site=None):
        root = Path(root)
        (root / "shots").mkdir(parents=True)
        (root / "site").mkdir()
        (root / "pr.json").write_text(json.dumps({"number": number, "head_sha": sha}))
        for name, body in (shots or {"desktop-home.png": PNG, "summary.json": b"{}"}).items():
            (root / "shots" / name).write_bytes(body)
        for name in site or sorted(check_artifact.SITE_FILES):
            target = root / "site" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("x")
        return root

    def test_a_good_artifact_names_its_pr(self):
        with tempfile.TemporaryDirectory() as directory:
            self.make(directory)
            self.assertEqual(check_artifact.check(directory, "a" * 40, {12}), 12)

    def test_refusals(self):
        cases = {
            "another commit": dict(sha="b" * 40),
            "a PR that is not open with that head": dict(number=99),
            "a fake PNG": dict(shots={"desktop-home.png": b"<svg onload=x>"}),
            "an unexpected screenshot name": dict(shots={"evil.png": PNG}),
            "an extra site file": dict(site=("index.html", "evil.js")),
            "an extra navigation file": dict(site=("navigation/evil.js",)),
        }
        for label, kwargs in cases.items():
            with self.subTest(label), tempfile.TemporaryDirectory() as directory:
                try:
                    self.make(directory, **kwargs)
                except (OSError, ValueError):
                    continue  # the bad name cannot even be written; nothing to publish
                with self.assertRaises(check_artifact.Refused):
                    check_artifact.check(directory, "a" * 40, {12})

    def test_symlinks_are_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.make(directory)
            os.symlink("/etc/hostname", root / "site" / "history.json.tmp")
            os.replace(root / "site" / "history.json.tmp", root / "site" / "history.json")
            with self.assertRaises(check_artifact.Refused):
                check_artifact.check(directory, "a" * 40, {12})

    def test_navigation_symlink_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.make(directory)
            asset = root / "site/navigation/navigation.js"
            asset.unlink()
            asset.symlink_to("/etc/hostname")
            with self.assertRaises(check_artifact.Refused):
                check_artifact.check(directory, "a" * 40, {12})


class CommentTests(unittest.TestCase):
    SUMMARY = {
        "checks": [
            {"view": "desktop", "name": "Search", "status": "pass", "detail": "ok"},
            {"view": "mobile", "name": "Search", "status": "fail", "detail": "nothing found"},
            {"view": "mobile", "name": "Sport tabs", "status": "skip", "detail": "none"},
        ],
        "screenshots": ["desktop-home.png", "mobile-home.png", "mobile-shell.png"],
    }

    def test_a_readable_comment_with_screenshots(self):
        body = pr_comment.render(self.SUMMARY, "abcdef1234", "https://run", "success", images_base="https://img/pr-1/abcdef1")
        self.assertTrue(body.startswith(pr_comment.MARKER))
        self.assertIn("**Tests:** ✅ passed", body)
        self.assertIn("❌ 1 browser check(s) failed", body)
        self.assertIn("| Search | ✅ | ❌ |", body)
        self.assertIn("**mobile · Search**: nothing found", body)
        self.assertIn('<img src="https://img/pr-1/abcdef1/mobile-home.png" width="160"', body)
        self.assertIn("mobile-shell.png", body, "the homepage screenshot is shown")
        self.assertIn("not set up", body, "says when there is no live preview")
        with_link = pr_comment.render(self.SUMMARY, "abc", "https://run", "success", preview_url="https://pr-1.p.pages.dev/x")
        self.assertIn("[Open the preview](https://pr-1.p.pages.dev/x)", with_link)
        self.assertIn("pr-preview** artifact", with_link, "no image base: points to the artifact")

    def test_untrusted_text_is_escaped(self):
        evil = {"checks": [{"view": "desktop", "name": "<img src=x onerror=alert(1)>", "status": "<b>",
                            "detail": "[click](https://evil) | `x`"}],
                "screenshots": ["../../etc/passwd", "desktop-home.png"]}
        body = pr_comment.render(evil, "abc`", "https://run", "<script>", images_base="https://img")
        self.assertNotIn("<img src=x", body)
        self.assertNotIn("<script>", body)
        self.assertNotIn("[click](", body)
        self.assertNotIn("passwd", body)
        self.assertIn("| ❌ |", body, "an unknown status counts as a failure")

    def test_no_summary_still_reports(self):
        body = pr_comment.render({}, "abc", "https://run", "failure")
        self.assertIn("Browser checks ran", body)
        self.assertIn("❌ failed", body)


class WorkflowSafetyTests(unittest.TestCase):
    def test_the_pr_job_has_no_secrets_and_cannot_write(self):
        checks = _workflow("pr-checks.yml")
        text = (WORKFLOWS / "pr-checks.yml").read_text(encoding="utf-8")
        self.assertNotIn("pull_request_target", text)
        self.assertNotIn("secrets.", text)
        self.assertEqual(checks["permissions"], {"contents": "read"})
        preview = checks["jobs"]["preview"]
        self.assertEqual(preview["permissions"], {"contents": "read"})
        self.assertIn("vars.PR_PREVIEWS != 'off'", preview["if"])
        self.assertIs(preview["steps"][0]["with"]["persist-credentials"], False)
        # The banner label keeps the PR number (an unquoted " #" was a YAML comment).
        label = next(step for step in preview["steps"] if step["name"] == "Build the preview site")["env"]["LABEL"]
        self.assertTrue(label.startswith("PR #${{ github.event.pull_request.number }}"), label)

    def test_the_publisher_runs_main_code_on_data_only(self):
        publish = _workflow("pr-preview-publish.yml")
        text = (WORKFLOWS / "pr-preview-publish.yml").read_text(encoding="utf-8")
        self.assertEqual(list(publish["on"]), ["workflow_run"])
        self.assertEqual(publish["permissions"], {})
        job = publish["jobs"]["publish"]
        self.assertEqual(job["permissions"], {"actions": "read", "contents": "write", "pull-requests": "write"})
        self.assertIn("vars.PR_PREVIEWS != 'off'", job["if"])
        checkout = job["steps"][0]
        self.assertEqual(checkout["with"]["ref"], "${{ github.event.repository.default_branch }}")
        self.assertNotIn("head_sha }}\n", checkout["with"].get("ref", ""))
        # The artifact is data: nothing in it is executed or sourced.
        self.assertNotRegex(text, r"(^|[\s;&|])(bash|sh|python3?|node|source|\.)\s+(\./)?incoming")
        self.assertNotRegex(text, r"(^|\s)npm\s")
        self.assertNotIn("pull_request_target", text)
        self.assertIn("ci/check_artifact.py incoming", text)
        # A live preview needs the owner's opt-in, and is never production.
        deploy = next(step for step in job["steps"] if step.get("id") == "cloudflare")
        self.assertIn("vars.CF_PAGES_PROJECT != ''", deploy["if"])
        self.assertIn("same_repo == 'true'", deploy["if"])
        self.assertIn('--branch "pr-$NUMBER"', deploy["run"])
        self.assertNotIn("--branch main", text)

    def test_nothing_new_touches_production(self):
        for name in ("pr-checks.yml", "pr-preview-publish.yml"):
            text = (WORKFLOWS / name).read_text(encoding="utf-8")
            for forbidden in ("scraper.py", "SMTP", "ALERTS_HMAC", "deploy.sh", "git push origin main", "gh pr merge", "/merge"):
                self.assertNotIn(forbidden, text, f"{name}: {forbidden}")
        script = (ROOT / "ci" / "publish_screenshots.sh").read_text(encoding="utf-8")
        # Comment images link through the branch: a commit link breaks once
        # the next run replaces that commit.
        self.assertIn("raw.githubusercontent.com/${REPO}/${branch}/pr-${number}/${short}", script)
        self.assertIn('branch="ci-previews"', script)
        self.assertIn('"snapshot:refs/heads/$branch"', script)
        self.assertNotIn("refs/heads/main", script)


if __name__ == "__main__":
    unittest.main()
