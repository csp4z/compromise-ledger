from datetime import UTC, date, datetime, timedelta, timezone

import pytest
from ledger_schemas import (
    Correction,
    Incident,
    Organization,
    Product,
    ProductMention,
    Provenance,
    RawDocument,
    Relationship,
    Vendor,
    Vulnerability,
    make_id,
)
from pydantic import ValidationError


def test_id_is_derived_from_natural_key(provenance: Provenance) -> None:
    vuln = Vulnerability(cve_id="CVE-2024-3400", provenance=provenance)
    assert vuln.id == make_id("vulnerability", "CVE-2024-3400")


def test_reparse_gives_same_id(provenance: Provenance) -> None:
    a = Vendor(
        slug="palo-alto-networks",
        name="Palo Alto Networks",
        is_security_vendor=True,
        provenance=provenance,
    )
    b = Vendor(
        slug="palo-alto-networks",
        name="Palo Alto Networks, Inc.",
        is_security_vendor=True,
        provenance=provenance,
    )
    assert a.id == b.id


def test_round_trip_keeps_id(provenance: Provenance) -> None:
    vuln = Vulnerability(cve_id="CVE-2024-3400", provenance=provenance)
    assert Vulnerability.model_validate(vuln.model_dump()) == vuln
    assert Vulnerability.model_validate_json(vuln.model_dump_json()) == vuln


def test_supplied_id_must_match(provenance: Provenance) -> None:
    with pytest.raises(ValidationError, match="does not match natural key"):
        Vulnerability(
            id=make_id("vulnerability", "CVE-2024-0001"),
            cve_id="CVE-2024-3400",
            provenance=provenance,
        )


def test_missing_key_field_is_reported(provenance: Provenance) -> None:
    with pytest.raises(ValidationError, match="cve_id"):
        Vulnerability.model_validate({"provenance": provenance})


def test_rejects_unknown_fields(provenance: Provenance) -> None:
    with pytest.raises(ValidationError):
        Vulnerability.model_validate(
            {"cve_id": "CVE-2024-3400", "provenance": provenance, "exploit_url": "x"}
        )


def test_product_requires_vendor_identity(provenance: Provenance) -> None:
    vendor = Vendor(
        slug="fortinet", name="Fortinet", is_security_vendor=True, provenance=provenance
    )
    product = Product(vendor_id=vendor.id, slug="fortios", name="FortiOS", provenance=provenance)
    assert product.id == make_id("software", vendor.id, "fortios")
    with pytest.raises(ValidationError, match="identity"):
        Product(vendor_id=product.id, slug="x", name="X", provenance=provenance)


def test_relationship_key_and_time_order(provenance: Provenance) -> None:
    src = make_id("software", make_id("identity", "fortinet"), "fortios")
    dst = make_id("vulnerability", "CVE-2024-21762")
    rel = Relationship(
        relationship_type="has", source_ref=src, target_ref=dst, provenance=provenance
    )
    assert rel.id == make_id("relationship", "has", src, dst)
    now = datetime.now(UTC)
    with pytest.raises(ValidationError, match="stop_time"):
        Relationship(
            relationship_type="has",
            source_ref=src,
            target_ref=dst,
            start_time=now,
            stop_time=now - timedelta(days=1),
            provenance=provenance,
        )


def test_datetimes_normalized_to_utc(provenance: Provenance) -> None:
    pst = timezone(timedelta(hours=-8))
    vuln = Vulnerability(
        cve_id="CVE-2024-3400",
        published=datetime(2024, 4, 12, 4, tzinfo=pst),
        provenance=provenance,
    )
    assert vuln.published == datetime(2024, 4, 12, 12, tzinfo=UTC)
    assert vuln.published is not None and vuln.published.tzinfo == UTC


def test_naive_datetimes_rejected(provenance: Provenance) -> None:
    with pytest.raises(ValidationError):
        Vulnerability(
            cve_id="CVE-2024-3400", published=datetime(2024, 4, 12), provenance=provenance
        )


