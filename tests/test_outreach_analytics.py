import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import outreach_analytics as a


class OutreachAnalyticsTests(unittest.TestCase):
    def test_metrics_distinguish_smtp_acceptance_from_outcomes(self):
        rows = [
            {
                "status": "replied",
                "sent_at": "2026-09-04T07:00:00Z",
                "followup_sent_at": "",
                "verification_status": "safe",
            },
            {
                "status": "bounced",
                "sent_at": "2026-09-04T07:30:00Z",
                "followup_sent_at": "",
                "verification_status": "safe",
            },
            {
                "status": "opted_out",
                "sent_at": "2026-09-03T07:30:00Z",
                "followup_sent_at": "2026-09-04T08:30:00Z",
                "verification_status": "safe",
            },
            {
                "status": "approved",
                "sent_at": "",
                "followup_sent_at": "",
                "verification_status": "safe",
            },
        ]
        metrics = a.build_metrics(
            rows,
            datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc),
            "Europe/Amsterdam",
        )
        self.assertEqual(metrics["total_rows"], 4)
        self.assertEqual(metrics["initial_sent_total"], 3)
        self.assertEqual(metrics["initial_sent_today"], 2)
        self.assertEqual(metrics["followup_sent_today"], 1)
        self.assertEqual(metrics["replied"], 1)
        self.assertEqual(metrics["bounced"], 1)
        self.assertEqual(metrics["opted_out"], 1)
        self.assertEqual(metrics["reply_rate"], 33.33)
        self.assertEqual(metrics["bounce_rate"], 33.33)
        self.assertEqual(metrics["opt_out_rate"], 33.33)

    def test_due_followup_and_ready_initial_are_counted(self):
        rows = [
            {"status": "approved", "verification_status": "safe"},
            {
                "status": "sent",
                "followup_body": "Follow up",
                "next_send_at": "2026-09-04T09:00:00Z",
                "verification_status": "safe",
            },
            {
                "status": "sent",
                "followup_body": "Later",
                "next_send_at": "2026-09-05T09:00:00Z",
                "verification_status": "safe",
            },
        ]
        metrics = a.build_metrics(
            rows,
            datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc),
            "Europe/Amsterdam",
        )
        self.assertEqual(metrics["ready_initial"], 1)
        self.assertEqual(metrics["due_followup"], 1)

    def test_markdown_includes_policy_without_claiming_delivery(self):
        metrics = {
            "total_rows": 1,
            "status_counts": {"sent": 1},
            "verification_counts": {"safe": 1},
            "initial_sent_total": 1,
            "followup_sent_total": 0,
            "initial_sent_today": 1,
            "followup_sent_today": 0,
            "ready_initial": 0,
            "due_followup": 0,
            "reply_rate": 0.0,
            "bounce_rate": 0.0,
            "opt_out_rate": 0.0,
            "replied": 0,
            "bounced": 0,
            "opted_out": 0,
        }
        report = a.render_markdown(
            metrics,
            suppression_count=0,
            policy_reason="active_window",
            effective_mode="live",
            effective_daily_limit="8",
            effective_max_sends_per_run="1",
        )
        self.assertIn("SMTP-accepted", report)
        self.assertIn("not proof of inbox placement", report)
        self.assertIn("effective daily limit: `8`", report)


if __name__ == "__main__":
    unittest.main()
