import ledger_schemas


def test_version_matches_distribution_metadata() -> None:
    assert ledger_schemas.__version__ == "0.1.0"
