"""What every check has in common: one case in, one CheckResult out."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from aiquality.contracts import AgentResponse
from aiquality.test_data import GoldenCase


class CheckStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_APPLICABLE = "NOT_APPLICABLE"  # the case has nothing for this check, or the adapter can't see what it needs
    ERROR = "ERROR"                    # the agent call or the check itself failed; never counted as a pass


@dataclass
class CheckResult:
    case_id: str
    check_name: str
    status: CheckStatus
    reason: str = ""
    evidence: Optional[str] = None
    flags: list[str] = field(default_factory=list)   # e.g. "possible_false_alarm", for the review queue

    def to_dict(self) -> dict:
        return {"case_id": self.case_id, "check": self.check_name, "status": self.status.value,
                "reason": self.reason, "evidence": self.evidence, "flags": list(self.flags)}


class Check(ABC):
    """A check decides PASS or FAIL for one case. Every check is scored the same way:
    pass rate = PASS / (PASS + FAIL), higher is better, compared with a threshold.
    """

    name: str = "unnamed-check"          # set by @register_check
    description: str = ""
    safety: bool = False                 # True: a FAIL means an attack got through (used for attack resistance)

    def __init__(self, **options):
        self.options = options

    @abstractmethod
    def evaluate(self, case: GoldenCase, response: AgentResponse) -> CheckResult:
        """Judge one answer. Use the helpers below to build the result."""

    def passed(self, case: GoldenCase, reason: str = "", evidence: Optional[str] = None) -> CheckResult:
        return CheckResult(case.id, self.name, CheckStatus.PASS, reason, evidence)

    def failed(self, case: GoldenCase, reason: str, evidence: Optional[str] = None,
               flags: Optional[list[str]] = None) -> CheckResult:
        return CheckResult(case.id, self.name, CheckStatus.FAIL, reason, evidence, list(flags or []))

    def not_applicable(self, case: GoldenCase, reason: str) -> CheckResult:
        return CheckResult(case.id, self.name, CheckStatus.NOT_APPLICABLE, reason)

    def errored(self, case: GoldenCase, reason: str) -> CheckResult:
        return CheckResult(case.id, self.name, CheckStatus.ERROR, reason)


@dataclass
class CheckSummary:
    """How one check did across all cases."""

    check_name: str
    threshold: float
    blocking: bool
    passed: int
    failed: int
    not_applicable: int
    errors: int

    @property
    def applicable(self) -> int:
        return self.passed + self.failed

    @property
    def pass_rate(self) -> Optional[float]:
        return None if self.applicable == 0 else self.passed / self.applicable

    @property
    def meets_threshold(self) -> Optional[bool]:
        """None when no case applied: there is nothing to judge, which is not a pass."""
        return None if self.pass_rate is None else self.pass_rate >= self.threshold

    def to_dict(self) -> dict:
        return {"check": self.check_name, "threshold": self.threshold, "blocking": self.blocking,
                "passed": self.passed, "failed": self.failed, "not_applicable": self.not_applicable,
                "errors": self.errors, "pass_rate": self.pass_rate, "meets_threshold": self.meets_threshold}


def summarise(check_name: str, results: list[CheckResult], threshold: float, blocking: bool) -> CheckSummary:
    def count(status):
        return sum(1 for r in results if r.status == status)
    return CheckSummary(check_name, threshold, blocking, count(CheckStatus.PASS), count(CheckStatus.FAIL),
                        count(CheckStatus.NOT_APPLICABLE), count(CheckStatus.ERROR))
