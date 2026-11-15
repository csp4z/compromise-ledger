"""The Phase 2 gate for entity resolution, on a frozen, labelled snapshot (tests/entity-resolution).

Each labelled name has the entity it should resolve to, or none. A prediction is a true
positive when it names the expected entity, a false positive when it names any other entity
(or one when none was expected), and a false negative when it names nothing but one was expected.
"""

import csv
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest
from ledger_pipelines.entities import EntityIndex, normalized, squashed
from ledger_pipelines.resolve import load_seeds, name_key
from ledger_schemas.types import NameKind

SNAPSHOT = Path(__file__).parents[2] / "tests" / "entity-resolution"
MIN_PRECISION = 0.98


@dataclass(frozen=True)
class Pair:
    kind: NameKind
    name: str
    expected: str  # "vendor:<slug>", "org:<cik>", or "" for none


def pairs() -> list[Pair]:
    with (SNAPSHOT / "pairs.csv").open(encoding="utf-8") as f:
        return [Pair(r["kind"], r["name"], r["expected"]) for r in csv.DictReader(f)]  # type: ignore[arg-type]


def index() -> EntityIndex:
    with (SNAPSHOT / "organizations.csv").open(encoding="utf-8") as f:
        orgs = [(r["sec_cik"], r["name"]) for r in csv.DictReader(f)]
    return EntityIndex(load_seeds(SNAPSHOT / "seeds"), orgs)


@dataclass(frozen=True)
class Score:
    tp: int
    fp: int
    fn: int

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else 1.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else 1.0


def score(predict: Callable[[Pair], str], labelled: list[Pair]) -> Score:
    tp = fp = fn = 0
    for pair in labelled:
        got = predict(pair)
        if got and got == pair.expected:
            tp += 1
        elif got:
            fp += 1
        elif pair.expected:
            fn += 1
    return Score(tp, fp, fn)


def resolver(pair: Pair) -> str:
    match = INDEX.resolve(pair.name, pair.kind)
    return match.target if match else ""


def alias_table_alone(pair: Pair) -> str:
    """The baseline: what ``ledger resolve`` does for KEV names, vendors only."""
    slug = SEEDS.lookup.get(name_key(pair.name))
    return f"vendor:{slug}" if slug else ""


INDEX = index()
SEEDS = load_seeds(SNAPSHOT / "seeds")
PAIRS = pairs()


def test_the_labelled_set_is_the_size_the_gate_asks_for() -> None:
    assert len(PAIRS) >= 100
    assert len({(p.kind, p.name) for p in PAIRS}) == len(PAIRS)
    # Enough negatives to make precision mean something.
    assert sum(not p.expected for p in PAIRS) >= 30


def test_gate_precision_and_recall_beat_the_alias_table() -> None:
    ours, baseline = score(resolver, PAIRS), score(alias_table_alone, PAIRS)
    misses = [p for p in PAIRS if resolver(p) != p.expected]
    assert ours.precision >= MIN_PRECISION, misses
    assert ours.recall > baseline.recall


@pytest.mark.parametrize("kind", ["cna", "sec", "third-party"])
def test_precision_holds_for_each_kind_of_name(kind: str) -> None:
    assert score(resolver, [p for p in PAIRS if p.kind == kind]).precision >= MIN_PRECISION


def test_report(capsys: pytest.CaptureFixture[str]) -> None:
    """Prints the measurement (pytest -s) for the roadmap and the gate evidence."""
    with capsys.disabled():
        for kind in ("cna", "sec", "third-party", None):
            subset = [p for p in PAIRS if kind is None or p.kind == kind]
            ours, base = score(resolver, subset), score(alias_table_alone, subset)
            print(
                f"\n{kind or 'all':12} n={len(subset):3} "
                f"precision {ours.precision:.3f} (alias table {base.precision:.3f}) "
                f"recall {ours.recall:.3f} (alias table {base.recall:.3f}) "
                f"tp={ours.tp} fp={ours.fp} fn={ours.fn}"
            )


def test_normalization() -> None:
    assert normalized("F5, INC.") == "f5"
    assert normalized("AT&T INC.") == "at and t"
    assert normalized("8X8 INC /DE/") == "8x8"
    assert normalized("Dassault Systèmes") == "dassault systemes"
    assert squashed("Check Point Software Ltd.") == "checkpointsoftware"
    assert normalized("The Company") == "the company"  # never normalized to nothing


def test_hard_negatives_stay_unmatched() -> None:
    assert INDEX.resolve("META MATERIALS INC.", "sec") is None
    assert INDEX.resolve("SONIC AUTOMOTIVE INC", "sec") is None
    assert INDEX.resolve("GitHub_M", "cna") is None
    assert INDEX.resolve("rapid7", "cna") is None
    # Two vendors in one name, as KEV writes it: never one of them.
    assert INDEX.resolve("D-Link and TRENDnet", "cna") is None


def test_rules_agree_with_the_alias_table_on_names_they_were_not_tuned_on() -> None:
    """Every KEV vendor name the alias table resolves resolves to the same vendor here, and
    the KEV names it leaves unresolved on purpose stay unresolved."""
    for key, slug in SEEDS.lookup.items():
        match = INDEX.resolve(key, "cna")
        assert match is not None and match.target == f"vendor:{slug}", key
    for name in ("Npm package", "D-Link and TRENDnet"):
        assert INDEX.resolve(name, "cna") is None


def test_matches_name_their_rule() -> None:
    palo = INDEX.resolve("palo_alto", "cna")
    assert palo and (palo.target, palo.rule, palo.confidence) == (
        "vendor:palo-alto-networks",
        "prefix",
        75,
    )
    msft = INDEX.resolve("MICROSOFT CORP", "sec")
    assert msft and (msft.target, msft.rule) == ("vendor:microsoft", "normalized")
    evertec = INDEX.resolve("Evertec, Inc.", "third-party")
    assert evertec and evertec.target == "org:0001559865"