@pytest.mark.parametrize("cve", ["cve-2024-3400", "CVE-24-3400", "CVE-2024-12"])
def test_cve_id_format(cve: str, provenance: Provenance) -> None:
    with pytest.raises(ValidationError):
        Vulnerability(cve_id=cve, provenance=provenance)


def test_provenance_needs_exactly_one_source(provenance: Provenance) -> None:
    fields = provenance.model_dump()
    with pytest.raises(ValidationError, match="exactly one"):
        Provenance(**{**fields, "source_url": None})
    with pytest.raises(ValidationError, match="exactly one"):
        Provenance(**{**fields, "source_url_sha256": "b" * 64})
    hashed = Provenance(**{**fields, "source_url": None, "source_url_sha256": "b" * 64})
    assert hashed.source_url is None


@pytest.mark.parametrize("confidence", [-1, 101])
def test_confidence_bounds(confidence: int, provenance: Provenance) -> None:
    with pytest.raises(ValidationError):
        Provenance(**{**provenance.model_dump(), "confidence": confidence})


def test_correction_amend_rules() -> None:
    target = make_id("vulnerability", "CVE-2024-3400")
    decided = datetime(2026, 10, 24, tzinfo=UTC)
    suppress = Correction(
        request_ref="github#12",
        target_id=target,
        action="suppress",
        reason="out-of-policy",
        decided_at=decided,
    )
    assert suppress.id == make_id("x-ledger-correction", "github#12", target)
    amend = Correction(
        request_ref="github#12",
        target_id=target,
        action="amend",
        amend_field="kev_ransomware_use",
        amend_value='"unknown"',
        reason="inaccurate",
        decided_at=decided,
    )
    assert amend.id != suppress.id
    with pytest.raises(ValidationError, match="amend_field"):
        Correction(
            request_ref="github#12",
            target_id=target,
            action="amend",
            reason="inaccurate",
            decided_at=decided,
        )
    with pytest.raises(ValidationError, match="amend_field"):
        Correction(
            request_ref="github#12",
            target_id=target,
            action="suppress",
            amend_field="x",
            amend_value="1",
            reason="inaccurate",
            decided_at=decided,
        )


def test_raw_document_blob_key() -> None:
    sha = "ab" + "0" * 62
    doc = RawDocument(
        id=sha,
        source_id="cisa-kev",
        crawler_version="0.1.0",
        url="https://www.cisa.gov/feeds/known_exploited_vulnerabilities.json",
        fetched_at=datetime(2026, 10, 24, tzinfo=UTC),
        http_status=200,
        content_type="application/json",
        size_bytes=1234,
    )
    assert doc.blob_key == f"raw/cisa-kev/ab/{sha}"


def test_product_mention_key_tolerates_any_names(provenance: Provenance) -> None:
    vuln_id = make_id("vulnerability", "CVE-2024-3400")
    a = ProductMention(
        vulnerability_id=vuln_id, vendor_name="A|B", product_name="C", provenance=provenance
    )
    b = ProductMention(
        vulnerability_id=vuln_id, vendor_name="A", product_name="B|C", provenance=provenance
    )
    assert a.id != b.id
    with pytest.raises(ValidationError, match="vulnerability ID"):
        ProductMention(
            vulnerability_id=make_id("identity", "x"),
            vendor_name="A",
            product_name="B",
            provenance=provenance,
        )


def test_incident_keys_and_refs(provenance: Provenance) -> None:
    org = Organization(sec_cik="0000885725", name="Boston Scientific Corp", provenance=provenance)
    assert org.id == make_id("identity", "sec-cik", "0000885725")
    incident = Incident(
        organization_id=org.id,
        status="confirmed",
        disclosed_on=date(2026, 9, 8),
        sec_accession="0000885725-26-000059",
        sec_form="8-K",
        sec_item="1.05",
        provenance=provenance,
    )
    assert incident.id == make_id("incident", "sec", "0000885725-26-000059")
    with pytest.raises(ValidationError, match="identity"):
        Incident(**{**incident.model_dump(exclude={"id"}), "organization_id": incident.id})
    with pytest.raises(ValidationError):
        Organization(sec_cik="885725", name="Short CIK", provenance=provenance)
