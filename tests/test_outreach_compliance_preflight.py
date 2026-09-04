from scripts.outreach_compliance_preflight import compliance_errors


def row(country: str, basis: str) -> dict[str, str]:
    return {"country": country, "compliance_basis": basis}


def test_nl_consent_allowed():
    assert compliance_errors(row("Nederland", "consent")) == []


def test_nl_existing_customer_allowed():
    assert compliance_errors(row("NL", "existing_customer_similar")) == []


def test_nl_other_basis_blocked():
    assert compliance_errors(row("Nederland", "other_verified_basis"))


def test_missing_country_blocked():
    assert compliance_errors(row("", "consent"))


def test_missing_basis_blocked():
    assert compliance_errors(row("United States", ""))


def test_non_eea_verified_basis_allowed():
    assert compliance_errors(row("United States", "other_verified_basis")) == []
