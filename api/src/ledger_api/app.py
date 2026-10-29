"""The read-only HTTP API over the gold exports."""

from collections.abc import Awaitable, Callable
from datetime import date
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi import Path as PathParam
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ledger_api import __version__
from ledger_api.gold import Gold, GoldNotAvailableError, default_exports_dir, filters
from ledger_api.models import (
    GroupSummary,
    Health,
    Incident,
    KevEntry,
    Month,
    Page,
    UnresolvedVendorName,
    Vendor,
    VendorCveCount,
    VendorDetail,
    Vulnerability,
    VulnerabilityDetail,
)

DESCRIPTION = """\
Read-only access to the Compromise Ledger dataset: security vendors' own products in CISA's
Known Exploited Vulnerabilities catalog, enriched with NVD, and cybersecurity incidents that
companies disclose to the SEC.

Data is CC BY 4.0; upstream sources keep their own terms (see `/v1/datasets`). This product
uses data from the NVD API but is not endorsed or certified by the NVD.
"""
CACHE_SECONDS = 300
MAX_LIMIT = 1000

Limit = Annotated[int, Query(ge=1, le=MAX_LIMIT)]
Offset = Annotated[int, Query(ge=0)]
SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
Slug = Annotated[str, Query(pattern=SLUG_PATTERN, max_length=128)]
SlugPath = Annotated[str, PathParam(pattern=SLUG_PATTERN, max_length=128)]
CvePath = Annotated[str, PathParam(pattern=r"^CVE-\d{4}-\d{4,}$")]

KEV_COLUMNS = ", ".join(KevEntry.model_fields)
VULN_COLUMNS = ", ".join(Vulnerability.model_fields)
VENDOR_COLUMNS = ", ".join(Vendor.model_fields)
INCIDENT_COLUMNS = ", ".join(Incident.model_fields)


