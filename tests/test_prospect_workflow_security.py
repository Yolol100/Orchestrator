import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "prospect-discovery.yml"
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


class ProspectWorkflowSecurityTests(unittest.TestCase):
    def test_workflow_is_read_only_at_github_permission_layer(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("\npermissions:\n  contents: read\n", text)
        self.assertNotIn("write-all", text)

    def test_remote_actions_are_sha_pinned_if_any_are_used(self):
        for raw in WORKFLOW.read_text(encoding="utf-8").splitlines():
            stripped = raw.strip()
            if not stripped.startswith("uses:"):
                continue
            target = stripped.split("uses:", 1)[1].strip().split()[0]
            ref = target.rsplit("@", 1)[1]
            self.assertRegex(ref, FULL_SHA)

    def test_legacy_discovery_route_is_manual_only_disabled_and_secret_free(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("schedule:", text)
        self.assertIn("LEGACY_DOMAIN_ROUTE=disabled", text)
        self.assertIn("Yolol100/Leadscanner", text)
        for forbidden in (
            "GOOGLE_SERVICE_ACCOUNT_JSON",
            "OUTREACH_MAIL_PASSWORD",
            "OUTREACH_MAILBOXES_JSON",
            "REOON_API_KEY",
            "scripts/prospect_",
            "secrets.",
        ):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
