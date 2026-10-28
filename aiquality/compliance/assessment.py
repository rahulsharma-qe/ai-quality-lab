"""A run's evidence held against a team's frameworks, at every risk level.

Each control gets one label, for the risk level the team set and for the others (the what-if view):

    applies, no evidence          it applies; the run lacks some or all of the evidence it names
    applies, bar not met          it applies; the evidence shows a bar not met (a failing gate, say)
    applies, evidence             it applies; the run has evidence, and no bar it shows is missed
    good practice                 it doesn't apply at this level; the run has evidence anyway
    not required here             it doesn't apply at this level, and the run has nothing for it
    outside the tool              an organisation's process: a test run can't show it

Evidence to support an assessment, never a compliance decision: nothing here says "compliant".
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from aiquality.compliance.evidence import Evidence, gather
from aiquality.compliance.frameworks import RISK_LEVELS, Control, Framework
from aiquality.reporting.run_record import RunRecord

LABELS = {
    "gap": "Applies, no evidence",
    "miss": "Applies, evidence: bar not met",
    "covered": "Applies, evidence",
    "practice": "Optional here (good practice)",
    "not_required": "Not required here",
    "outside": "Outside the tool",
}


@dataclass
class ControlResult:
    framework: Framework
    control: Control
    evidence: list = field(default_factory=list)        # Evidence, in the order the control names them
    labels: dict = field(default_factory=dict)          # risk level -> label key

    @property
    def anchor(self) -> str:
        text = f"{self.framework.key}-{self.control.id}".lower()
        return "-".join(part for part in "".join(c if c.isalnum() else " " for c in text).split())

    def summary(self) -> str:
        control = self.control
        if control.outside_the_tool:
            return control.outside_the_tool
        missing = [e.summary for e in self.evidence if not e.found]
        if missing:
            return " ".join(missing)
        return "; ".join(e.summary for e in self.evidence) + (" (partial)" if control.partial else "")


@dataclass
class Assessment:
    team: str
    risk_level: str                                      # the level this report is read at
    record: RunRecord
    results: list = field(default_factory=list)          # ControlResult
    frameworks: list = field(default_factory=list)       # Framework, in the team's order
    configured_level: str = ""                           # the level in team.yaml (risk_level, unless --as)

    def count(self, level: Optional[str] = None) -> dict:
        level = level or self.risk_level
        counts = {key: 0 for key in LABELS}
        for result in self.results:
            counts[result.labels[level]] += 1
        return counts

    def not_shown(self, level: Optional[str] = None) -> list:
        """The controls that apply and aren't shown to be met: what to look at first."""
        level = level or self.risk_level
        return [r for r in self.results if r.labels[level] in ("gap", "miss")]


def assess(record: RunRecord, frameworks: list, risk_level: str, judge_results: Optional[Path] = None,
           configured_level: str = "") -> Assessment:
    cache: dict[str, Evidence] = {}

    def evidence(name: str) -> Evidence:
        if name not in cache:
            cache[name] = gather(name, record, judge_results)
        return cache[name]

    assessment = Assessment(record.team, risk_level, record, frameworks=list(frameworks),
                            configured_level=configured_level or risk_level)
    for framework in frameworks:
        for control in framework.controls:
            result = ControlResult(framework, control, [evidence(name) for name in control.evidence])
            result.labels = {level: _label(control, result.evidence, level) for level in RISK_LEVELS}
            assessment.results.append(result)
    return assessment


def _label(control: Control, evidence: list, level: str) -> str:
    """Every evidence a control names must be there: a control shown by two things isn't shown by one."""
    if control.outside_the_tool:
        return "outside"
    complete = all(e.found for e in evidence)
    if level not in control.applies_when:
        return "practice" if complete else "not_required"
    if not complete:
        return "gap"
    return "miss" if any(e.met is False for e in evidence) else "covered"
