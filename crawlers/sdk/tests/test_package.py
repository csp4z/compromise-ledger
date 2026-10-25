import ledger_crawl


def test_version_matches_distribution_metadata() -> None:
    assert ledger_crawl.__version__ == "0.1.0"
