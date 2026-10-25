"""The evidence a run record can give, by name. A framework file names these; nothing else is evidence.

    check:<name>            a check's result: passed, failed, its bar, and whether the bar is met
    attack_resistance       attack results, overall and per family
    release_gate            the gate's decision and why
    golden_set              the test set: name, version, cases by category, checks and their bars
    judge_validation        whether the AI judge was measured against people's labels, and how it did
    human_review            accepted findings (reason, who, until when) and questions handed over
    run_records             the run's id, time, commit, agent version
    production_monitoring   monitoring of the agent in use: not something a test run records

Each gives an Evidence: found or not, met or not (None when there is no bar to meet), a one-line
summary and the facts behind it. A name a run can't fill says why, in plain words.
"""

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from aiquality.reporting.run_record import RunRecord

CHECK_PREFIX = "check:"


@dataclass
class Evidence:
    name: str
    found: bool
    summary: str
    facts: list = field(default_factory=list)
    met: Optional[bool] = None          # False: the evidence shows a bar not met


EVIDENCE: dict[str, Callable] = {}


def _evidence(name: str):
    def register(function):
        EVIDENCE[name] = function
        return function
    return register


def known_evidence(name: str) -> bool:
    return (name in EVIDENCE or name == "judge_validation"
            or (name.startswith(CHECK_PREFIX) and len(name) > len(CHECK_PREFIX)))


def gather(name: str, record: RunRecord, judge_results: Optional[Path] = None) -> Evidence:
    if name.startswith(CHECK_PREFIX):
        return _check(name[len(CHECK_PREFIX):], record)
    if name == "judge_validation":
        return _judge_validation(record, judge_results)
    return EVIDENCE[name](record)


def _percent(rate: float) -> str:
    return f"{rate * 100:.1f}".rstrip("0").rstrip(".") + "%"


def _check(check: str, record: RunRecord) -> Evidence:
    name = CHECK_PREFIX + check
    scopes = {s["check"]: s for s in (record.gate_decision or {}).get("scopes", []) if s.get("scope") == "team"}
    summary = scopes.get(check) or next((s for s in record.summaries if s["check"] == check), None)
    if summary is None:
        return Evidence(name, False, f"No check named {check} in this team's run.")
    total = summary["passed"] + summary["failed"]
    rate, bar = summary.get("pass_rate", 0.0), summary.get("threshold", 1.0)
    met = rate >= bar
    advisory = "" if summary.get("blocking", True) else ", advisory"
    line = f"{check}: {summary['passed']} of {total} passed ({_percent(rate)}, bar {_percent(bar)}{advisory})"
    facts = [line]
    if check in scopes:
        facts.append("After accepted findings, as the release gate counts it")
    return Evidence(name, True, line, facts, met)


@_evidence("attack_resistance")
def _attacks(record: RunRecord) -> Evidence:
    attacks = record.attacks or {}
    if not attacks.get("total"):
        return Evidence("attack_resistance", False, "No attack cases in this run.")
    families = [f"{f['family'].replace('_', ' ').capitalize()}: {f['resisted']} of {f['total']} resisted"
                for f in attacks.get("families", [])]
    bar = (record.gate_decision or {}).get("attacks", {}).get("threshold", 1.0)
    met = attacks.get("resistance_rate", 0.0) >= bar
    return Evidence("attack_resistance", True,
                    f"{attacks['resisted']} of {attacks['total']} attacks resisted, {len(families)} families",
                    families, met)


@_evidence("release_gate")
def _gate(record: RunRecord) -> Evidence:
    gate = record.gate_decision
    if not gate:
        return Evidence("release_gate", False, f"This run was an '{record.command}', not a gate: no release decision.")
    reasons = gate.get("failures") or []
    summary = f"Gate {gate['decision']}" + (f": {reasons[0]}" if reasons else ": every blocking bar met")
    facts = [f"{s['check']}: {_percent(s['pass_rate'])} (bar {_percent(s['threshold'])})"
             + ("" if s.get("blocking", True) else ", advisory") for s in gate.get("scopes", []) if s.get("scope") == "team"]
    facts += [f"High-priority bar: {p['priority']} cases {_percent(p['pass_rate'])} (bar {_percent(p['bar'])})"
              + (f", failed: {', '.join(p['failed'])}" if p.get("failed") else "") for p in gate.get("priorities", [])]
    facts += reasons[1:]
    return Evidence("release_gate", True, summary, facts, bool(gate.get("passed")))


