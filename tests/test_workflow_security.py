import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
LEGACY_LEADS_WORKFLOWS = (
    "outreach-smtp.yml",
    "outreach-drafts.yml",
    "prospect-discovery.yml",
)


class WorkflowSecurityTests(unittest.TestCase):
    def test_all_remote_actions_are_pinned_to_full_commit_sha(self):
        for path in sorted(WORKFLOWS.glob("*.yml")):
            text = path.read_text(encoding="utf-8")
            for raw in text.splitlines():
                stripped = raw.strip()
                if not stripped.startswith("uses:"):
                    continue
                target = stripped.split("uses:", 1)[1].strip().split()[0]
                if target.startswith("./"):
                    continue
                self.assertIn("@", target, f"{path.name}: unpinned action {target}")
                ref = target.rsplit("@", 1)[1]
                self.assertRegex(ref, FULL_SHA, f"{path.name}: action is not pinned to a full SHA: {target}")

    def test_all_workflows_declare_explicit_permissions(self):
        for path in sorted(WORKFLOWS.glob("*.yml")):
            text = path.read_text(encoding="utf-8")
            self.assertIn("\npermissions:\n", text, f"{path.name}: missing explicit permissions")
            self.assertNotIn("write-all", text, f"{path.name}: write-all is forbidden")

    def test_legacy_leads_domain_routes_are_manual_only_disabled_stubs(self):
        for filename in LEGACY_LEADS_WORKFLOWS:
            text = (WORKFLOWS / filename).read_text(encoding="utf-8")
            self.assertIn("workflow_dispatch:", text, filename)
            self.assertNotIn("schedule:", text, filename)
            self.assertIn("LEGACY_DOMAIN_ROUTE=disabled", text, filename)
            self.assertIn("Yolol100/Leadscanner", text, filename)
            self.assertIn("contents: read", text, filename)

    def test_disabled_legacy_leads_routes_receive_no_runtime_secrets(self):
        forbidden = (
            "GOOGLE_SERVICE_ACCOUNT_JSON",
            "OUTREACH_MAIL_PASSWORD",
            "OUTREACH_MAILBOXES_JSON",
            "OUTREACH_SEED_INBOXES_JSON",
            "REOON_API_KEY",
        )
        for filename in LEGACY_LEADS_WORKFLOWS:
            text = (WORKFLOWS / filename).read_text(encoding="utf-8")
            for name in forbidden:
                self.assertNotIn(name, text, f"{filename}: disabled route must not receive {name}")

    def test_disabled_legacy_leads_routes_cannot_execute_domain_scripts(self):
        forbidden = (
            "scripts/outreach_",
            "scripts/prospect_",
            "smtp",
            "imap",
        )
        for filename in LEGACY_LEADS_WORKFLOWS:
            text = (WORKFLOWS / filename).read_text(encoding="utf-8").lower()
            self.assertNotIn("scripts/outreach_", text, filename)
            self.assertNotIn("scripts/prospect_", text, filename)
            self.assertNotIn("secrets.", text, filename)


if __name__ == "__main__":
    unittest.main()
