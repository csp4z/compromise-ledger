import json
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path

import pyarrow as pa
import pytest
from ledger_pipelines.arrow import to_table
from ledger_pipelines.corrections import apply_corrections
from ledger_pipelines.export import ExportTable, Source, export, verify
from ledger_pipelines.gold import build_gold, gold_files
from ledger_pipelines.lakehouse import TABLES
from ledger_schemas import (
    Correction,
    CveCount,
    Incident,
    Organization,
    Product,
    Provenance,
    Relationship,
    UnresolvedVendorName,
    Vendor,
    Vulnerability,
    make_id,
)
from pydantic import BaseModel

NOW = datetime(2026, 10, 24, tzinfo=UTC)


def prov(parser_id: str = "cisa-kev", confidence: int = 95) -> Provenance:
    return Provenance(
        source_url="https://www.cisa.gov/feed.json",
        raw_document_id="a" * 64,
        crawled_at=NOW,
        parser_id=parser_id,
        parser_version="0.1.0",
        confidence=confidence,
        license="CC0-1.0",
    )


def kev(cve: str, added: date, ransomware: str = "unknown") -> Vulnerability:
    return Vulnerability(
        cve_id=cve,
        description=f"{cve} from KEV",
        kev_date_added=added,
        kev_due_date=added,
        kev_ransomware_use=ransomware,  # type: ignore[arg-type]
        provenance=prov(),
    )


def silver() -> dict[str, Sequence[BaseModel]]:
    fortinet = Vendor(
        slug="fortinet",
        name="Fortinet",
        is_security_vendor=True,
        cpe_vendor="fortinet",
        provenance=prov("vendor-resolution", 90),
    )
    microsoft = Vendor(
        slug="microsoft",
        name="Microsoft",
        is_security_vendor=False,
        provenance=prov("vendor-resolution", 90),
    )
    fortios = Product(
        vendor_id=fortinet.id, slug="fortios", name="FortiOS", provenance=prov("vendor-resolution")
    )
    windows = Product(
        vendor_id=microsoft.id, slug="windows", name="Windows", provenance=prov("vendor-resolution")
    )
    vulns = [
        kev("CVE-2024-21762", date(2024, 2, 9), "known"),
        kev("CVE-2024-0001", date(2024, 2, 20)),
        kev("CVE-2024-0002", date(2024, 3, 1)),  # vendor unresolved: no relationship
        # An NVD-like row for the same CVE: gold merges it with the KEV row.
        Vulnerability(
            cve_id="CVE-2024-21762",
            description="NVD text",
            published=datetime(2024, 2, 8, tzinfo=UTC),
            cvss_v3_base_score=9.8,
            provenance=prov("nvd", 99),
        ),
    ]
    rels = [
        Relationship(
            relationship_type="has",
            source_ref=fortios.id,
            target_ref=make_id("vulnerability", "CVE-2024-21762"),
            provenance=prov("vendor-resolution"),
        ),
        Relationship(
            relationship_type="has",
            source_ref=windows.id,
            target_ref=make_id("vulnerability", "CVE-2024-0001"),
            provenance=prov("vendor-resolution"),
        ),
    ]
    return {
        "silver.vendors": [fortinet, microsoft],
        "silver.products": [fortios, windows],
        "silver.vulnerabilities": vulns,
        "silver.relationships": rels,
        "silver.product_mentions": [],
        "silver.organizations": [],
        "silver.incidents": [],
        "silver.cve_counts": [
            cve_count("fortinet", "all", 1000),
            cve_count("fortinet", "kev", 30),
            # Microsoft has no cpe_vendor in these seeds, so its counts join to nothing.
            cve_count("microsoft", "all", 9000),
            cve_count("microsoft", "kev", 300),
        ],
    }


def cve_count(cpe_vendor: str, scope: str, count: int) -> CveCount:
    return CveCount(
        cpe_vendor=cpe_vendor,
        scope=scope,  # type: ignore[arg-type]
        cve_count=count,
        provenance=prov("nvd-cve-counts"),
    )


def tables(records: Mapping[str, Sequence[BaseModel]]) -> dict[str, pa.Table]:
    return {name: to_table(TABLES[name], rows) for name, rows in records.items()}


def inputs(corrections: Sequence[Correction] = ()) -> dict[str, pa.Table]:
    corrected = apply_corrections(tables(silver()), list(corrections))
    unresolved = [
        UnresolvedVendorName(vendor_name="Npm package", mentions=1, parser_ids=["cisa-kev"])
    ]
    return corrected | tables(
        {"ops.unresolved_vendor_names": unresolved, "silver.corrections": list(corrections)}
    )