@_evidence("golden_set")
def _golden_set(record: RunRecord) -> Evidence:
    categories = Counter(outcome.get("category") or "uncategorised" for outcome in record.outcomes)
    spread = ", ".join(f"{count} {name.replace('_', ' ')}" for name, count in sorted(categories.items()))
    checks = ", ".join(f"{s['check']} {_percent(s['threshold'])}" for s in record.summaries)
    return Evidence("golden_set", True,
                    f"{record.golden_set_name} {record.golden_set_version}: {record.case_count} cases",
                    [f"Cases: {spread}", f"Checks and their bars: {checks}", f"Source: {Path(record.golden_set_source).name}"])


def _judge_validation(record: RunRecord, results: Optional[Path]) -> Evidence:
    judge = record.judge
    if not judge:
        return Evidence("judge_validation", False, "No AI judge in this run.")
    facts = [f"Judge {judge['version']}: {judge['status'].replace('_', ' ')}, "
             + ("can block" if judge.get("blocking") else "reports only")]
    measured = _last_validation(results, judge["version"])
    if measured is None:
        return Evidence("judge_validation", False, f"The judge {judge['version']} has no validation run.", facts)
    overall = measured["overall"]
    facts.append(f"{measured['split']} labels, {overall['n']} answers: catches {_percent(overall['catch_rate'])} of real "
                 f"failures, leaves {_percent(overall['leave_alone_rate'])} of good answers alone")
    return Evidence("judge_validation", True,
                    f"Judge measured against people's labels ({measured['split']}): {judge['status'].replace('_', ' ')}",
                    facts)


def _last_validation(results: Optional[Path], version: str) -> Optional[dict]:
    if results is None or not Path(results).is_file():
        return None
    runs = [json.loads(line) for line in Path(results).read_text(encoding="utf-8").splitlines() if line.strip()]
    matching = [run for run in runs if run.get("judge_version") == version]
    return matching[-1] if matching else None


@_evidence("human_review")
def _human_review(record: RunRecord) -> Evidence:
    accepted = (record.gate_decision or {}).get("accepted_findings", [])
    handed = [o for o in record.outcomes if o.get("category") == "out_of_scope"]
    if not accepted and not handed:
        return Evidence("human_review", False, "No accepted findings and no questions to hand over in this run.")
    facts = [f"{a['case']} {a['check']}: {a['reason']} (approved by {a['approved_by']}, until {a['expires']})"
             for a in accepted]
    if handed:
        facts.append(f"{len(handed)} questions outside the policies, where the agent should hand over to a person")
    return Evidence("human_review", True,
                    f"{len(accepted)} accepted findings with reason, approver and expiry; "
                    f"{len(handed)} hand-over questions", facts)


@_evidence("run_records")
def _run_records(record: RunRecord) -> Evidence:
    return Evidence("run_records", True,
                    f"Run {record.run_id}: time, commit, agent version, every answer and verdict",
                    [f"Run {record.run_id}, {record.created_at}, commit {record.git_commit or 'unknown'}",
                     f"Agent {record.agent_version}; {record.run_mode} answers",
                     "Every answer and every check result is kept in run_records.jsonl, and can be exported "
                     "as OpenTelemetry traces"])


@_evidence("production_monitoring")
def _production(record: RunRecord) -> Evidence:
    return Evidence("production_monitoring", False,
                    "A test run doesn't watch the agent in use: drift monitoring is a study in "
                    "demos/observability, not part of the platform's runs.")
