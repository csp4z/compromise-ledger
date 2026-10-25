import ledger_api


def test_version_matches_distribution_metadata() -> None:
    assert ledger_api.__version__ == "0.1.0"
