"""Repeat checks: ask the same cases several times and see which results hold.

An AI agent doesn't give the same answer twice, and a model judge doesn't give the same verdict
twice, so one run can't tell a real fix from a lucky answer. Asking a case 3 times can: a case that
passes 3 of 3 is steady, a case that passes 1 of 3 is a coin toss, whatever one run said.

Each check is counted on its own, because they vary for different reasons: the answer_judge can
change its verdict on the same facts, while a phrase check only changes when the wording does.

    rows = [RepeatRow(...), ...]           # one per case per repeat, saved as JSONL
    summary = summarise_repeats(rows)      # per case and check: passes out of verdicts
    print(render_repeats(summary))
"""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

VERDICTS = ("PASS", "FAIL", "ERROR")      # NOT_APPLICABLE gives no verdict, so it isn't counted


@dataclass
class RepeatRow:
    """One answer to one case in one repeat, with every check's result on it."""

    case_id: str
    repeat: int
    agent_version: str
    answer_text: Optional[str]
    error: Optional[str]
    tool_calls: Optional[list]
    results: list = field(default_factory=list)      # [{"check", "status", "reason", "flags"}]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CheckCount:
    """How one check scored one case across the repeats."""

    passed: int = 0
    verdicts: int = 0

    @property
    def varies(self) -> bool:
        return 0 < self.passed < self.verdicts

    def text(self) -> str:
        if self.verdicts == 0:
            return "-"
        return f"{self.passed}/{self.verdicts}" + (" *" if self.varies else "")


@dataclass
class RepeatSummary:
    agent_version: str
    times: int
    case_ids: list
    checks: list
    counts: dict                                  # (case_id, check) -> CheckCount
    errors: dict = field(default_factory=dict)    # case_id -> calls that failed

    def count(self, case_id: str, check: str) -> CheckCount:
        return self.counts.get((case_id, check), CheckCount())

    def varying_cases(self, check: str) -> list:
        return [case_id for case_id in self.case_ids if self.count(case_id, check).varies]

    def judged_cases(self, check: str) -> list:
        return [case_id for case_id in self.case_ids if self.count(case_id, check).verdicts]


def summarise_repeats(rows: list[RepeatRow]) -> RepeatSummary:
    case_ids = list(dict.fromkeys(row.case_id for row in rows))
    checks = list(dict.fromkeys(result["check"] for row in rows for result in row.results))
    counts, errors = {}, {}
    for row in rows:
        if row.error:
            errors[row.case_id] = errors.get(row.case_id, 0) + 1
        for result in row.results:
            if result["status"] not in VERDICTS:
                continue
            count = counts.setdefault((row.case_id, result["check"]), CheckCount())
            count.verdicts += 1
            count.passed += result["status"] == "PASS"
    versions = sorted({row.agent_version for row in rows})
    times = max((row.repeat for row in rows), default=0)
    return RepeatSummary(", ".join(versions), times, case_ids, checks, counts, errors)


def render_repeats(summary: RepeatSummary) -> str:
    answers = len(summary.case_ids) * summary.times
    lines = [f"Repeat check: {len(summary.case_ids)} cases x {summary.times} times with {summary.agent_version} "
             f"({answers} answers)",
             "Each cell: passes / repeats that gave a verdict.  * the result changed between repeats.  "
             "- the check doesn't apply to this case.", ""]
    id_width = max([len("case")] + [len(case_id) for case_id in summary.case_ids])
    widths = [max(len(check), 6) for check in summary.checks]
    lines.append("  ".join(["case".ljust(id_width)] + [c.ljust(w) for c, w in zip(summary.checks, widths)]))
    for case_id in summary.case_ids:
        cells = [summary.count(case_id, check).text().ljust(w) for check, w in zip(summary.checks, widths)]
        failed_calls = summary.errors.get(case_id)
        note = f"  ({failed_calls} call(s) failed)" if failed_calls else ""
        lines.append("  ".join([case_id.ljust(id_width)] + cells).rstrip() + note)
    lines += ["", "results that changed between repeats:"]
    for check in summary.checks:
        varying, judged = summary.varying_cases(check), summary.judged_cases(check)
        listed = f": {', '.join(varying)}" if varying else ""
        lines.append(f"  {check}: {len(varying)} of {len(judged)} cases{listed}")
    return "\n".join(lines)


def save_repeat_rows(rows: list[RepeatRow], path: Path, append: bool = False) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a" if append else "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row.to_dict(), ensure_ascii=False) + "\n")
    return path


def load_repeat_rows(path: Path) -> list[RepeatRow]:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [RepeatRow(**json.loads(line)) for line in lines if line.strip()]
