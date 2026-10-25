"""Builds gold tables by running the DuckDB SQL files in ``pipelines/sql/gold/``.

Files run in name order (``10_...``, ``20_...``). Each is one SELECT whose result becomes
``gold.<name without the numeric prefix>``, and it may read ``silver.*``, ``ops.*``, and any
gold table built before it.
"""

import re
from collections.abc import Mapping
from pathlib import Path

import duckdb
import pyarrow as pa

GOLD_SQL_DIR = Path(__file__).resolve().parents[2] / "sql" / "gold"
_FILE_RE = re.compile(r"^\d+_([a-z][a-z0-9_]*)\.sql$")
_INPUT_RE = re.compile(r"^[a-z]+\.[a-z][a-z0-9_]*$")

# Gold builds share the 8 GB development machine with everything else.
MEMORY_LIMIT = "1GB"


def gold_files(sql_dir: Path = GOLD_SQL_DIR) -> list[tuple[str, Path]]:
    files: list[tuple[str, Path]] = []
    for path in sorted(sql_dir.glob("*.sql")):
        match = _FILE_RE.match(path.name)
        if not match:
            raise ValueError(f"gold SQL file names look like '10_name.sql': {path.name}")
        files.append((match.group(1), path))
    names = [name for name, _ in files]
    if len(names) != len(set(names)):
        raise ValueError(f"duplicate gold table names in {sql_dir}")
    return files


def build_gold(inputs: Mapping[str, pa.Table], sql_dir: Path = GOLD_SQL_DIR) -> dict[str, pa.Table]:
    """Run every gold SQL file over ``inputs`` (keyed ``schema.table``)."""
    con = duckdb.connect()
    try:
        con.execute(f"SET memory_limit = '{MEMORY_LIMIT}'")
        # Otherwise timestamps come back in the machine's local zone, and output varies by host.
        con.execute("SET TimeZone = 'UTC'")
        for schema in {name.split(".")[0] for name in inputs} | {"gold"}:
            con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        for name, table in inputs.items():
            if not _INPUT_RE.match(name):
                raise ValueError(f"not a schema.table name: {name!r}")
            alias = f"_input_{name.replace('.', '_')}"
            con.register(alias, table)
            # Identifiers are validated above, never user input.
            con.execute(f"CREATE VIEW {name} AS SELECT * FROM {alias}")  # noqa: S608
        results: dict[str, pa.Table] = {}
        for name, path in gold_files(sql_dir):
            try:
                result = con.execute(path.read_text(encoding="utf-8")).to_arrow_table()
            except duckdb.Error as exc:
                raise ValueError(f"{path.name}: {exc}") from exc
            results[name] = result
            con.register(f"_gold_{name}", result)
            con.execute(f"CREATE VIEW gold.{name} AS SELECT * FROM _gold_{name}")  # noqa: S608
        return results
    finally:
        con.close()
