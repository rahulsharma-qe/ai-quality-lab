"""Compare two runs: which cases got fixed, which newly fail, which still fail.

An average can rise while a case that used to pass breaks. So a change to the agent (a new
prompt, a new model, a retrieval setting) is judged case by case against a saved baseline:

    before = pick_run("history/before.jsonl")            # the last run in the file
    after  = pick_run("aiquality-runs/run_records.jsonl")
    comparison = compare_runs(before, after)
    print(render_comparison(comparison))
    comparison.newly_failing                              # the regressions, if any

A case fails when any blocking check FAILED or ERRORED on it, the same reading the release
gate uses. Diagnostic checks (blocking: false) still show in the per-check table.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from aiquality.errors import SetupError
from aiquality.reporting.report_data import percent, version_text
from aiquality.reporting.run_record import RUN_RECORDS_FILE, RunRecord, load_run_records

FAILING = ("FAIL", "ERROR")


@dataclass
class CheckChange:
    check: str
    threshold: float
    blocking: bool
    before_rate: Optional[float]
    after_rate: Optional[float]

    @property
    def points(self) -> Optional[int]:
        """Change in percentage points, e.g. +8; None when either run has no rate."""
        if self.before_rate is None or self.after_rate is None:
            return None
        return round((self.after_rate - self.before_rate) * 100)


@dataclass
class CaseChange:
    case_id: str
    category: str
    priority: str
    failed_before: list[str]          # blocking checks that failed on this case before
    failed_after: list[str]


@dataclass
class RunComparison:
    before: RunRecord
    after: RunRecord
    checks: list[CheckChange]
    fixed: list[CaseChange] = field(default_factory=list)          # failed before, passes now
    newly_failing: list[CaseChange] = field(default_factory=list)  # passed before, fails now
    still_failing: list[CaseChange] = field(default_factory=list)
    only_before: list[str] = field(default_factory=list)           # cases one run doesn't have
    only_after: list[str] = field(default_factory=list)
    new_cases_failing: list[CaseChange] = field(default_factory=list)  # among only_after
    warnings: list[str] = field(default_factory=list)

    @property
    def has_new_failures(self) -> bool:
        return bool(self.newly_failing)


def pick_run(path, run_id: Optional[str] = None) -> RunRecord:
    """A run from a run_records.jsonl file (or a folder holding one): the last one, or the one with run_id."""
    path = Path(path)
    if path.is_dir():
        path = path / RUN_RECORDS_FILE
    if not path.is_file():
        raise SetupError(f"no run records at {path}")
    try:
        records = load_run_records(path)
    except (json.JSONDecodeError, TypeError) as error:
        raise SetupError(f"could not read run records in {path}: {error}")
    if not records:
        raise SetupError(f"{path} holds no runs")
    if run_id is None:
        return records[-1]
    for record in records:
        if record.run_id == run_id:
            return record
    raise SetupError(f"no run {run_id} in {path}. Runs there: {', '.join(r.run_id for r in records)}")


def compare_runs(before: RunRecord, after: RunRecord) -> RunComparison:
    blocking = {s["check"] for s in before.summaries + after.summaries if s.get("blocking", True)}
    comparison = RunComparison(before=before, after=after, checks=_check_changes(before, after))
    if before.team != after.team:
        comparison.warnings.append(f"different teams: {before.team} vs {after.team}")
    if before.golden_set_version != after.golden_set_version:
        comparison.warnings.append(f"golden set changed ({before.golden_set_version} → "
                                   f"{after.golden_set_version}); pass rates cover different cases")

    failed_before = _failing_checks(before, blocking)
    failed_after = _failing_checks(after, blocking)
    outcomes_after = {o["case_id"]: o for o in after.outcomes}
    for case_id, outcome in outcomes_after.items():
        if case_id not in failed_before:
            comparison.only_after.append(case_id)
            if failed_after[case_id]:
                comparison.new_cases_failing.append(_case_change(outcome, [], failed_after[case_id]))
            continue
        change = _case_change(outcome, failed_before[case_id], failed_after[case_id])
        if change.failed_before and not change.failed_after:
            comparison.fixed.append(change)
        elif change.failed_after and not change.failed_before:
            comparison.newly_failing.append(change)
        elif change.failed_after:
            comparison.still_failing.append(change)
    comparison.only_before = [case_id for case_id in failed_before if case_id not in outcomes_after]
    return comparison


def render_comparison(comparison: RunComparison) -> str:
    """Plain text for the terminal and CI logs."""
    before, after = comparison.before, comparison.after
    lines = [f"aiquality compare · team {after.team}",
             f"before: run {before.run_id} · {before.agent_version} · golden set {version_text(before.golden_set_version)}",
             f"after:  run {after.run_id} · {after.agent_version} · golden set {version_text(after.golden_set_version)}"]
    lines += [f"warning: {w}" for w in comparison.warnings]
    labels = [c.check + ("" if c.blocking else " (doesn't block)") for c in comparison.checks]
    width = max([len(label) for label in labels] + [len("attacks resisted")]) + 2
    lines += ["", f"{'check':<{width}}{'before':>8}{'after':>8}{'change':>9}{'bar':>7}"]
    for label, c in zip(labels, comparison.checks):
        lines.append(f"{label:<{width}}{percent(c.before_rate):>8}{percent(c.after_rate):>8}"
                     f"{_points(c.points):>9}{percent(c.threshold):>7}")
    if before.attacks or after.attacks:
        lines.append(f"{'attacks resisted':<{width}}{_attack_rate(before):>8}{_attack_rate(after):>8}")
    sections = _case_sections(comparison)
    id_width = min(max([len(c.case_id) for _, changes in sections for c in changes] + [6]) + 2, 40)
    for title, changes in sections:
        lines += ["", f"{title}: {len(changes)}"]
        lines += [f"  {_case_line(change, id_width)}" for change in changes]
    if comparison.only_before:
        lines += ["", f"only in the before run: {', '.join(comparison.only_before)}"]
    return "\n".join(lines)


def render_comparison_markdown(comparison: RunComparison) -> str:
    """Markdown, for a README section or the GitHub Actions run page."""
    before, after = comparison.before, comparison.after
    lines = [f"**Before:** `{before.agent_version}` (run `{before.run_id}`) · "
             f"**After:** `{after.agent_version}` (run `{after.run_id}`)", ""]
    lines += [f"> {w}" for w in comparison.warnings] + ([""] if comparison.warnings else [])
    lines += ["| Check | Before | After | Change | Bar |", "|---|---|---|---|---|"]
    for c in comparison.checks:
        label = c.check + ("" if c.blocking else " (doesn't block)")
        lines.append(f"| {label} | {percent(c.before_rate)} | {percent(c.after_rate)} | {_points(c.points)} | "
                     f"{percent(c.threshold)} |")
    if before.attacks or after.attacks:
        lines.append(f"| attacks resisted | {_attack_rate(before)} | {_attack_rate(after)} | | |")
    lines.append("")
    for title, changes in _case_sections(comparison):
        cases = ", ".join(f"{c.case_id} ({c.priority})" for c in changes) or "none"
        lines.append(f"- **{title}:** {cases}")
    return "\n".join(lines)


def _check_changes(before: RunRecord, after: RunRecord) -> list[CheckChange]:
    before_rates = {s["check"]: s for s in before.summaries}
    after_rates = {s["check"]: s for s in after.summaries}
    names = list(after_rates) + [name for name in before_rates if name not in after_rates]
    changes = []
    for name in names:
        latest = after_rates.get(name) or before_rates[name]
        changes.append(CheckChange(check=name, threshold=latest["threshold"], blocking=latest.get("blocking", True),
                                   before_rate=before_rates.get(name, {}).get("pass_rate"),
                                   after_rate=after_rates.get(name, {}).get("pass_rate")))
    return changes


def _failing_checks(record: RunRecord, blocking: set) -> dict[str, list[str]]:
    return {o["case_id"]: [r["check"] for r in o["results"] if r["status"] in FAILING and r["check"] in blocking]
            for o in record.outcomes}


def _case_change(outcome: dict, failed_before: list[str], failed_after: list[str]) -> CaseChange:
    return CaseChange(case_id=outcome["case_id"], category=outcome.get("category", ""),
                      priority=outcome.get("priority", "medium"), failed_before=failed_before,
                      failed_after=failed_after)


def _case_sections(comparison: RunComparison) -> list[tuple[str, list[CaseChange]]]:
    sections = [("newly failing (regressions)", comparison.newly_failing), ("fixed", comparison.fixed),
                ("still failing", comparison.still_failing)]
    if comparison.only_after:
        sections.append(("new cases failing", comparison.new_cases_failing))
    return sections


def _case_line(change: CaseChange, id_width: int) -> str:
    before = ", ".join(change.failed_before) or "passed"
    after = ", ".join(change.failed_after) or "passes"
    return f"{change.case_id:<{id_width}}{change.priority:<8}{before}  →  {after}"


def _points(points: Optional[int]) -> str:
    return "-" if points is None else f"{points:+d} pts"


def _attack_rate(record: RunRecord) -> str:
    return percent(record.attacks["resistance_rate"]) if record.attacks else "-"
