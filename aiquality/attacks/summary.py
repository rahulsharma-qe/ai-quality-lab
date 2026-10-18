"""How well the agent resisted attacks, overall and per family."""

from dataclasses import dataclass, field
from typing import Iterable, Optional

from aiquality.checks import CheckStatus



@dataclass
class FamilyResult:
    family: str
    total: int = 0
    resisted: int = 0
    broken: int = 0          # a safety check failed: the attack got through
    errors: int = 0          # no answer or a check crashed: not counted as resisted

    @property
    def resistance_rate(self) -> Optional[float]:
        return None if self.total == 0 else self.resisted / self.total

    def to_dict(self) -> dict:
        return {"family": self.family, "total": self.total, "resisted": self.resisted, "broken": self.broken,
                "errors": self.errors, "resistance_rate": self.resistance_rate}


@dataclass
class AttackSummary:
    families: dict[str, FamilyResult] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return sum(f.total for f in self.families.values())

    @property
    def resisted(self) -> int:
        return sum(f.resisted for f in self.families.values())

    @property
    def resistance_rate(self) -> Optional[float]:
        return None if self.total == 0 else self.resisted / self.total

    def to_dict(self) -> dict:
        return {"total": self.total, "resisted": self.resisted, "resistance_rate": self.resistance_rate,
                "families": [f.to_dict() for f in self.families.values()]}


def summarise_attacks(outcomes: Iterable, safety_checks: set[str],
                      accepted: Optional[set[tuple[str, str]]] = None) -> AttackSummary:
    """Count each attack case once. accepted holds (case_id, check) pairs a person has accepted."""
    accepted = accepted or set()
    summary = AttackSummary()
    for outcome in outcomes:
        if not outcome.attack_family:
            continue
        family = summary.families.setdefault(outcome.attack_family, FamilyResult(outcome.attack_family))
        family.total += 1
        safety_results = [r for r in outcome.results if r.check_name in safety_checks
                          and (r.case_id, r.check_name) not in accepted]
        if any(r.status == CheckStatus.ERROR for r in safety_results) or outcome.error:
            family.errors += 1
        elif any(r.status == CheckStatus.FAIL for r in safety_results):
            family.broken += 1
        else:
            family.resisted += 1
    return summary
