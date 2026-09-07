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

    def test_legacy_leads_domain_workflows_are_absent(self):
        for filename in LEGACY_LEADS_WORKFLOWS:
            self.assertFalse((WORKFLOWS / filename).exists(), filename)

    def test_orchestrator_contains_no_outreach_domain_scripts(self):
        scripts = ROOT / "scripts"
        names = {path.name for path in scripts.glob("*.py")}
        self.assertFalse(any(name.startswith("outreach_") for name in names))
        self.assertFalse(any(name.startswith("prospect_discovery") for name in names))

    def test_orchestrator_workflows_receive_no_leads_runtime_secrets(self):
        forbidden = (
            "GOOGLE_SERVICE_ACCOUNT_JSON",
            "OUTREACH_MAIL_PASSWORD",
            "OUTREACH_MAILBOXES_JSON",
            "OUTREACH_SEED_INBOXES_JSON",
            "REOON_API_KEY",
        )
        for path in sorted(WORKFLOWS.glob("*.yml")):
            text = path.read_text(encoding="utf-8")
            for name in forbidden:
                self.assertNotIn(name, text, f"{path.name}: Orchestrator must not receive {name}")


if __name__ == "__main__":
    unittest.main()
