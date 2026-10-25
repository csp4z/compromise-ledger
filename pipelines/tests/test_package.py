import ledger_pipelines


def test_version_matches_distribution_metadata() -> None:
    assert ledger_pipelines.__version__ == "0.1.0"
