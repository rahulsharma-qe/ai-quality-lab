"""The release gate: turns an evaluation into PASS or FAIL, with every reason written down.

Rules, strictest reading first:
- every blocking check must meet its threshold for the team AND for each client tag;
- an ERROR counts as a failure (a call that failed may hide a real problem);
- a blocking check with no applicable case fails: there is no evidence it passes (a misspelled
  column in the golden set must not switch a check off quietly);
- attack resistance (safety checks on attack cases) must meet the attacks threshold;
- each priority with a bar (e.g. high: 1.0) needs that share of its cases to pass every blocking
  check, so a good average can't hide a failing high-priority case;
- a FAIL a person has accepted (see accepted_findings) counts as a pass until it expires.
  ERRORs can't be accepted. Every acceptance is listed in the decision.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from aiquality.attacks import summarise_attacks
from aiquality.checks import CheckStatus
from aiquality.config import TeamConfig
from aiquality.evaluation import Evaluation

TOO_MANY_ACCEPTED = 0.10     # warn when more than 10% of cases rely on an acceptance


@dataclass
class ScopeResult:
    scope: str               # "team" or "client:<name>"
    check: str
    passed: int
    failed: int
    threshold: float
    blocking: bool

    @property
    def pass_rate(self) -> Optional[float]:
        total = self.passed + self.failed
        return None if total == 0 else self.passed / total

    def to_dict(self) -> dict:
        return {"scope": self.scope, "check": self.check, "passed": self.passed, "failed": self.failed,
                "pass_rate": self.pass_rate, "threshold": self.threshold, "blocking": self.blocking}


@dataclass
class GateDecision:
    passed: bool
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    scopes: list[ScopeResult] = field(default_factory=list)
    attacks: Optional[dict] = None
    priorities: list[dict] = field(default_factory=list)
    categories: list[dict] = field(default_factory=list)
    accepted_findings: list[dict] = field(default_factory=list)   # acceptances that matched a FAIL
    expired_acceptances: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"passed": self.passed, "decision": "PASS" if self.passed else "FAIL",
                "failures": self.failures, "warnings": self.warnings,
                "scopes": [s.to_dict() for s in self.scopes], "attacks": self.attacks,
                "priorities": self.priorities, "categories": self.categories,
                "accepted_findings": self.accepted_findings, "expired_acceptances": self.expired_acceptances}


class ReleaseGate:
    def __init__(self, config: TeamConfig, mandatory_checks: list[str], today: Optional[date] = None,
                 check_settings: Optional[dict] = None):
        """check_settings: the settings the run actually used, when they differ from the config
        (an unqualified judge's check is advisory whatever the config says)."""
        self.config = config
        self.checks = check_settings if check_settings is not None else config.checks
        self.mandatory_checks = set(mandatory_checks)
        self.today = today or date.today()

    def decide(self, evaluation: Evaluation) -> GateDecision:
        decision = GateDecision(passed=True)
        accepted_pairs = self._apply_acceptances(evaluation, decision)

        golden = [o for o in evaluation.outcomes if not o.is_attack]
        for name, settings in self.checks.items():
            for scope, outcomes in self._scopes(golden):
                result = self._score(name, outcomes, accepted_pairs, scope, settings)
                decision.scopes.append(result)
                if not settings.blocking:
                    continue
                if result.pass_rate is None:
                    if scope == "team":
                        why = "mandatory check" if name in self.mandatory_checks else \
                            "it blocks: give it a case, or make it non-blocking"
                        decision.failures.append(f"{name}: no applicable case, so no evidence it passes ({why})")
                elif result.pass_rate < settings.threshold:
                    decision.failures.append(f"{name}: {result.pass_rate:.0%} is below {settings.threshold:.0%} "
                                             f"({_describe_scope(scope, result)})")

        self._check_bars("priority", self.config.priority_bars, golden, accepted_pairs, decision.priorities,
                         decision)
        self._check_bars("category", self.config.category_bars, golden, accepted_pairs, decision.categories,
                         decision)
        if self.config.attacks:
            self._check_attacks(evaluation, accepted_pairs, decision)

        golden_ids = {o.case_id for o in golden}
        accepted_cases = {a["case"] for a in decision.accepted_findings if a["case"] in golden_ids}
        if golden and len(accepted_cases) / len(golden) > TOO_MANY_ACCEPTED:
            decision.warnings.append(f"{len(accepted_cases)} of {len(golden)} golden cases rely on an accepted "
                                     f"finding, more than {TOO_MANY_ACCEPTED:.0%} of cases: the check or the "
                                     "golden set may need fixing")
        decision.passed = not decision.failures
        return decision

    def _apply_acceptances(self, evaluation: Evaluation, decision: GateDecision) -> set:
        failed_pairs = {(r.case_id, r.check_name) for o in evaluation.outcomes for r in o.results
                        if r.status == CheckStatus.FAIL}
        accepted = set()
        for finding in self.config.accepted_findings:
            key = (finding.case, finding.check)
            if not finding.is_active(self.today):
                decision.expired_acceptances.append(finding.to_dict())
                if key in failed_pairs:
                    decision.warnings.append(f"acceptance for {finding.case} / {finding.check} expired on "
                                             f"{finding.expires.isoformat()}; the finding counts again")
                continue
            if key in failed_pairs:
                accepted.add(key)
                decision.accepted_findings.append(finding.to_dict())
            else:
                decision.warnings.append(f"acceptance for {finding.case} / {finding.check} matched no failure; "
                                         "remove it if the finding is fixed")
        return accepted

    def _scopes(self, outcomes):
        yield "team", outcomes
        clients = sorted({o.client for o in outcomes if o.client})
        if len(clients) > 1:
            for client in clients:
                yield f"client:{client}", [o for o in outcomes if o.client == client]

    @staticmethod
    def _score(check_name, outcomes, accepted_pairs, scope, settings) -> ScopeResult:
        passed = failed = 0
        for outcome in outcomes:
            for r in outcome.results:
                if r.check_name != check_name:
                    continue
                if r.status == CheckStatus.PASS or (r.status == CheckStatus.FAIL
                                                    and (r.case_id, r.check_name) in accepted_pairs):
                    passed += 1
                elif r.status in (CheckStatus.FAIL, CheckStatus.ERROR):
                    failed += 1
        return ScopeResult(scope, check_name, passed, failed, settings.threshold, settings.blocking)

    def _check_bars(self, kind: str, bars: dict, golden, accepted_pairs: set, results: list,
                    decision: GateDecision) -> None:
        """A bar per priority (kind "priority") or per test type (kind "category"): that share of its golden
        cases must pass every blocking check. An average over all cases can hide them failing."""
        blocking = {name for name, settings in self.checks.items() if settings.blocking}
        for value, bar in bars.items():
            cases = [o for o in golden if str(getattr(o, kind) or "").casefold() == str(value).casefold()]
            if not cases:
                decision.warnings.append(f"{kind} bar '{value}' has no golden cases with that {kind}")
                continue
            failing = [o.case_id for o in cases if self._case_failed(o, blocking, accepted_pairs)]
            rate = (len(cases) - len(failing)) / len(cases)
            results.append({kind: value, "cases": len(cases), "failed": failing, "pass_rate": rate, "bar": bar})
            if rate < bar:
                label = f"{value}-priority cases" if kind == "priority" else f"{value} cases"
                decision.failures.append(f"{label}: {len(failing)} of {len(cases)} failed "
                                         f"({', '.join(failing[:10])}), bar {bar:.0%}")

    @staticmethod
    def _case_failed(outcome, blocking_checks: set, accepted_pairs: set) -> bool:
        for r in outcome.results:
            if r.check_name not in blocking_checks:
                continue
            if r.status == CheckStatus.ERROR:
                return True
            if r.status == CheckStatus.FAIL and (r.case_id, r.check_name) not in accepted_pairs:
                return True
        return False

    def _check_attacks(self, evaluation: Evaluation, accepted_pairs: set, decision: GateDecision) -> None:
        threshold = self.config.attacks.threshold
        summary = summarise_attacks([o for o in evaluation.outcomes if o.is_attack],
                                    evaluation.safety_checks, accepted_pairs)
        decision.attacks = {**summary.to_dict(), "threshold": threshold}
        if summary.total == 0:
            decision.failures.append("attacks: no attack case ran, so no evidence the agent resists them")
        elif summary.resistance_rate < threshold:
            broken = [f"{f.family} ({f.broken} broken, {f.errors} errors)" for f in summary.families.values()
                      if f.broken or f.errors]
            decision.failures.append(f"attacks: {summary.resistance_rate:.0%} resisted, below {threshold:.0%}: "
                                     + ", ".join(broken))


def _describe_scope(scope: str, result: ScopeResult) -> str:
    """'team' -> 'all golden cases: 7 of 36 failed'; 'client:x' -> 'client x only: 2 of 12 failed'."""
    counted = f"{result.failed} of {result.passed + result.failed} failed"
    if scope == "team":
        return f"all golden cases: {counted}"
    return f"{scope.replace('client:', 'client ', 1)} only: {counted}"
