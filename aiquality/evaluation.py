"""Score every case with every configured check, then summarise per check."""

from dataclasses import dataclass, field
from typing import Optional

from aiquality.attacks import ATTACK_CATEGORY, AttackSummary, summarise_attacks
from aiquality.checks import CheckResult, CheckSummary, create_check, summarise
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
    attack_family: Optional[str] = None
    priority: str = "medium"
    tool_calls: Optional[list] = None              # as the adapter saw them; None when it can't see tools
    retrieved_documents: Optional[list] = None

    @property
    def is_attack(self) -> bool:
        return self.category == ATTACK_CATEGORY


@dataclass
class Evaluation:
    """outcomes holds every case; summaries cover the golden cases only, and attacks the attack
    cases, so attack prompts never change the golden-set pass rates."""

    outcomes: list[CaseOutcome]
    summaries: dict[str, CheckSummary]
    attacks: Optional[AttackSummary] = None
    safety_checks: set = field(default_factory=set)


def evaluate_runs(case_runs: list[CaseRun], check_settings: dict[str, CheckSettings],
                  default_client: Optional[str] = None) -> Evaluation:
    checks = {name: create_check(name, **settings.options) for name, settings in check_settings.items()}
    outcomes = []
    groups: dict[tuple, list] = {}          # (check, group) -> [(outcome, place in its results, run)]
    for run in case_runs:
        outcome = CaseOutcome(case_id=run.case.id, category=run.case.category,
                              client=run.case.client or default_client, question=run.case.input,
                              answer_text=run.response.answer_text if run.response else None,
                              error=run.error, attack_family=run.case.extra.get("attack_family"),
                              priority=run.case.priority,
                              tool_calls=_tool_calls(run.response),
                              retrieved_documents=run.response.retrieved_documents if run.response else None)
        for name, check in checks.items():
            group = check.group_of(run.case)
            if group is None:
                outcome.results.append(_score_one(check, run))
            else:
                groups.setdefault((name, group), []).append((outcome, len(outcome.results), run))
                outcome.results.append(None)            # judged with its group, below
        outcomes.append(outcome)
    for (name, _), members in groups.items():
        for (outcome, place, run), result in zip(members, _score_group(checks[name], [m[2] for m in members])):
            outcome.results[place] = result

    summaries = {}
    for name, settings in check_settings.items():
        results = [r for o in outcomes if not o.is_attack for r in o.results if r.check_name == name]
        summaries[name] = summarise(name, results, settings.threshold, settings.blocking)

    safety_checks = {name for name, check in checks.items() if check.safety}
    attack_outcomes = [o for o in outcomes if o.is_attack]
    attacks = summarise_attacks(attack_outcomes, safety_checks) if attack_outcomes else None
    return Evaluation(outcomes=outcomes, summaries=summaries, attacks=attacks, safety_checks=safety_checks)


def _score_one(check, run: CaseRun) -> CheckResult:
    if not run.succeeded:
        return check.errored(run.case, f"no answer to check: {run.error}")
    try:
        return check.evaluate(run.case, run.response)
    except Exception as error:  # a buggy check must show up, not pass silently
        return check.errored(run.case, f"check raised {type(error).__name__}: {error}")


def _score_group(check, runs: list[CaseRun]) -> list[CheckResult]:
    try:
        results = check.evaluate_group(runs)
        return [results[run.case.id] for run in runs]
    except Exception as error:  # a buggy check must show up, not pass silently
        return [check.errored(run.case, f"check raised {type(error).__name__}: {error}") for run in runs]


def _tool_calls(response) -> Optional[list]:
    if response is None or response.tool_calls is None:
        return None
    return [call.to_dict() for call in response.tool_calls]
