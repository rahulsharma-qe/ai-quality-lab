"""Ask the agent every case, one at a time, and keep what came back (or what went wrong)."""

from dataclasses import dataclass
from typing import Iterable, Optional

from aiquality.contracts import AgentResponse, AgentUnderTest
from aiquality.errors import SetupError
from aiquality.test_data import GoldenCase


@dataclass
class CaseRun:
    case: GoldenCase
    response: Optional[AgentResponse] = None
    error: Optional[str] = None

    @property
    def succeeded(self) -> bool:
        return self.response is not None


class Runner:
    """Runs cases sequentially. A failed call is recorded for that case and the run goes on.

    If more than max_error_rate of the calls fail, the run stops with a SetupError:
    with that many failures there is no fair quality result to report.
    """

    def __init__(self, agent: AgentUnderTest, max_error_rate: float = 0.2):
        self.agent = agent
        self.max_error_rate = max_error_rate

    def run(self, cases: Iterable[GoldenCase]) -> list[CaseRun]:
        runs = [self._run_one(case) for case in cases]
        failed = [r for r in runs if not r.succeeded]
        if runs and len(failed) / len(runs) > self.max_error_rate:
            examples = "; ".join(f"{r.case.id}: {r.error}" for r in failed[:3])
            raise SetupError(f"{len(failed)} of {len(runs)} agent calls failed "
                             f"(allowed: {self.max_error_rate:.0%}). First errors: {examples}")
        return runs

    def _run_one(self, case: GoldenCase) -> CaseRun:
        try:
            response = self.agent.answer(case.input, case.conversation_history or None)
        except Exception as error:  # one broken call must not hide the other results
            return CaseRun(case=case, error=f"{type(error).__name__}: {error}")
        return CaseRun(case=case, response=response)
