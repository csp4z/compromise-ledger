"""Read access to the gold export files (the API reads gold only)."""

import json
import os
from pathlib import Path
from typing import Any

import duckdb

TABLES = frozenset(
    {
        "vulnerabilities",
        "kev_vendor_products",
        "vendors",
        "security_vendor_summary",
        "security_vendor_kev_monthly",
        "unresolved_vendor_names",
        "vendor_cve_counts",
        "incidents",
        "vendor_signals",
        "security_vendor_signals",
        "breach_notice_yearly",
        "breach_notice_groups",
    }
)


def default_exports_dir() -> Path:
    if "CL_EXPORTS_DIR" in os.environ:
        return Path(os.environ["CL_EXPORTS_DIR"]).resolve()
    return (Path(os.environ.get("CL_DATA_DIR", ".lake")) / "exports").resolve()


class GoldNotAvailableError(RuntimeError):
    """The export doesn't hold what a request needs: nothing is published yet, or the export
    is older than this API and lacks a table or column."""


class Gold:
    """Queries the Parquet exports with DuckDB, one short-lived connection per call.

    Exports are replaced file by file with atomic renames and the manifest last, so each query
    sees whole files, and a new daily export is picked up without a restart. An export written
    before a table or column existed still serves everything it has: only a request that needs
    the missing part is refused, until the next export.
    """

    def __init__(self, exports_dir: Path) -> None:
        self.exports_dir = exports_dir

    def manifest(self) -> dict[str, Any]:
        path = self.exports_dir / "datasets.json"
        if not path.exists():
            raise GoldNotAvailableError(f"no datasets.json in {self.exports_dir}")
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return data

    def query(self, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
        """Run ``sql`` with each table available by name. Values go in ``params``, never SQL."""
        con = duckdb.connect()
        try:
            con.execute("SET TimeZone = 'UTC'")
            if not (self.exports_dir / "datasets.json").exists():
                raise GoldNotAvailableError(f"no datasets.json in {self.exports_dir}")
            for table in TABLES:
                path = self.exports_dir / f"{table}.parquet"
                if not path.exists():
                    continue
                # Table names come from TABLES and the path from configuration, never a request;
                # DuckDB can't bind a parameter here, so the path is quoted by hand.
                quoted = str(path).replace("'", "''")
                con.execute(f"CREATE VIEW {table} AS SELECT * FROM read_parquet('{quoted}')")  # noqa: S608
            try:
                cursor = con.execute(sql, params or [])
            except (duckdb.CatalogException, duckdb.BinderException) as exc:
                raise GoldNotAvailableError(f"the export lacks a table or column: {exc}") from exc
            columns = [d[0] for d in cursor.description or []]
            return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
        finally:
            con.close()

    def count(self, sql: str, params: list[Any] | None = None) -> int:
        (row,) = self.query(f"SELECT count(*) AS n FROM ({sql})", params)  # noqa: S608
        return int(row["n"])


def filters(**conditions: tuple[str, Any] | None) -> tuple[str, list[Any]]:
    """Build ``WHERE`` from ``name=("sql with ?", value)`` pairs, skipping unset values."""
    clauses: list[str] = []
    params: list[Any] = []
    for condition in conditions.values():
        if condition is not None and condition[1] is not None:
            clauses.append(condition[0])
            params.append(condition[1])
    return (" WHERE " + " AND ".join(clauses)) if clauses else "", params
