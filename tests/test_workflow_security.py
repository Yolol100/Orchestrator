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

    def test_outreach_policy_preflights_compliance_before_sender(self):
        text = (WORKFLOWS / "outreach-smtp.yml").read_text(encoding="utf-8")
        policy = text.index("- name: Resolve campaign pacing policy")
        preflight = text.index("- name: Run sender preflight")
        extended = text.index("- name: Run extended outreach contract preflight")
        compliance = text.index("- name: Run outreach compliance preflight")
        sender = text.index("- name: Process approved outreach queue")
        analytics = text.index("- name: Summarize outreach analytics")
        self.assertLess(policy, preflight)
        self.assertLess(preflight, extended)
        self.assertLess(extended, compliance)
        self.assertLess(compliance, sender)
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
        self.assertIn("run: python3 scripts/outreach_direct_smtp_runtime.py", sender)

    def test_active_smtp_workflow_has_no_reoon_dependency(self):
        text = (WORKFLOWS / "outreach-smtp.yml").read_text(encoding="utf-8")
        self.assertNotIn("REOON_API_KEY", text)
        self.assertNotIn("outreach_verifier.py", text)
        self.assertNotIn("Verify pending outreach emails", text)

    def test_mailbox_pool_secret_is_scoped_to_sender_preflight_and_sender(self):
        text = (WORKFLOWS / "outreach-smtp.yml").read_text(encoding="utf-8")
        preflight = text.split("- name: Run sender preflight", 1)[1].split(
            "- name: Run extended outreach contract preflight", 1
        )[0]
        extended = text.split("- name: Run extended outreach contract preflight", 1)[1].split(
            "- name: Run outreach compliance preflight", 1
        )[0]
        compliance = text.split("- name: Run outreach compliance preflight", 1)[1].split(
            "- name: Process approved outreach queue", 1
        )[0]
        sender = text.split("- name: Process approved outreach queue", 1)[1].split(
            "- name: Summarize outreach analytics", 1
        )[0]
        analytics = text.split("- name: Summarize outreach analytics", 1)[1]
        self.assertIn("OUTREACH_MAILBOXES_JSON: ${{ secrets.OUTREACH_MAILBOXES_JSON }}", preflight)
        self.assertIn("OUTREACH_MAILBOXES_JSON: ${{ secrets.OUTREACH_MAILBOXES_JSON }}", sender)
        self.assertNotIn("OUTREACH_MAILBOXES_JSON", extended)
        self.assertNotIn("OUTREACH_MAILBOXES_JSON", compliance)
        self.assertNotIn("OUTREACH_MAILBOXES_JSON", analytics)

    def test_reporting_is_non_blocking_and_has_no_mail_secrets(self):
        text = (WORKFLOWS / "outreach-smtp.yml").read_text(encoding="utf-8")
        analytics = text.split("- name: Summarize outreach analytics", 1)[1]
        self.assertIn("continue-on-error: true", analytics)
        self.assertIn("run: python3 scripts/outreach_reporting.py", analytics)
        self.assertNotIn("OUTREACH_MAIL_PASSWORD", analytics)
        self.assertNotIn("OUTREACH_MAILBOXES_JSON", analytics)
        self.assertNotIn("REOON_API_KEY", analytics)

    def test_extended_and_compliance_preflights_have_sheet_access_only(self):
        text = (WORKFLOWS / "outreach-smtp.yml").read_text(encoding="utf-8")
        extended = text.split("- name: Run extended outreach contract preflight", 1)[1].split(
            "- name: Run outreach compliance preflight", 1
        )[0]
        compliance = text.split("- name: Run outreach compliance preflight", 1)[1].split(
            "- name: Process approved outreach queue", 1
        )[0]
        for section in (extended, compliance):
            self.assertIn("GOOGLE_SERVICE_ACCOUNT_JSON", section)
            self.assertNotIn("OUTREACH_MAIL_PASSWORD", section)
            self.assertNotIn("OUTREACH_MAILBOXES_JSON", section)
            self.assertNotIn("REOON_API_KEY", section)

    def test_drafts_workflow_is_manual_and_password_only_reaches_draft_writer(self):
        text = (WORKFLOWS / "outreach-drafts.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("schedule:", text)
        extended = text.split("- name: Run extended outreach contract preflight", 1)[1].split(
            "- name: Validate outreach compliance state", 1
        )[0]
        compliance = text.split("- name: Validate outreach compliance state", 1)[1].split(
            "- name: Save approved initial emails to mijn.host Drafts", 1
        )[0]
        draft_writer = text.split("- name: Save approved initial emails to mijn.host Drafts", 1)[1]
        self.assertNotIn("OUTREACH_MAIL_PASSWORD", extended)
        self.assertNotIn("OUTREACH_MAIL_PASSWORD", compliance)
        self.assertIn("OUTREACH_MAIL_PASSWORD: ${{ secrets.OUTREACH_MAIL_PASSWORD }}", draft_writer)
        self.assertIn("run: python3 scripts/outreach_drafts.py", draft_writer)
        self.assertNotIn("REOON_API_KEY", text)

    def test_outreach_job_remains_disabled_without_explicit_flag(self):
        text = (WORKFLOWS / "outreach-smtp.yml").read_text(encoding="utf-8")
        self.assertIn("if: vars.OUTREACH_ENABLED == 'true'", text)


if __name__ == "__main__":
    unittest.main()
