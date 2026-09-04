import json
import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import outreach_verifier as v


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class OutreachVerifierTests(unittest.TestCase):
    def test_bulk_requires_at_least_ten(self):
        with self.assertRaises(ValueError):
            v.reoon_verify_bulk([f"a{i}@example.com" for i in range(9)], "key", opener=lambda *args, **kwargs: None)

    def test_bulk_create_poll_and_normalize(self):
        emails = [f"a{i}@example.com" for i in range(10)]
        calls = []

        def opener(request, timeout=90):
            calls.append(request)
            if isinstance(request, Request):
                body = json.loads(request.data.decode("utf-8"))
                self.assertEqual(body["emails"], emails)
                return FakeResponse({"status": "success", "task_id": 123, "count_submitted": 10})
            if len(calls) == 2:
                return FakeResponse({"status": "running", "task_id": "123", "progress_percentage": 50})
            return FakeResponse({
                "status": "completed",
                "task_id": "123",
                "results": {
                    email: {"email": email, "status": "safe", "is_safe_to_send": True}
                    for email in emails
                },
            })

        results = v.reoon_verify_bulk(emails, "key", opener=opener, sleeper=lambda _: None, max_polls=3)
        self.assertEqual(set(results), set(emails))
        self.assertTrue(all(item["is_safe_to_send"] for item in results.values()))
        self.assertEqual(len(calls), 3)

    def test_bulk_terminal_error_fails_closed(self):
        emails = [f"a{i}@example.com" for i in range(10)]
        calls = 0

        def opener(request, timeout=90):
            nonlocal calls
            calls += 1
            if calls == 1:
                return FakeResponse({"status": "success", "task_id": 123})
            return FakeResponse({"status": "file_loading_error", "task_id": "123"})

        with self.assertRaises(RuntimeError):
            v.reoon_verify_bulk(emails, "key", opener=opener, sleeper=lambda _: None, max_polls=2)

    def test_normalize_bulk_results_accepts_list(self):
        payload = {"results": [{"email": "A@Example.com", "status": "safe", "is_safe_to_send": True}]}
        normalized = v.normalize_bulk_results(payload)
        self.assertIn("a@example.com", normalized)

    def test_candidate_indexes_include_pending_but_skip_fresh_safe(self):
        now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
        rows = [
            {"status": "approved", "verification_status": "", "verification_checked_at": ""},
            {"status": "verification_pending", "verification_status": "", "verification_checked_at": ""},
            {"status": "approved", "verification_status": "safe", "verification_checked_at": "2026-09-03T12:00:00Z"},
            {"status": "manual_review", "verification_status": "", "verification_checked_at": ""},
        ]
        self.assertEqual(v.candidate_indexes(rows, now, 30), [0, 1])

    def test_max_verifications_is_bounded(self):
        old = os.environ.get("OUTREACH_MAX_VERIFICATIONS_PER_RUN")
        try:
            os.environ["OUTREACH_MAX_VERIFICATIONS_PER_RUN"] = "50"
            self.assertEqual(v.max_verifications_from_env(), 50)
            os.environ["OUTREACH_MAX_VERIFICATIONS_PER_RUN"] = "501"
            with self.assertRaises(ValueError):
                v.max_verifications_from_env()
        finally:
            if old is None:
                os.environ.pop("OUTREACH_MAX_VERIFICATIONS_PER_RUN", None)
            else:
                os.environ["OUTREACH_MAX_VERIFICATIONS_PER_RUN"] = old


if __name__ == "__main__":
    unittest.main()
