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
    BreachNotice,
    Correction,
    CveCount,
    EpssScore,
    Incident,
    Organization,
    Product,
    Provenance,
    Relationship,
    ThirdPartyIncident,
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
        "silver.third_party_incidents": [],
        "silver.epss_scores": [],
        "silver.breach_notices": [],
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


def test_third_party_marks_reach_the_whole_incident() -> None:
    org = Organization(sec_cik="0000000001", name="Example Corp", provenance=prov("sec-8k"))
    first = filing(org, date(2026, 1, 5), "8-K", "8.01", 1)
    update = filing(org, date(2026, 1, 20), "8-K", "8.01", 2)
    other = filing(org, date(2026, 9, 1), "8-K", "8.01", 3)
    records = silver()
    records["silver.organizations"] = [org]
    records["silver.incidents"] = [first, update, other]
    records["silver.third_party_incidents"] = [
        ThirdPartyIncident(
            sec_accession=update.sec_accession,
            third_party="Example Processor",
            note="The vendor's incident exposed customer data.",
            provenance=prov("third-party-review", 90),
        )
    ]
    corrected = apply_corrections(tables(records), [])
    extra = tables({"ops.unresolved_vendor_names": [], "silver.corrections": []})
    gold = build_gold(corrected | extra)
    filings = {f["sec_accession"]: f for f in gold["incident_filings"].to_pylist()}
    assert filings[update.sec_accession]["via_third_party"] is True
    assert filings[first.sec_accession]["via_third_party"] is False
    incidents = {i["incident_id"]: i for i in gold["incidents"].to_pylist()}
    marked, unmarked = incidents[first.id], incidents[other.id]
    assert (marked["via_third_party"], marked["third_party"]) == (True, "Example Processor")
    assert (unmarked["via_third_party"], unmarked["third_party"]) == (False, None)


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


# Aggregates name their `sources`; the corrections log records maintainer decisions, not facts.
AGGREGATES = {
    "security_vendor_kev_monthly",
    "security_vendor_summary",
    "unresolved_vendor_names",
    "vendor_signals",
    "security_vendor_signals",
    "breach_notice_yearly",
    "breach_notice_groups",
}
NOT_FACTS = {"corrections_log"}
# What every row of a row-level table must carry, and the column names that hold it (plural
# where a row merges several source documents).
PROVENANCE = {
    "source": ("source_url", "source_urls"),
    "crawl time": ("crawled_at", "counted_at"),
    "confidence": ("confidence",),
    "license": ("license", "licenses"),
}


def test_every_published_fact_carries_provenance() -> None:
    org = Organization(sec_cik="0000000001", name="Example Corp", provenance=prov("sec-8k"))
    records = silver()
    records["silver.organizations"] = [org]
    records["silver.incidents"] = [filing(org, date(2026, 1, 5), "8-K", "8.01", 1)]
    corrected = apply_corrections(tables(records), [])
    extra = tables({"ops.unresolved_vendor_names": [], "silver.corrections": []})
    gold = build_gold(corrected | extra)
    assert set(gold) == {name for name, _ in gold_files()}
    for name, table in gold.items():
        if name in NOT_FACTS:
            continue
        if name in AGGREGATES:
            assert "sources" in table.column_names, f"gold.{name} doesn't name its sources"
            continue
        assert table.num_rows > 0, f"the fixture has no rows for gold.{name}"
        for what, columns in PROVENANCE.items():
            present = [c for c in columns if c in table.column_names]
            assert present, f"gold.{name} has no {what} column ({' or '.join(columns)})"
            values = table.column(present[0]).to_pylist()
            assert None not in values, f"gold.{name}.{present[0]} has empty values"


