"""What every judge has in common: one case and one answer in, one PASS or FAIL verdict out.

A judge grades meaning, where a check can only match words. Because a judge can be wrong too,
every judge has a version that changes whenever the judge changes (a new model, new
instructions), and trust is earned per version: see aiquality/judges/validation.py.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from aiquality.test_data import GoldenCase


@dataclass
class JudgeVerdict:
    passed: bool
    reason: str

    def to_dict(self) -> dict:
        return {"verdict": "PASS" if self.passed else "FAIL", "reason": self.reason}


class Judge(ABC):
    name: str = "unnamed-judge"     # set by @register_judge unless the class sets its own

    @property
    @abstractmethod
    def version(self) -> str:
        """Changes whenever the judge's behaviour can change. Validation results belong to one version."""

    @abstractmethod
    def verdict(self, case: GoldenCase, answer_text: str) -> JudgeVerdict:
        """Grade one answer to one case."""