def test_gold_files_are_ordered_and_named() -> None:
    names = [name for name, _ in gold_files()]
    assert names[:2] == ["vulnerabilities", "kev_vendor_products"]
    assert len(names) == len(set(names))


def test_vulnerabilities_merge_sources() -> None:
    gold = build_gold(inputs())
    rows = {r["cve_id"]: r for r in gold["vulnerabilities"].to_pylist()}
    assert len(rows) == 3
    merged = rows["CVE-2024-21762"]
    assert merged["description"] == "NVD text"  # higher confidence wins
    assert merged["cvss_v3_base_score"] == 9.8
    assert merged["kev_date_added"] == date(2024, 2, 9)
    assert merged["days_to_kev"] == 1
    assert merged["sources"] == "cisa-kev;nvd"
    assert (
        merged["published"].tzinfo is not None
        and merged["published"].utcoffset().total_seconds() == 0
    )


def test_vendor_totals_and_monthly_share() -> None:
    gold = build_gold(inputs())
    vendors = {r["slug"]: r for r in gold["vendors"].to_pylist()}
    assert vendors["fortinet"]["kev_count"] == 1
    assert vendors["fortinet"]["kev_ransomware_known"] == 1
    monthly = {r["month"]: r for r in gold["security_vendor_kev_monthly"].to_pylist()}
    feb = monthly[date(2024, 2, 1)]
    assert (feb["kev_added"], feb["security_vendor_kev_added"]) == (2, 1)
    assert feb["security_vendor_share"] == 0.5
    # The unresolved CVE still counts toward the total.
    assert monthly[date(2024, 3, 1)]["kev_added"] == 1
    assert gold["unresolved_vendor_names"].to_pylist()[0]["vendor_name"] == "Npm package"


def correction(action: str, target: str, **kwargs: str) -> Correction:
    return Correction(
        request_ref="github#1",
        target_id=target,
        action=action,  # type: ignore[arg-type]
        reason="inaccurate",
        decided_at=NOW,
        **kwargs,
    )


def test_suppressing_a_vendor_removes_its_products_and_links() -> None:
    gold = build_gold(inputs([correction("suppress", make_id("identity", "fortinet"))]))
    assert "fortinet" not in {r["slug"] for r in gold["vendors"].to_pylist()}
    assert {r["vendor_slug"] for r in gold["kev_vendor_products"].to_pylist()} == {"microsoft"}
    # The CVE itself stays: only the vendor was suppressed.
    assert len(gold["vulnerabilities"]) == 3


def test_corrections_log_lists_decisions_without_amended_values() -> None:
    amend = correction(
        "amend",
        make_id("vulnerability", "CVE-2024-0001"),
        amend_field="kev_ransomware_use",
        amend_value='"known"',
    )
    (row,) = build_gold(inputs([amend]))["corrections_log"].to_pylist()
    assert (row["target_id"], row["action"], row["amend_field"]) == (
        amend.target_id,
        "amend",
        "kev_ransomware_use",
    )
    assert "amend_value" not in row


def filing(org: Organization, day: date, form: str, item: str, n: int) -> Incident:
    return Incident(
        organization_id=org.id,
        status="confirmed",
        disclosed_on=day,
        sec_accession=f"0000000001-26-{n:06d}",
        sec_form=form,  # type: ignore[arg-type]
        sec_item=item,  # type: ignore[arg-type]
        provenance=prov("sec-8k", 90 if item == "1.05" else 75),
    )


def test_incidents_group_a_companys_filings() -> None:
    org = Organization(sec_cik="0000000001", name="Example Corp", provenance=prov("sec-8k"))
    first = filing(org, date(2026, 1, 5), "8-K", "8.01", 1)
    filings = [
        first,
        filing(org, date(2026, 1, 20), "8-K", "1.05", 2),  # escalated: same incident
        filing(org, date(2026, 6, 1), "8-K/A", "1.05", 3),  # amendment: same incident
        filing(org, date(2026, 9, 1), "8-K", "8.01", 4),  # 224 days later: a new incident
    ]
    records = silver()
    records["silver.organizations"] = [org]
    records["silver.incidents"] = filings
    corrected = apply_corrections(tables(records), [])
    extra = tables({"ops.unresolved_vendor_names": [], "silver.corrections": []})
    gold = build_gold(corrected | extra)
    incidents = gold["incidents"].to_pylist()
    assert [(i["first_disclosed_on"], i["filings"], i["material"]) for i in incidents] == [
        (date(2026, 9, 1), 1, False),
        (date(2026, 1, 5), 3, True),
    ]
    grouped = incidents[1]
    assert grouped["incident_id"] == first.id
    assert grouped["confidence"] == 90
    assert grouped["sec_accessions"].split(";")[0] == first.sec_accession
    assert gold["incident_filings"].num_rows == 4


