"""Entity resolution beyond the alias table: maps names from other sources to curated vendors and
SEC-filing organizations (roadmap Phase 2, step 4).

Names come from three places: the CNA that assigned a CVE (``palo_alto``), the companies that
file 8-Ks (``MICROSOFT CORP``), and the third parties named in those filings (``Evertec, Inc.``).
Each is matched by the first rule that finds exactly one entity:

1. ``alias``: the alias table, exact after Unicode and case normalization (what
   ``ledger resolve`` already does for KEV names).
2. ``cpe``: the vendor's curated NVD CPE name (``paloaltonetworks``).
3. ``normalized``: punctuation and legal suffixes removed (``F5, INC.`` -> ``f5``).
4. ``squashed``: the same, with spaces removed (``trendmicro`` -> ``Trend Micro``).
5. ``prefix``: CNA names only. One name starts the other, sharing at least five characters
   (``palo_alto`` -> ``Palo Alto Networks``, ``Samsung Mobile`` -> ``Samsung``). Never for a
   name that joins two parties with "and" (``D-Link and TRENDnet``).
6. ``core``: breach-notice names only. Equal once bracketed asides, trade names, and notice
   labels are removed (``Amgen, Inc. (The Lash Group, LLC)`` -> ``AMGEN INC``); see
   ``names.py`` and ADR 0008.

A rule that finds more than one entity stops the search with no match: a false merge
misattributes an incident, so precision comes first. Accuracy is measured against a labelled,
frozen snapshot in ``tests/entity-resolution/`` (``test_entity_resolution.py``).
"""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from ledger_schemas import EntityLink, Provenance, make_id
from ledger_schemas.types import EntityType, NameKind, ResolutionRule

from ledger_pipelines.names import core_name, group_id, normalized, squashed
from ledger_pipelines.resolve import Seeds, name_key

TargetType = EntityType

# Confidence of a match by rule (0-100), carried into the published links.
CONFIDENCE: dict[ResolutionRule, int] = {
    "alias": 95,
    "cpe": 90,
    "normalized": 90,
    "squashed": 85,
    "prefix": 75,
    "core": 80,
}
MIN_PREFIX = 5
# Which entities each kind of name may resolve to, in order of preference.
TARGETS: dict[NameKind, tuple[TargetType, ...]] = {
    "cna": ("vendor",),
    "sec": ("vendor",),
    "third-party": ("vendor", "org"),
    "breach-notice": ("vendor", "org"),
}


@dataclass(frozen=True, slots=True)
class Match:
    target_type: TargetType
    target_key: str  # a vendor slug, or an SEC CIK
    rule: ResolutionRule
    confidence: int

    @property
    def target(self) -> str:
        return f"{self.target_type}:{self.target_key}"


class EntityIndex:
    """The curated vendors (names, aliases, CPE names) and SEC organizations, by matching key."""

    def __init__(self, seeds: Seeds, organizations: Iterable[tuple[str, str]] = ()) -> None:
        self._alias: dict[TargetType, dict[str, set[str]]] = {"vendor": {}, "org": {}}
        self._cpe: dict[str, set[str]] = defaultdict(set)
        self._normalized: dict[TargetType, dict[str, set[str]]] = {"vendor": {}, "org": {}}
        self._squashed: dict[TargetType, dict[str, set[str]]] = {"vendor": {}, "org": {}}
        self._core: dict[TargetType, dict[str, set[str]]] = {"vendor": {}, "org": {}}
        names: dict[TargetType, list[tuple[str, str]]] = {"vendor": [], "org": []}
        for key, slug in seeds.lookup.items():
            self._alias["vendor"].setdefault(key, set()).add(slug)
        for vendor in seeds.vendors:
            names["vendor"].append((vendor.name, vendor.slug))
            if vendor.cpe_vendor:
                self._cpe[vendor.cpe_vendor].add(vendor.slug)
        for cik, name in organizations:
            names["org"].append((name, cik))
            self._alias["org"].setdefault(name_key(name), set()).add(cik)
        for target_type, entries in names.items():
            for name, key in entries:
                self._normalized[target_type].setdefault(normalized(name), set()).add(key)
                self._squashed[target_type].setdefault(squashed(name), set()).add(key)
                core = core_name(name).replace(" ", "")
                self._core[target_type].setdefault(core, set()).add(key)

    def resolve(self, name: str, kind: NameKind) -> Match | None:
        for target_type in TARGETS[kind]:
            match = self._resolve(name, kind, target_type)
            if match is not None:
                return match
        return None

    def _resolve(self, name: str, kind: NameKind, target_type: TargetType) -> Match | None:
        rules: list[tuple[ResolutionRule, set[str]]] = [
            ("alias", self._alias[target_type].get(name_key(name), set())),
        ]
        if target_type == "vendor":
            rules.append(("cpe", self._cpe.get(name.strip().lower(), set())))
        rules.append(("normalized", self._normalized[target_type].get(normalized(name), set())))
        rules.append(("squashed", self._squashed[target_type].get(squashed(name), set())))
        if kind == "cna" and " and " not in f" {normalized(name)} ":
            rules.append(("prefix", self._prefix(squashed(name), target_type)))
        if kind == "breach-notice":
            core = core_name(name).replace(" ", "")
            rules.append(("core", self._core[target_type].get(core, set())))
        for rule, found in rules:
            if len(found) == 1:
                return Match(target_type, next(iter(found)), rule, CONFIDENCE[rule])
            if len(found) > 1:
                return None  # ambiguous: never guess between two entities
        return None

    def _prefix(self, key: str, target_type: TargetType) -> set[str]:
        if len(key) < MIN_PREFIX:
            return set()
        found: set[str] = set()
        for other, keys in self._squashed[target_type].items():
            shorter = min(len(other), len(key))
            if shorter >= MIN_PREFIX and (other.startswith(key) or key.startswith(other)):
                found |= keys
        return found


def target_id(match: Match) -> str:
    """The STIX ID of the matched vendor or organization (as ``Vendor`` and ``Organization``)."""
    if match.target_type == "vendor":
        return make_id("identity", match.target_key)
    return make_id("identity", "sec-cik", match.target_key)


def link_names(
    index: EntityIndex, names: Iterable[tuple[NameKind, str]], provenance: Provenance
) -> list[EntityLink]:
    """One link per distinct name, matched or not. Confidence is the rule's, or 0 for no match."""
    links: dict[tuple[NameKind, str], EntityLink] = {}
    for kind, name in sorted(set(names)):
        match = index.resolve(name, kind)
        links[(kind, name)] = EntityLink(
            name_kind=kind,
            name=name,
            target_type=match.target_type if match else None,
            target_id=target_id(match) if match else None,
            target_key=match.target_key if match else None,
            rule=match.rule if match else None,
            group_id=group_id(name) if kind == "breach-notice" else None,
            provenance=provenance.model_copy(
                update={"confidence": match.confidence if match else 0}
            ),
        )
    return list(links.values())
