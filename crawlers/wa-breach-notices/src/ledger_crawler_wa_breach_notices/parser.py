"""Parses the Washington breach-notification dataset into ``BreachNotice`` records.

Kept: the notifier's name, the four dates, cause, attack type, industry, state, and the number
of residents. The office's derived columns (day counts and ranges) are recomputed in gold from
the dates. Nothing describes the people affected beyond their number.

The name is withheld when it carries a professional-practice marker (PLLC, P.S., DDS, "Law
Office of"), because such a notifier is often one named person. The rule is deliberately broad:
it also withholds some group practices.
"""

import json
import re
from collections.abc import Iterator
from datetime import date, datetime
from importlib.metadata import version
from typing import Any

from ledger_crawl import ParseContext, ParserMeta
from ledger_schemas import BreachNotice
from ledger_schemas.types import AttackType, BreachCause
from pydantic import BaseModel, ConfigDict, Field

from ledger_crawler_wa_breach_notices.crawler import LIMIT

# The organization's own statutory notice to a regulator, as the regulator recorded it.
WA_CONFIDENCE = 90
CAUSES: dict[str, BreachCause] = {
    "Cyberattack": "cyberattack",
    "Unauthorized Access": "unauthorized-access",
    "Theft or Mistake": "theft-or-mistake",
}
ATTACK_TYPES: dict[str, AttackType] = {
    "Ransomware": "ransomware",
    "Malware": "malware",
    "Phishing": "phishing",
    "Skimmers": "skimmer",
    "Other": "other",
    "Unclear/unknown": "unknown",
}
STATE = re.compile(r"^[A-Z]{2}$")
PRACTICE = re.compile(
    r"(?<![A-Za-z])(PLLC|P\.?L\.?L\.?C\.?|P\.S\.|P\.C\.|P\.A\.|CPA|DDS|D\.D\.S\.|DMD|M\.D\.|"
    r"Law Offices? of|Dr\.)(?![A-Za-z])",
    re.IGNORECASE,
)


class Row(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    submitted: datetime = Field(alias="datesubmitted")
    aware: datetime | None = Field(default=None, alias="dateaware")
    start: datetime | None = Field(default=None, alias="datestart")
    end: datetime | None = Field(default=None, alias="dateend")
    cause: str = Field(alias="databreachcause")
    attack_type: str | None = Field(default=None, alias="cyberattacktype")
    industry: str | None = Field(default=None, alias="industrytype")
    state: str | None = Field(default=None, alias="entitystate")
    residents: int | None = Field(default=None, alias="washingtoniansaffected")


def day(value: datetime | None) -> date | None:
    """The dataset's dates are calendar days written as midnight, with no zone."""
    return value.date() if value else None


def lookup[T](vocabulary: dict[str, T], value: str | None, what: str) -> T | None:
    if value is None:
        return None
    try:
        return vocabulary[value.strip()]
    except KeyError:
        raise ValueError(f"unexpected {what} {value!r}") from None


def publishable_name(name: str) -> str | None:
    cleaned = " ".join(name.split())
    return None if PRACTICE.search(cleaned) else cleaned or None


def state_code(value: str | None) -> str | None:
    """Two-letter codes only; the few spelled-out names are dropped rather than guessed."""
    code = (value or "").strip()
    return code if STATE.match(code) else None


class WaBreachNoticeParser:
    meta = ParserMeta(
        id="wa-breach-notices",
        version=version("ledger-crawler-wa-breach-notices"),
        source_id="wa-breach-notices",
        confidence=WA_CONFIDENCE,
    )

    def parse(self, body: bytes, ctx: ParseContext) -> Iterator[BreachNotice]:
        rows: list[dict[str, Any]] = json.loads(body)
        if len(rows) >= LIMIT:
            raise ValueError(f"{len(rows)} rows fill the page; the dataset was cut off")
        provenance = ctx.provenance()
        for item in rows:
            row = Row.model_validate(item)
            yield BreachNotice(
                jurisdiction="US-WA",
                notice_id=row.id,
                organization_name=publishable_name(row.name),
                # The organization's own notice to a regulator confirms it (DATA_POLICY.md).
                status="confirmed",
                submitted_on=row.submitted.date(),
                aware_on=day(row.aware),
                breach_started_on=day(row.start),
                breach_ended_on=day(row.end),
                cause=lookup(CAUSES, row.cause, "cause"),
                attack_type=lookup(ATTACK_TYPES, row.attack_type, "attack type"),
                industry=" ".join(row.industry.split()) if row.industry else None,
                organization_state=state_code(row.state),
                residents_affected=row.residents,
                provenance=provenance,
            )