def signal_inputs() -> dict[str, pa.Table]:
    """The base fixture plus what the CVE List, NVD's own score, and EPSS add."""
    records = silver()
    cve_list = prov("cve-list", 96)
    records["silver.vulnerabilities"] = [
        *records["silver.vulnerabilities"],
        # Fortinet's CVE: the CNA scored it 9.6, NVD 9.8; automatable with total impact.
        Vulnerability(
            cve_id="CVE-2024-21762",
            published=datetime(2024, 2, 9, 8, tzinfo=UTC),
            cvss_v3_base_score=9.6,
            cvss_v3_scorer="cna",
            cve_assigner="fortinet",
            cve_reserved=datetime(2024, 1, 2, tzinfo=UTC),
            ssvc_exploitation="active",
            ssvc_automatable="yes",
            ssvc_technical_impact="total",
            provenance=cve_list,
        ),
        Vulnerability(
            cve_id="CVE-2024-21762",
            cvss_v3_base_score=9.8,
            cvss_v3_scorer="nvd",
            provenance=prov("nvd", 97),
        ),
        # Microsoft's: not automatable, and only a third party's score.
        Vulnerability(
            cve_id="CVE-2024-0001",
            cvss_v3_base_score=7.8,
            cvss_v3_scorer="other",
            cve_assigner="microsoft",
            ssvc_automatable="no",
            ssvc_technical_impact="total",
            provenance=cve_list,
        ),
    ]
    records["silver.epss_scores"] = [
        # Listed 2024-02-20, scored the day before. CVE-2024-21762 (listed 2024-02-09) has a
        # score only for another day, so it counts as unscored before its listing.
        epss("CVE-2024-0001", date(2024, 2, 19), 0.02),
        epss("CVE-2024-21762", date(2024, 2, 20), 0.9),
    ]
    corrected = apply_corrections(tables(records), [])
    return corrected | tables({"ops.unresolved_vendor_names": [], "silver.corrections": []})


def epss(cve: str, day: date, score: float) -> EpssScore:
    return EpssScore(
        vulnerability_id=make_id("vulnerability", cve),
        cve_id=cve,
        score_date=day,
        epss=score,
        percentile=score,
        provenance=prov("epss").model_copy(
            update={"source_url": "https://api.first.org/epss", "license": "LicenseRef-EPSS"}
        ),
    )


def test_vulnerabilities_carry_cna_ssvc_and_epss() -> None:
    rows = {r["cve_id"]: r for r in build_gold(signal_inputs())["vulnerabilities"].to_pylist()}
    forti = rows["CVE-2024-21762"]
    assert forti["cve_assigner"] == "fortinet"
    assert forti["days_reserved_before_published"] == 37
    assert (forti["nvd_cvss_v3_base_score"], forti["cna_cvss_v3_base_score"]) == (9.8, 9.6)
    assert forti["cvss_v3_base_score"] == 9.8  # the headline score is still the most confident
    assert (forti["ssvc_automatable"], forti["ssvc_technical_impact"]) == ("yes", "total")
    assert forti["epss_before_kev"] is None  # its only score is for another day
    assert forti["sources"] == "cisa-kev;cve-list;nvd"
    ms = rows["CVE-2024-0001"]
    assert (ms["epss_before_kev"], ms["epss_score_date"]) == (0.02, date(2024, 2, 19))
    # A third party's score is neither NVD's nor the CNA's.
    assert ms["nvd_cvss_v3_base_score"] is None and ms["cna_cvss_v3_base_score"] is None
    # The EPSS document joins the row's provenance.
    assert ms["sources"] == "cisa-kev;cve-list;epss"
    assert "https://api.first.org/epss" in ms["source_urls"].split(";")
    assert ms["licenses"] == "CC0-1.0;LicenseRef-EPSS"
    # Nothing known about the third CVE beyond KEV.
    assert rows["CVE-2024-0002"]["ssvc_automatable"] is None


def test_vendor_signals_count_each_signal() -> None:
    gold = build_gold(signal_inputs())
    vendors = {r["slug"]: r for r in gold["vendor_signals"].to_pylist()}
    forti = vendors["fortinet"]
    assert (forti["kev_count"], forti["ssvc_assessed"], forti["automatable_total"]) == (1, 1, 1)
    assert (forti["cvss_both_scored"], forti["cna_scored_lower"]) == (1, 1)
    assert (forti["epss_asked"], forti["epss_scored"], forti["epss_unscored"]) == (1, 0, 1)
    assert forti["median_days_reserved_before_published"] == 37
    ms = vendors["microsoft"]
    assert (ms["automatable"], ms["total_impact"], ms["automatable_total"]) == (0, 1, 0)
    assert (ms["epss_scored"], ms["epss_under_10pct"], ms["median_epss_before_kev"]) == (1, 1, 0.02)
    groups = {r["vendor_group"]: r for r in gold["security_vendor_signals"].to_pylist()}
    security, others = groups["security_vendors"], groups["all_other_vendors"]
    assert (security["kev_count"], others["kev_count"]) == (1, 2)
    assert security["automatable_total_share"] == 1.0
    assert security["cna_scored_lower_share"] == 1.0
    # The unresolved CVE was listed after the last day EPSS was asked about: not counted.
    assert (others["epss_asked"], others["epss_scored"], others["epss_unscored"]) == (1, 1, 0)
    assert others["epss_under_10pct_share"] == 1.0