def test_suppressing_an_organization_removes_its_incidents() -> None:
    org = Organization(sec_cik="0000885725", name="Example Corp", provenance=prov("sec-8k"))
    incident = Incident(
        organization_id=org.id,
        status="confirmed",
        disclosed_on=date(2026, 9, 8),
        sec_accession="0000885725-26-000059",
        sec_form="8-K",
        sec_item="1.05",
        provenance=prov("sec-8k"),
    )
    silver = tables({"silver.organizations": [org], "silver.incidents": [incident]})
    corrected = apply_corrections(silver, [correction("suppress", org.id)])
    assert corrected["silver.organizations"].num_rows == 0
    assert corrected["silver.incidents"].num_rows == 0


def test_suppressing_a_vulnerability_removes_every_row_about_it() -> None:
    target = make_id("vulnerability", "CVE-2024-21762")
    gold = build_gold(inputs([correction("suppress", target)]))
    assert "CVE-2024-21762" not in {r["cve_id"] for r in gold["vulnerabilities"].to_pylist()}
    assert "CVE-2024-21762" not in {r["cve_id"] for r in gold["kev_vendor_products"].to_pylist()}


def test_amend_changes_a_field_everywhere() -> None:
    target = make_id("vulnerability", "CVE-2024-0001")
    amend = correction("amend", target, amend_field="kev_ransomware_use", amend_value='"known"')
    gold = build_gold(inputs([amend]))
    row = next(r for r in gold["vulnerabilities"].to_pylist() if r["cve_id"] == "CVE-2024-0001")
    assert row["kev_ransomware_use"] == "known"


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [("cve_id", '"CVE-2024-9999"', "natural key"), ("no_such_field", "1", "no field")],
)
def test_amend_cannot_break_keys_or_schema(field: str, value: str, message: str) -> None:
    target = make_id("vulnerability", "CVE-2024-0001")
    with pytest.raises(ValueError, match=message):
        inputs([correction("amend", target, amend_field=field, amend_value=value)])


def test_export_writes_files_and_a_verifiable_manifest(tmp_path: Path) -> None:
    gold = build_gold(inputs())
    items = [ExportTable(name, table, snapshot_id=7) for name, table in gold.items()]
    sources = [Source("cisa-kev", "CISA KEV", "CC0-1.0")]
    manifest = export(items, sources, tmp_path, generated_at=NOW)
    assert {f["format"] for f in manifest["files"]} == {"parquet", "csv", "json"}
    assert len(manifest["files"]) == 3 * len(gold)
    on_disk = json.loads((tmp_path / "datasets.json").read_text())
    assert on_disk == manifest and on_disk["license"] == "CC-BY-4.0"
    vulns = json.loads((tmp_path / "vulnerabilities.json").read_text())
    assert {v["cve_id"] for v in vulns} >= {"CVE-2024-21762"}
    assert verify(tmp_path) == []

    (tmp_path / "vendors.csv").write_text("tampered\n")
    (tmp_path / "vendors.json").unlink()
    assert sorted(verify(tmp_path)) == ["vendors.csv: checksum mismatch", "vendors.json: missing"]


def test_security_vendor_summary() -> None:
    gold = build_gold(inputs())
    rows = {r["vendor_group"]: r for r in gold["security_vendor_summary"].to_pylist()}
    security, others = rows["security_vendors"], rows["all_other_vendors"]
    assert (security["kev_count"], security["ransomware_known"]) == (1, 1)
    assert security["ransomware_share"] == 1.0
    # Only the NVD-merged CVE has a publication date, so only it counts toward time to KEV.
    assert (security["recent_cves"], security["median_days_to_kev"]) == (1, 1.0)
    assert security["share_within_7_days"] == 1.0
    # Unresolved CVEs count as "other": they are not known to be security vendors'.
    assert (others["kev_count"], others["recent_cves"]) == (2, 0)
    assert others["median_days_to_kev"] is None


def test_vendor_cve_counts() -> None:
    (row,) = build_gold(inputs())["vendor_cve_counts"].to_pylist()
    assert (row["slug"], row["nvd_cve_count"], row["nvd_kev_count"]) == ("fortinet", 1000, 30)
    assert row["kev_share"] == 0.03
    assert row["counted_at"] == NOW


def test_vendor_cve_counts_need_both_scopes() -> None:
    records = silver()
    records["silver.cve_counts"] = [cve_count("fortinet", "all", 1000)]
    corrected = apply_corrections(tables(records), [])
    unresolved = tables({"ops.unresolved_vendor_names": [], "silver.corrections": []})
    assert build_gold(corrected | unresolved)["vendor_cve_counts"].num_rows == 0
