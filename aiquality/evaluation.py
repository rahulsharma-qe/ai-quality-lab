"""Score every case with every configured check, then summarise per check."""

from dataclasses import dataclass, field
from typing import Optional

from aiquality.checks import CheckResult, CheckStatus, CheckSummary, create_check, summarise
from aiquality.config import CheckSettings
from aiquality.runner import CaseRun


@dataclass
class CaseOutcome:
    case_id: str
    category: str
    client: Optional[str]
    question: str
    answer_text: Optional[str]
    error: Optional[str]
    results: list[CheckResult] = field(default_factory=list)

    @property
    def failed_checks(self) -> list[CheckResult]:
        return [r for r in self.results if r.status in (CheckStatus.FAIL, CheckStatus.ERROR)]


@dataclass
class Evaluation:
    outcomes: list[CaseOutcome]
    summaries: dict[str, CheckSummary]


def evaluate_runs(case_runs: list[CaseRun], check_settings: dict[str, CheckSettings],
                  default_client: Optional[str] = None) -> Evaluation:
    checks = {name: create_check(name, **settings.options) for name, settings in check_settings.items()}
    outcomes = []
    for run in case_runs:
        outcome = CaseOutcome(case_id=run.case.id, category=run.case.category,
                              client=run.case.client or default_client, question=run.case.input,
                              answer_text=run.response.answer_text if run.response else None,
                              error=run.error)
        for name, check in checks.items():
            outcome.results.append(_score_one(check, run))
        outcomes.append(outcome)

    summaries = {}
    for name, settings in check_settings.items():
        results = [r for o in outcomes for r in o.results if r.check_name == name]
        summaries[name] = summarise(name, results, settings.threshold, settings.blocking)
    return Evaluation(outcomes=outcomes, summaries=summaries)


def _score_one(check, run: CaseRun) -> CheckResult:
    if not run.succeeded:
        return check.errored(run.case, f"no answer to check: {run.error}")
    try:
        return check.evaluate(run.case, run.response)
    except Exception as error:  # a buggy check must show up, not pass silently
        return check.errored(run.case, f"check raised {type(error).__name__}: {error}")
