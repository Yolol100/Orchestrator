import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import outreach_preflight as p
import outreach_sender as o


class TxtRecord:
    def __init__(self, value: str):
        self.strings = [value.encode("utf-8")]


class FakeSMTP:
    def __init__(self, host, port, **kwargs):
        self.host = host
        self.port = port
        self.logged_in = False
        self.tls = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def ehlo(self):
        return 250, b"ok"

    def has_extn(self, name):
        return name.lower() == "starttls"

    def starttls(self, context=None):
        self.tls = True
        return 220, b"ready"

    def login(self, user, password):
        self.logged_in = bool(user and password)
        return 235, b"ok"


class FakeIMAP:
    def __init__(self, host, port, **kwargs):
        self.host = host
        self.port = port

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def login(self, user, password):
        return "OK", [b"logged in"]

    def noop(self):
        return "OK", [b""]


def settings(mode="validate", password="secret"):
    return o.Settings(
        spreadsheet_id="sheet-id",
        mode=mode,
        timezone_name="Europe/Amsterdam",
        send_window_start="08:00",
        send_window_end="18:00",
        daily_send_limit=20,
        max_sends_per_run=2,
        verification_max_age_days=30,
        smtp_host="mail.example.com",
        smtp_port=587,
        imap_host="mail.example.com",
        imap_port=993,
        mail_user="info@example.com",
        mail_password=password,
        sender_name="Andrew",
        sender_email="info@example.com",
    )


class OutreachPreflightTests(unittest.TestCase):
    def test_static_live_requires_dkim_and_password(self):
        errors = p.validate_static(settings(mode="live", password=""), "", "include:spf.mijn.host")
        self.assertTrue(any("OUTREACH_MAIL_PASSWORD" in item for item in errors))
        self.assertTrue(any("OUTREACH_DKIM_SELECTOR" in item for item in errors))

    def test_dns_authentication_accepts_spf_dmarc_dkim(self):
        records = {
            "example.com": [TxtRecord("v=spf1 include:spf.mijn.host ~all")],
            "_dmarc.example.com": [TxtRecord("v=DMARC1; p=none")],
            "x._domainkey.example.com": [TxtRecord("v=DKIM1; k=rsa; p=abc123")],
        }

        def resolver(name, record_type):
            self.assertEqual(record_type, "TXT")
            return records[name]

        errors, checks = p.check_dns_authentication(
            "example.com", "x", "include:spf.mijn.host", resolver=resolver
        )
        self.assertEqual(errors, [])
        self.assertEqual(set(checks), {"spf", "dmarc", "dkim"})

    def test_dns_authentication_rejects_wrong_spf_source(self):
        records = {
            "example.com": [TxtRecord("v=spf1 include:other.example ~all")],
            "_dmarc.example.com": [TxtRecord("v=DMARC1; p=none")],
            "x._domainkey.example.com": [TxtRecord("v=DKIM1; p=abc123")],
        }

        errors, _ = p.check_dns_authentication(
            "example.com",
            "x",
            "include:spf.mijn.host",
            resolver=lambda name, _: records[name],
        )
        self.assertTrue(any("missing required token" in item for item in errors))

    def test_sheet_contract_checks_all_transport_tabs(self):
        values = {
            o.QUEUE_SHEET: [o.QUEUE_HEADERS],
            o.SUPPRESSION_SHEET: [o.SUPPRESSION_HEADERS],
            o.LOG_SHEET: [o.LOG_HEADERS],
        }
        with patch.object(p, "get_values", side_effect=lambda service, spreadsheet_id, name: values[name]):
            checks = p.check_sheet_contract(object(), "sheet-id")
        self.assertEqual(
            checks,
            ["sheet:OutreachQueue", "sheet:Suppression", "sheet:OutreachLog"],
        )

    def test_live_mailbox_auth_uses_starttls_and_imap_ssl(self):
        checks = p.check_mailbox_auth(
            settings(mode="live"),
            smtp_factory=FakeSMTP,
            smtp_ssl_factory=FakeSMTP,
            imap_factory=FakeIMAP,
        )
        self.assertEqual(checks, ["smtp-auth", "imap-auth"])

    def test_non_live_mailbox_auth_does_not_login(self):
        self.assertEqual(p.check_mailbox_auth(settings(mode="verify")), [])


if __name__ == "__main__":
    unittest.main()
