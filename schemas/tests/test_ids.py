import uuid

import pytest
from ledger_schemas import PROJECT_NAMESPACE, make_id
from ledger_schemas.ids import id_type


def test_namespace_is_fixed() -> None:
    # Changing the namespace would change every published ID.
    assert (
        uuid.uuid5(uuid.NAMESPACE_URL, "https://github.com/csp4z/compromise-ledger")
        == PROJECT_NAMESPACE
    )


def test_golden_ids() -> None:
    assert (
        make_id("vulnerability", "CVE-2024-3400")
        == "vulnerability--b1795401-0f18-530d-b4e1-6a34d84d934f"
    )
    assert (
        make_id("identity", "palo-alto-networks")
        == "identity--135e7a63-a46c-5d40-983f-9c65e0dcbb4f"
    )


def test_name_is_type_and_parts_joined() -> None:
    expected = uuid.uuid5(PROJECT_NAMESPACE, "software|identity--x|pan-os")
    assert make_id("software", "identity--x", "pan-os") == f"software--{expected}"


def test_type_is_part_of_the_name() -> None:
    a = make_id("identity", "acme").split("--")[1]
    b = make_id("software", "acme").split("--")[1]
    assert a != b


@pytest.mark.parametrize(
    ("stix_type", "parts"),
    [
        ("Vulnerability", ("CVE-2024-3400",)),
        ("vulnerability", ()),
        ("vulnerability", ("",)),
        ("relationship", ("has", "a|b")),
    ],
)
def test_rejects_bad_input(stix_type: str, parts: tuple[str, ...]) -> None:
    with pytest.raises(ValueError):
        make_id(stix_type, *parts)


def test_id_type() -> None:
    assert id_type("x-ledger-correction--abc") == "x-ledger-correction"
    with pytest.raises(ValueError):
        id_type("not-an-id")
