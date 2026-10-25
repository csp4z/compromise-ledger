from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from ledger_api.app import MAX_LIMIT, create_app

SAMPLE = Path(__file__).parents[2] / "tests" / "sample-exports"


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(SAMPLE))


def test_health_and_manifest(client: TestClient) -> None:
    health = client.get("/health")
    assert health.status_code == 200 and health.json()["status"] == "ok"
    manifest = client.get("/v1/datasets").json()
    assert {s["id"] for s in manifest["sources"]} >= {"cisa-kev", "nvd"}
    assert health.headers["cache-control"] == "public, max-age=300"


def test_no_export_yet_is_503(tmp_path: Path) -> None:
    empty = TestClient(create_app(tmp_path))
    assert empty.get("/health").status_code == 503
    assert empty.get("/v1/kev").status_code == 503


def test_summary_and_monthly(client: TestClient) -> None:
    groups = {g["vendor_group"]: g for g in client.get("/v1/summary").json()}
    assert set(groups) == {"security_vendors", "all_other_vendors"}
    assert 0 <= groups["security_vendors"]["ransomware_share"] <= 1
    months = client.get("/v1/stats/monthly").json()
    assert months == sorted(months, key=lambda m: m["month"])


def test_kev_filters_and_paging(client: TestClient) -> None:
    everything = client.get("/v1/kev", params={"limit": MAX_LIMIT}).json()
    assert everything["total"] == len(everything["items"]) == 40
    page = client.get("/v1/kev", params={"limit": 5, "offset": 5}).json()
    assert page["items"] == everything["items"][5:10] and page["total"] == 40

    pan = client.get("/v1/kev", params={"vendor": "palo-alto-networks"}).json()
    assert pan["total"] > 0 and {i["vendor_slug"] for i in pan["items"]} == {"palo-alto-networks"}
    security = client.get("/v1/kev", params={"security_vendor": "true", "limit": MAX_LIMIT}).json()
    assert all(i["is_security_vendor"] for i in security["items"])
    known = client.get("/v1/kev", params={"ransomware": "known", "limit": MAX_LIMIT}).json()
    assert all(i["kev_ransomware_use"] == "known" for i in known["items"])
    recent = client.get("/v1/kev", params={"added_since": "2026-01-01", "limit": MAX_LIMIT}).json()
    assert all(i["kev_date_added"] >= "2026-01-01" for i in recent["items"])


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": MAX_LIMIT + 1},
        {"vendor": "Bad Slug"},
        {"ransomware": "maybe"},
        {"added_since": "yesterday"},
    ],
)
def test_rejects_bad_parameters(client: TestClient, params: dict[str, object]) -> None:
    assert client.get("/v1/kev", params=params).status_code == 422


def test_vulnerability_detail(client: TestClient) -> None:
    cve = client.get("/v1/kev", params={"vendor": "fortinet", "limit": 1}).json()["items"][0]
    detail = client.get(f"/v1/vulnerabilities/{cve['cve_id']}").json()
    assert detail["cve_id"] == cve["cve_id"] and detail["in_kev"] is True
    assert "nvd" in detail["sources"] and detail["products"]
    assert client.get("/v1/vulnerabilities/CVE-1999-0001").status_code == 404
    assert client.get("/v1/vulnerabilities/not-a-cve").status_code == 422


def test_vendors(client: TestClient) -> None:
    security = client.get("/v1/vendors", params={"security_vendor": "true"}).json()
    assert security["total"] > 0 and all(v["is_security_vendor"] for v in security["items"])
    counts = [v["kev_count"] for v in security["items"]]
    assert counts == sorted(counts, reverse=True)
    fortinet = client.get("/v1/vendors/fortinet").json()
    assert fortinet["name"] == "Fortinet" and fortinet["kev"]
    assert client.get("/v1/vendors/no-such-vendor").status_code == 404
    assert client.get("/v1/vendors/Not_A_Slug").status_code == 422


def test_unresolved_names(client: TestClient) -> None:
    names = {n["vendor_name"] for n in client.get("/v1/unresolved-vendor-names").json()}
    assert "Npm package" in names


def test_injection_attempts_are_inert(client: TestClient) -> None:
    attempt = "'; DROP VIEW vendors; --"
    assert client.get("/v1/kev", params={"vendor": attempt}).status_code == 422
    assert client.get("/v1/vendors").status_code == 200


def test_openapi_is_published(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()
    assert {"/v1/kev", "/v1/vendors/{slug}", "/v1/summary"} <= set(spec["paths"])
    assert "not endorsed or certified by the NVD" in spec["info"]["description"]