def test_signals_are_empty_not_wrong_before_the_new_sources_run() -> None:
    gold = build_gold(inputs())
    (forti,) = [r for r in gold["vendor_signals"].to_pylist() if r["slug"] == "fortinet"]
    assert (forti["ssvc_assessed"], forti["epss_asked"], forti["epss_unscored"]) == (0, 0, 0)
    for group in gold["security_vendor_signals"].to_pylist():
        assert group["automatable_total_share"] is None
        assert group["epss_unscored_share"] is None


def notice(
    notice_id: int,
    submitted: date,
    *,
    aware: date | None = None,
    started: date | None = None,
    cause: str = "cyberattack",
    attack_type: str | None = "ransomware",
    industry: str = "Health",
    residents: int | None = 1000,
) -> BreachNotice:
    return BreachNotice(
        jurisdiction="US-WA",
        notice_id=str(notice_id),
        organization_name=f"Example {notice_id}",
        status="confirmed",
        submitted_on=submitted,
        aware_on=aware,
        breach_started_on=started,
        cause=cause,  # type: ignore[arg-type]
        attack_type=attack_type,  # type: ignore[arg-type]
        industry=industry,
        residents_affected=residents,
        provenance=prov("wa-breach-notices", 90),
    )


def breach_gold(corrections: Sequence[Correction] = ()) -> dict[str, pa.Table]:
    records = silver()
    records["silver.breach_notices"] = [
        notice(1, date(2024, 3, 1), aware=date(2024, 2, 20), started=date(2024, 2, 10)),
        notice(2, date(2024, 6, 1), aware=date(2024, 3, 3), started=date(2024, 3, 1)),
        notice(3, date(2024, 7, 1), cause="theft-or-mistake", attack_type=None, industry="Finance"),
        # Dates out of order: counted as a notice, left out of the day counts.
        notice(4, date(2025, 1, 10), aware=date(2025, 1, 1), started=date(2025, 1, 5)),
    ]
    corrected = apply_corrections(tables(records), list(corrections))
    extra = tables({"ops.unresolved_vendor_names": [], "silver.corrections": list(corrections)})
    return build_gold(corrected | extra)


def test_breach_notices_per_year() -> None:
    years = {r["year"]: r for r in breach_gold()["breach_notice_yearly"].to_pylist()}
    y2024 = years[2024]
    assert (y2024["notices"], y2024["cyberattacks"], y2024["ransomware"]) == (3, 2, 2)
    assert y2024["ransomware_share"] == 0.6667
    assert (y2024["discover_measured"], y2024["median_days_to_discover"]) == (2, 6.0)
    assert (y2024["notify_measured"], y2024["median_days_to_notify"]) == (2, 50.0)
    assert y2024["share_notified_after_30_days"] == 0.5
    assert y2024["residents_affected"] == 3000
    y2025 = years[2025]
    assert (y2025["notices"], y2025["discover_measured"], y2025["notify_measured"]) == (1, 0, 1)
    assert y2025["median_days_to_discover"] is None


def test_breach_notice_groups_and_no_names_in_gold() -> None:
    gold = breach_gold()
    groups = {(r["dimension"], r["label"]): r for r in gold["breach_notice_groups"].to_pylist()}
    assert groups[("industry", "Health")]["notices"] == 3
    assert groups[("cause", "theft-or-mistake")]["ransomware"] == 0
    # Attack types are counted for cyberattacks only.
    assert groups[("attack_type", "ransomware")]["notices"] == 3
    assert ("attack_type", "not-stated") not in groups
    # Only aggregates are published from this source: no gold table carries a notifier's name.
    for name, table in gold.items():
        for column in table.column_names:
            values = table.column(column).to_pylist()
            assert not any(isinstance(v, str) and v.startswith("Example ") for v in values), (
                f"gold.{name}.{column} names a notifying organization"
            )


def test_suppressing_a_breach_notice_removes_it_from_the_counts() -> None:
    target = make_id("incident", "breach-notice", "us-wa", "3")
    years = {
        r["year"]: r
        for r in breach_gold([correction("suppress", target)])["breach_notice_yearly"].to_pylist()
    }
    assert years[2024]["notices"] == 2
