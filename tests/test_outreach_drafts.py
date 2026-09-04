import sys
import unittest
from email.message import EmailMessage
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import outreach_drafts as d


class FakeImap:
    def __init__(self, host, port, ssl_context=None):
        self.host = host
        self.port = port
        self.logged_in = None
        self.appended = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def login(self, user, password):
        self.logged_in = (user, password)
        return "OK", []

    def list(self):
        return "OK", [
            b'(\\HasNoChildren) "/" "INBOX"',
            b'(\\HasNoChildren \\Drafts) "/" "Drafts"',
        ]

    def append(self, folder, flags, date_time, payload):
        self.appended = (folder, flags, payload)
        return "OK", [b"APPEND completed"]


class OutreachDraftTests(unittest.TestCase):
    def test_decode_mailbox_name(self):
        self.assertEqual(d._decode_mailbox_name(b'(\\Drafts) "/" "Drafts"'), "Drafts")
        self.assertEqual(d._decode_mailbox_name(b'(\\HasNoChildren) "." INBOX.Drafts'), "INBOX.Drafts")

    def test_find_drafts_folder_prefers_special_use_flag(self):
        fake = FakeImap("mail.example.com", 993)
        self.assertEqual(d.find_drafts_folder(fake), "Drafts")

    def test_append_draft_uses_imap_append(self):
        created = []
        def factory(host, port, ssl_context=None):
            instance = FakeImap(host, port, ssl_context)
            created.append(instance)
            return instance
        msg = EmailMessage()
        msg["From"] = "Andrew <info@example.com>"
        msg["To"] = "lead@example.org"
        msg["Subject"] = "Idee"
        msg.set_content("Body")
        mailbox = SimpleNamespace(mailbox_id="primary", imap_host="mail.example.com", imap_port=993, mail_user="info@example.com", mail_password="secret")
        folder = d.append_draft(msg, mailbox, imap_factory=factory)
        self.assertEqual(folder, "Drafts")
        self.assertEqual(created[0].logged_in, ("info@example.com", "secret"))
        self.assertEqual(created[0].appended[0], "Drafts")
        self.assertIn(b"Subject: Idee", created[0].appended[2])

    def test_fingerprint_is_stable(self):
        msg = EmailMessage()
        msg["Subject"] = "x"
        msg.set_content("y")
        self.assertEqual(d._draft_fingerprint(msg), d._draft_fingerprint(msg))


if __name__ == "__main__":
    unittest.main()
