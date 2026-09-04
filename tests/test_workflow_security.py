import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


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

    def test_outreach_preflight_runs_before_verifier_and_sender(self):
        text = (WORKFLOWS / "outreach-smtp.yml").read_text(encoding="utf-8")
        preflight = text.index("- name: Run sender preflight")
        verifier = text.index("- name: Verify pending outreach emails")
        sender = text.index("- name: Process approved outreach queue")
        self.assertLess(preflight, verifier)
        self.assertLess(verifier, sender)

    def test_outreach_sender_step_never_receives_reoon_key(self):
        text = (WORKFLOWS / "outreach-smtp.yml").read_text(encoding="utf-8")
        sender = text.split("- name: Process approved outreach queue", 1)[1]
        self.assertNotIn("REOON_API_KEY", sender)

    def test_outreach_job_remains_disabled_without_explicit_flag(self):
        text = (WORKFLOWS / "outreach-smtp.yml").read_text(encoding="utf-8")
        self.assertIn("if: vars.OUTREACH_ENABLED == 'true'", text)


if __name__ == "__main__":
    unittest.main()
