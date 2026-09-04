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

    def test_outreach_policy_preflight_verifier_sender_order(self):
        text = (WORKFLOWS / "outreach-smtp.yml").read_text(encoding="utf-8")
        policy = text.index("- name: Resolve campaign pacing policy")
        preflight = text.index("- name: Run sender preflight")
        verifier = text.index("- name: Verify pending outreach emails")
        sender = text.index("- name: Process approved outreach queue")
        analytics = text.index("- name: Summarize outreach analytics")
        self.assertLess(policy, preflight)
        self.assertLess(preflight, verifier)
        self.assertLess(verifier, sender)
        self.assertLess(sender, analytics)

    def test_sender_uses_only_policy_reduced_mode_and_limits(self):
        text = (WORKFLOWS / "outreach-smtp.yml").read_text(encoding="utf-8")
        sender = text.split("- name: Process approved outreach queue", 1)[1].split(
            "- name: Summarize outreach analytics", 1
        )[0]
        self.assertIn("OUTREACH_MODE: ${{ steps.policy.outputs.effective_mode }}", sender)
        self.assertIn("OUTREACH_DAILY_LIMIT: ${{ steps.policy.outputs.effective_daily_limit }}", sender)
        self.assertIn(
            "OUTREACH_MAX_SENDS_PER_RUN: ${{ steps.policy.outputs.effective_max_sends_per_run }}",
            sender,
        )

    def test_outreach_sender_step_never_receives_reoon_key(self):
        text = (WORKFLOWS / "outreach-smtp.yml").read_text(encoding="utf-8")
        sender = text.split("- name: Process approved outreach queue", 1)[1].split(
            "- name: Summarize outreach analytics", 1
        )[0]
        self.assertNotIn("REOON_API_KEY", sender)

    def test_analytics_is_readback_only_and_non_blocking(self):
        text = (WORKFLOWS / "outreach-smtp.yml").read_text(encoding="utf-8")
        analytics = text.split("- name: Summarize outreach analytics", 1)[1]
        self.assertIn("continue-on-error: true", analytics)
        self.assertNotIn("OUTREACH_MAIL_PASSWORD", analytics)
        self.assertNotIn("REOON_API_KEY", analytics)

    def test_outreach_job_remains_disabled_without_explicit_flag(self):
        text = (WORKFLOWS / "outreach-smtp.yml").read_text(encoding="utf-8")
        self.assertIn("if: vars.OUTREACH_ENABLED == 'true'", text)


if __name__ == "__main__":
    unittest.main()
