from pathlib import Path

from ledger_schemas.jsonschema import DEFAULT_OUT_DIR, MODELS, render


def test_committed_json_schema_is_current() -> None:
    # If this fails, run `make schemas` and commit the result.
    for name, model in MODELS.items():
        path = DEFAULT_OUT_DIR / f"{name}.schema.json"
        assert path.read_text(encoding="utf-8") == render(model), f"{path} is stale"


def test_no_stray_schema_files() -> None:
    expected = {f"{name}.schema.json" for name in MODELS}
    assert {p.name for p in Path(DEFAULT_OUT_DIR).glob("*.json")} == expected
