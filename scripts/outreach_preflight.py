from __future__ import annotations

import imaplib
import os
import smtplib
import ssl
from dataclasses import dataclass
from typing import Callable, Iterable

import dns.resolver

from outreach_sender import (
    LOG_HEADERS,
    LOG_SHEET,
    QUEUE_HEADERS,
    QUEUE_SHEET,
    SUPPRESSION_HEADERS,
    SUPPRESSION_SHEET,
    Settings,
    build_sheets_service,
    domain_of,
    ensure_expected_headers,
    get_values,
    normalize_address,
    rows_from_values,
)


@dataclass(frozen=True)
class PreflightReport:
    checks: tuple[str, ...]
    warnings: tuple[str, ...]


def _txt_values(name: str, resolver: Callable[[str, str], Iterable] = dns.resolver.resolve) -> list[str]:
    values: list[str] = []
    for record in resolver(name, "TXT"):
        if hasattr(record, "strings"):
            chunks = []
            for item in record.strings:
                chunks.append(item.decode("utf-8", errors="replace") if isinstance(item, bytes) else str(item))
            values.append("".join(chunks))
        else:
            values.append(str(record).strip('"').replace('" "', ""))
    return values


def validate_static(settings: Settings, dkim_selector: str, required_spf_token: str) -> list[str]:
    errors: list[str] = []
    sender = normalize_address(settings.sender_email)
    user = normalize_address(settings.mail_user)
    if not settings.spreadsheet_id:
        errors.append("OUTREACH_SPREADSHEET_ID is required")
    if not sender or "@" not in sender:
        errors.append("OUTREACH_SENDER_EMAIL must be a valid email address")
    if not user or "@" not in user:
        errors.append("OUTREACH_MAIL_USER must be a valid email address")
    if sender and user and domain_of(sender) != domain_of(user):
        errors.append("sender email and mailbox user must use the same domain")
    if not settings.sender_name.strip():
        errors.append("OUTREACH_SENDER_NAME is required")
    if not settings.smtp_host.strip():
        errors.append("OUTREACH_SMTP_HOST is required")
    if settings.smtp_port not in {465, 587}:
        errors.append("OUTREACH_SMTP_PORT must be 465 or 587")
    if not settings.imap_host.strip():
        errors.append("OUTREACH_IMAP_HOST is required")
    if settings.imap_port != 993:
        errors.append("OUTREACH_IMAP_PORT must be 993 for the guarded runtime")
    if settings.mode == "live" and not settings.mail_password:
        errors.append("OUTREACH_MAIL_PASSWORD is required in live mode")
    if settings.mode == "live" and not dkim_selector:
        errors.append("OUTREACH_DKIM_SELECTOR is required in live mode")
    if required_spf_token and any(ch.isspace() for ch in required_spf_token):
        errors.append("OUTREACH_REQUIRED_SPF_TOKEN must be one SPF token without whitespace")
    return errors


