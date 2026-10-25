"""Deterministic IDs for domain objects (ADR 0004)."""

import re
import uuid

# uuid5(NAMESPACE_URL, "https://github.com/csp4z/compromise-ledger"). Hard-coded so that a repo
# move or rename can never change it: every published ID depends on this value.
PROJECT_NAMESPACE = uuid.UUID("1b14795c-17e7-51a0-809f-109c69d879d5")

KEY_SEPARATOR = "|"

_TYPE_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
# `<type>--<UUIDv5>`; the version nibble is fixed at 5 and the variant at RFC 4122.
ID_PATTERN = (
    r"^[a-z][a-z0-9-]*--[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


def make_id(stix_type: str, *key_parts: str) -> str:
    """Return ``<stix_type>--<uuid5>`` for an object's natural key.

    The UUID name is the type and key parts joined by ``|``, so the same key under two types
    yields different IDs. Parts are used verbatim: callers pass canonical forms (slugs, upper-case
    CVE IDs), and the models enforce those forms with field patterns.
    """
    if not _TYPE_RE.fullmatch(stix_type):
        raise ValueError(f"invalid STIX type: {stix_type!r}")
    if not key_parts:
        raise ValueError("at least one natural-key part is required")
    for part in key_parts:
        if not part or KEY_SEPARATOR in part:
            raise ValueError(f"natural-key part must be non-empty and not contain '|': {part!r}")
    name = KEY_SEPARATOR.join((stix_type, *key_parts))
    return f"{stix_type}--{uuid.uuid5(PROJECT_NAMESPACE, name)}"


def id_type(object_id: str) -> str:
    """Return the STIX type prefix of an ID (``vulnerability--…`` → ``vulnerability``)."""
    stix_type, sep, _ = object_id.partition("--")
    if not sep:
        raise ValueError(f"not a STIX ID: {object_id!r}")
    return stix_type
