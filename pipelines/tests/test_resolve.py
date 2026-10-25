from datetime import UTC, datetime
from pathlib import Path

import pytest
from ledger_pipelines.resolve import (
    RESOLVER_ID,
    SeedError,
    load_seeds,
    name_key,
    product_slug,
    resolve,
)
from ledger_schemas import ProductMention, Provenance, make_id

REPO_SEEDS = Path(__file__).parents[2] / "data" / "seeds"
BUILT = datetime(2026, 10, 24, tzinfo=UTC)
VENDORS = """slug,name,is_security_vendor,source,note
palo-alto-networks,Palo Alto Networks,true,https://www.paloaltonetworks.com/,Network security
microsoft,Microsoft,false,,
"""
ALIASES = """alias,vendor_slug,note
ChakraCore,microsoft,Microsoft's JavaScript engine
"""


def write_seeds(tmp_path: Path, vendors: str = VENDORS, aliases: str = ALIASES) -> Path:
    (tmp_path / "vendors.csv").write_text(vendors, encoding="utf-8")
    (tmp_path / "vendor_aliases.csv").write_text(aliases, encoding="utf-8")
    return tmp_path


def mention(cve: str, vendor: str, product: str, parser_id: str = "cisa-kev") -> ProductMention:
    provenance = Provenance(
        source_url="https://www.cisa.gov/feed.json",
        raw_document_id="a" * 64,
        crawled_at=BUILT,
        parser_id=parser_id,
        parser_version="0.1.0",
        confidence=95,
        license="CC0-1.0",
    )
    return ProductMention(
        vulnerability_id=make_id("vulnerability", cve),
        vendor_name=vendor,
        product_name=product,
        provenance=provenance,
    )


def test_name_key_and_product_slug() -> None:
    assert name_key(f"  palo ALTO{chr(0xA0)}Networks ") == name_key("Palo Alto Networks")
    assert product_slug("Commerce and Magento") == "commerce-and-magento"
    assert product_slug("DELMIA Apriso (Dassault Systèmes)") == "delmia-apriso-dassault-systemes"
    assert product_slug("中文").startswith("p-")


def test_resolves_names_and_aliases(tmp_path: Path) -> None:
    seeds = load_seeds(write_seeds(tmp_path))
    result = resolve(
        [
            mention("CVE-2024-3400", "palo alto networks", "PAN-OS"),
            mention("CVE-2024-3401", "Palo Alto Networks", "PAN-OS"),
            mention("CVE-2019-0001", "ChakraCore", "ChakraCore scripting engine"),
            mention("CVE-2024-0002", "D-Link and TRENDnet", "Multiple Devices"),
            mention("CVE-2024-0003", "D-Link and TRENDnet", "Multiple Devices", "other"),
        ],
        seeds,
        built_at=BUILT,
    )
    assert {v.slug for v in result.vendors} == {"palo-alto-networks", "microsoft"}
    pan = next(v for v in result.vendors if v.slug == "palo-alto-networks")
    assert pan.is_security_vendor and pan.provenance.raw_document_id == seeds.digest
    assert len(result.products) == 2  # PAN-OS once, ChakraCore engine under Microsoft
    pan_os = next(p for p in result.products if p.slug == "pan-os")
    assert pan_os.vendor_id == pan.id
    assert pan_os.provenance.parser_id == RESOLVER_ID
    assert pan_os.provenance.source_url == "https://www.cisa.gov/feed.json"
    assert len(result.relationships) == 3
    assert {r.source_ref for r in result.relationships} <= {p.id for p in result.products}
    (unresolved,) = result.unresolved
    assert unresolved.vendor_name == "D-Link and TRENDnet"
    assert (unresolved.mentions, unresolved.parser_ids) == (2, ["cisa-kev", "other"])


def test_resolution_is_deterministic(tmp_path: Path) -> None:
    seeds = load_seeds(write_seeds(tmp_path))
    mentions = [
        mention("CVE-2024-3400", "Palo Alto Networks", "PAN-OS"),
        mention("CVE-2024-3401", "Palo Alto Networks", "Pan-OS"),
        mention("CVE-2024-3402", "Palo Alto Networks", "Pan-OS"),
    ]
    a = resolve(mentions, seeds, built_at=BUILT)
    b = resolve(list(reversed(mentions)), seeds, built_at=BUILT)
    assert a == b
    assert [p.name for p in a.products] == ["Pan-OS"]  # most common spelling wins


@pytest.mark.parametrize(
    ("vendors", "aliases", "message"),
    [
        (VENDORS.replace("true,https://www.paloaltonetworks.com/", "true,"), ALIASES, "https"),
        (VENDORS + "microsoft,Microsoft Corp,false,,\n", ALIASES, "duplicate slug"),
        (VENDORS + "msft,microsoft,false,,\n", ALIASES, "already used"),
        (VENDORS, ALIASES + "Windows,nope,\n", "unknown vendor_slug"),
        (VENDORS, ALIASES + "MICROSOFT,microsoft,\n", "already maps"),
        (VENDORS.replace("true,https", "yes,https"), ALIASES, "true or false"),
        (
            VENDORS.replace("note\n", "\n", 1).replace(
                "slug,name,is_security_vendor,source,", "slug,name,is_security_vendor,source"
            ),
            ALIASES,
            "expected columns",
        ),
    ],
)
def test_rejects_bad_seeds(tmp_path: Path, vendors: str, aliases: str, message: str) -> None:
    with pytest.raises(SeedError, match=message):
        load_seeds(write_seeds(tmp_path, vendors, aliases))


def test_committed_seeds_are_valid() -> None:
    seeds = load_seeds(REPO_SEEDS)
    security = [v for v in seeds.vendors if v.is_security_vendor]
    assert security, "no security vendors in the seed list"
    assert all(v.note for v in security), "each security vendor needs a note"
    for v in seeds.vendors:
        assert product_slug(v.slug) == v.slug, f"{v.slug!r} is not a canonical slug"