def check_dns_authentication(
    sender_domain: str,
    dkim_selector: str,
    required_spf_token: str,
    resolver: Callable[[str, str], Iterable] = dns.resolver.resolve,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    checks: list[str] = []

    try:
        root_txt = _txt_values(sender_domain, resolver)
    except Exception as exc:
        return [f"SPF DNS lookup failed for {sender_domain}: {type(exc).__name__}: {exc}"], checks
    spf = [value for value in root_txt if value.lower().startswith("v=spf1")]
    if len(spf) != 1:
        errors.append(f"expected exactly one SPF record for {sender_domain}; found {len(spf)}")
    else:
        if required_spf_token and required_spf_token.lower() not in spf[0].lower().split():
            errors.append(f"SPF record is missing required token {required_spf_token}")
        else:
            checks.append("spf")

    try:
        dmarc_txt = _txt_values(f"_dmarc.{sender_domain}", resolver)
    except Exception as exc:
        errors.append(f"DMARC DNS lookup failed for {sender_domain}: {type(exc).__name__}: {exc}")
    else:
        dmarc = [value for value in dmarc_txt if value.lower().startswith("v=dmarc1")]
        if len(dmarc) != 1:
            errors.append(f"expected exactly one DMARC record for {sender_domain}; found {len(dmarc)}")
        else:
            checks.append("dmarc")

    if dkim_selector:
        name = f"{dkim_selector}._domainkey.{sender_domain}"
        try:
            dkim_txt = _txt_values(name, resolver)
        except Exception as exc:
            errors.append(f"DKIM DNS lookup failed for {name}: {type(exc).__name__}: {exc}")
        else:
            dkim = [value for value in dkim_txt if "p=" in value.lower() or value.lower().startswith("v=dkim1")]
            if not dkim:
                errors.append(f"no DKIM public key found at {name}")
            else:
                checks.append("dkim")

    return errors, checks


def check_sheet_contract(service, spreadsheet_id: str) -> list[str]:
    checks: list[str] = []
    for name, expected in (
        (QUEUE_SHEET, QUEUE_HEADERS),
        (SUPPRESSION_SHEET, SUPPRESSION_HEADERS),
        (LOG_SHEET, LOG_HEADERS),
    ):
        headers, _ = rows_from_values(get_values(service, spreadsheet_id, name))
        ensure_expected_headers(headers, expected, name)
        checks.append(f"sheet:{name}")
    return checks


def check_mailbox_auth(
    settings: Settings,
    smtp_factory: Callable = smtplib.SMTP,
    smtp_ssl_factory: Callable = smtplib.SMTP_SSL,
    imap_factory: Callable = imaplib.IMAP4_SSL,
) -> list[str]:
    if settings.mode != "live":
        return []
    context = ssl.create_default_context()
    if settings.smtp_port == 465:
        with smtp_ssl_factory(settings.smtp_host, settings.smtp_port, context=context, timeout=30) as smtp:
            smtp.login(settings.mail_user, settings.mail_password)
    else:
        with smtp_factory(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
            smtp.ehlo()
            if not smtp.has_extn("starttls"):
                raise RuntimeError("SMTP server does not advertise STARTTLS")
            smtp.starttls(context=context)
            smtp.ehlo()
            smtp.login(settings.mail_user, settings.mail_password)

    with imap_factory(settings.imap_host, settings.imap_port, ssl_context=context) as imap:
        imap.login(settings.mail_user, settings.mail_password)
        status, _ = imap.noop()
        if status != "OK":
            raise RuntimeError("IMAP NOOP failed")
    return ["smtp-auth", "imap-auth"]


def run_preflight() -> PreflightReport:
    settings = Settings.from_env()
    dkim_selector = os.getenv("OUTREACH_DKIM_SELECTOR", "").strip()
    required_spf_token = os.getenv("OUTREACH_REQUIRED_SPF_TOKEN", "").strip()
    errors = validate_static(settings, dkim_selector, required_spf_token)
    if errors:
        raise RuntimeError("preflight configuration failed: " + "; ".join(errors))

    checks: list[str] = ["config"]
    warnings: list[str] = []
    sender_domain = domain_of(settings.sender_email)

    dns_errors, dns_checks = check_dns_authentication(
        sender_domain,
        dkim_selector,
        required_spf_token,
    )
    if dns_errors:
        raise RuntimeError("preflight DNS authentication failed: " + "; ".join(dns_errors))
    checks.extend(dns_checks)
    if not dkim_selector:
        warnings.append("DKIM selector not supplied; live mode will fail closed")

    if not os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip():
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON is required for Sheet preflight")
    service = build_sheets_service()
    checks.extend(check_sheet_contract(service, settings.spreadsheet_id))
    checks.extend(check_mailbox_auth(settings))

    return PreflightReport(tuple(checks), tuple(warnings))


def main() -> int:
    report = run_preflight()
    print("SENDER_PREFLIGHT=green checks=" + ",".join(report.checks))
    for warning in report.warnings:
        print("warning=" + warning)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