def create_app(exports_dir: Path | None = None) -> FastAPI:
    gold = Gold(exports_dir or default_exports_dir())
    app = FastAPI(
        title="Compromise Ledger API",
        version=__version__,
        description=DESCRIPTION,
        license_info={
            "name": "Data: CC BY 4.0",
            "url": "https://creativecommons.org/licenses/by/4.0/",
        },
    )
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"])

    @app.middleware("http")
    async def cache_headers(  # pyright: ignore[reportUnusedFunction]
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        if response.status_code == 200:
            response.headers["Cache-Control"] = f"public, max-age={CACHE_SECONDS}"
        return response

    @app.exception_handler(GoldNotAvailableError)
    async def no_gold(  # pyright: ignore[reportUnusedFunction]
        request: Request, exc: GoldNotAvailableError
    ) -> JSONResponse:
        return JSONResponse({"detail": "the dataset has not been published yet"}, status_code=503)

    def page(
        columns: str, table: str, where: str, params: list[Any], order: str, limit: int, offset: int
    ) -> dict[str, Any]:
        base = f"SELECT {columns} FROM {table}{where}"  # noqa: S608 - constants and bound params
        rows = gold.query(f"{base} ORDER BY {order} LIMIT ? OFFSET ?", [*params, limit, offset])
        return {"total": gold.count(base, params), "limit": limit, "offset": offset, "items": rows}

    @app.get("/health", tags=["meta"])
    def health() -> Health:
        manifest = gold.manifest()
        return Health(
            status="ok",
            generated_at=manifest["generated_at"],
            schema_version=manifest["schema_version"],
        )

    @app.get("/v1/datasets", tags=["meta"], summary="Export manifest (datasets.json)")
    def datasets() -> dict[str, Any]:
        """Files, row counts, SHA-256 checksums, Iceberg snapshots, licenses, and sources."""
        return gold.manifest()

    @app.get("/v1/summary", tags=["stats"])
    def summary() -> list[GroupSummary]:
        """Security vendors vs everyone else: KEV count, ransomware use, time to KEV."""
        return [
            GroupSummary.model_validate(r)
            for r in gold.query(
                "SELECT * EXCLUDE (sources) FROM security_vendor_summary ORDER BY vendor_group DESC"
            )
        ]

    @app.get("/v1/stats/monthly", tags=["stats"])
    def monthly() -> list[Month]:
        """KEV additions per month, and how many affect security vendors' own products."""
        return [
            Month.model_validate(r)
            for r in gold.query(
                "SELECT * EXCLUDE (sources) FROM security_vendor_kev_monthly ORDER BY month"
            )
        ]

    @app.get("/v1/stats/cve-share", tags=["stats"])
    def cve_share() -> list[VendorCveCount]:
        """Share of each curated vendor's NVD CVEs that reached KEV, highest first."""
        return [
            VendorCveCount.model_validate(r)
            for r in gold.query(
                "SELECT * EXCLUDE (vendor_id, sources) FROM vendor_cve_counts "
                "ORDER BY kev_share DESC NULLS LAST, slug"
            )
        ]

    @app.get("/v1/kev", tags=["kev"])
    def kev(
        limit: Limit = 100,
        offset: Offset = 0,
        vendor: Slug | None = None,
        security_vendor: bool | None = None,
        ransomware: Annotated[str | None, Query(pattern="^(known|unknown)$")] = None,
        added_since: date | None = None,
        added_until: date | None = None,
    ) -> Page[KevEntry]:
        """KEV entries by affected product, newest first."""
        where, params = filters(
            vendor=("vendor_slug = ?", vendor),
            security=("is_security_vendor = ?", security_vendor),
            ransomware=("kev_ransomware_use = ?", ransomware),
            since=("kev_date_added >= ?", added_since),
            until=("kev_date_added <= ?", added_until),
        )
        order = "kev_date_added DESC, cve_id, vendor_slug, product_name"
        return Page[KevEntry].model_validate(
            page(KEV_COLUMNS, "kev_vendor_products", where, params, order, limit, offset)
        )

    @app.get("/v1/incidents", tags=["incidents"])
    def incidents(
        limit: Limit = 100,
        offset: Offset = 0,
        material: bool | None = None,
        disclosed_since: date | None = None,
        disclosed_until: date | None = None,
    ) -> Page[Incident]:
        """Incidents disclosed in SEC 8-K filings, newest first."""
        where, params = filters(
            material=("material = ?", material),
            since=("first_disclosed_on >= ?", disclosed_since),
            until=("first_disclosed_on <= ?", disclosed_until),
        )
        order = "first_disclosed_on DESC, organization_name, incident_id"
        return Page[Incident].model_validate(
            page(INCIDENT_COLUMNS, "incidents", where, params, order, limit, offset)
        )

    @app.get("/v1/vulnerabilities/{cve_id}", tags=["kev"])
    def vulnerability(cve_id: CvePath) -> VulnerabilityDetail:
        rows = gold.query(f"SELECT {VULN_COLUMNS} FROM vulnerabilities WHERE cve_id = ?", [cve_id])  # noqa: S608
        if not rows:
            raise HTTPException(404, f"{cve_id} is not in the dataset")
        products = gold.query(
            f"SELECT {KEV_COLUMNS} FROM kev_vendor_products WHERE cve_id = ? "  # noqa: S608
            "ORDER BY vendor_slug, product_name",
            [cve_id],
        )
        return VulnerabilityDetail.model_validate({**rows[0], "products": products})

    @app.get("/v1/vendors", tags=["vendors"])
    def vendors(
        limit: Limit = 100, offset: Offset = 0, security_vendor: bool | None = None
    ) -> Page[Vendor]:
        """Curated vendors with their KEV totals, most KEV entries first."""
        where, params = filters(security=("is_security_vendor = ?", security_vendor))
        return Page[Vendor].model_validate(
            page(VENDOR_COLUMNS, "vendors", where, params, "kev_count DESC, slug", limit, offset)
        )

    @app.get("/v1/vendors/{slug}", tags=["vendors"])
    def vendor(slug: SlugPath) -> VendorDetail:
        rows = gold.query(f"SELECT {VENDOR_COLUMNS} FROM vendors WHERE slug = ?", [slug])  # noqa: S608
        if not rows:
            raise HTTPException(404, f"no vendor {slug!r}")
        entries = gold.query(
            f"SELECT {KEV_COLUMNS} FROM kev_vendor_products WHERE vendor_slug = ? "  # noqa: S608
            "ORDER BY kev_date_added DESC, cve_id, product_name",
            [slug],
        )
        return VendorDetail.model_validate({**rows[0], "kev": entries})

    @app.get("/v1/unresolved-vendor-names", tags=["vendors"])
    def unresolved() -> list[UnresolvedVendorName]:
        """Source vendor names that match no curated vendor, so the gaps are visible."""
        return [
            UnresolvedVendorName.model_validate(r)
            for r in gold.query(
                "SELECT * FROM unresolved_vendor_names ORDER BY mentions DESC, vendor_name"
            )
        ]

    return app
