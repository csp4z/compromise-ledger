"""Normalizing organization names, and grouping breach notices from the same organization
(ADR 0008).

Breach notices carry free-text names with no shared ID. The same organization files as
``Patelco Credit Union`` and ``Patelco Credit Union (Amended Notice)``, with a supplier in
brackets, or under a trade name. The **core name** removes those additions, and two names with
the same core name are treated as the same organization. Names that only share words (one
housing authority and another, a law firm and the client it files for) are not.

This is deliberately a rule, not a statistical model: see ADR 0008 for the comparison with
probabilistic linkage on these names.
"""

import hashlib
import re
import unicodedata

# Legal forms and filler that don't distinguish one company from another.
LEGAL = frozenset(
    "inc incorporated corp corporation co company ltd limited llc plc sa se ag gmbh nv bv "  # noqa: SIM905
    "holdings holding the de".split()
)

_BRACKETS = re.compile(r"\([^)]*\)|\[[^\]]*\]|\"[^\"]*\"|“[^”]*”")
_TRADE_NAME = re.compile(
    r"\b(d\s*/?\s*b\s*/?\s*a|doing business as|formerly known as|f\s*/?\s*k\s*/?\s*a)\b.*$",
    re.IGNORECASE,
)
_NOTICE_LABEL = re.compile(
    r"\b(amended|supplemental|updated|second|third)\s+notice\b", re.IGNORECASE
)


def normalized(name: str) -> str:
    """ASCII, lower case, ``&`` as ``and``, punctuation as spaces, legal suffixes dropped."""
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    text = text.replace("&", " and ")
    # Dotted abbreviations are one word: "L.L.C." is "llc", "U.S." is "us".
    text = re.sub(r"\b((?:[a-z]\.){2,})", lambda m: m.group(1).replace(".", ""), text)
    words = re.sub(r"[^a-z0-9]+", " ", text).split()
    kept = [w for w in words if w not in LEGAL]
    return " ".join(kept or words)


def squashed(name: str) -> str:
    return normalized(name).replace(" ", "")


def core_name(name: str) -> str:
    """The organization's own name: no bracketed asides, trade names, or notice labels, with
    punctuation and legal suffixes removed (``Humana, Inc. (Welltok, Inc.)`` -> ``humana``)."""
    text = _NOTICE_LABEL.sub(" ", _BRACKETS.sub(" ", name))
    return normalized(_TRADE_NAME.sub(" ", text)) or normalized(name)


def group_id(name: str) -> str:
    """The same for every name with the same core name, ignoring spaces. A digest, so it can
    sit beside published counts without naming anyone."""
    return hashlib.sha256(core_name(name).replace(" ", "").encode()).hexdigest()
