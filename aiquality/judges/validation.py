"""Check the examiner before trusting its marks: measure a judge against people's labels.

Two numbers, because one is not enough:
  catches real failures      of the answers a person FAILED, the share the judge also failed
  leaves good answers alone  of the answers a person PASSED, the share the judge also passed
A judge that fails everything scores 100% on the first and 0% on the second, so both must clear
their bar. Results are broken down by category too, because an average can hide one category
the judge gets wrong.

Rules that keep the numbers honest:
  - improve the judge on the tuning half only ("tune")
  - measure the held-back half once the judge is final ("holdout"); never tune on it
  - a new judge version (new model, new rubric) starts unvalidated and is measured again

Every run is appended to a results file with the judge's version. judge_status(version) reads
it: only a 'qualified' judge may block a release; any other judge is advisory.

Label file format (JSON): {"cases": [{"id", "input", "answer", "human_label": "PASS" | "FAIL",
"category", "split": "tune" | "holdout", "label_reason", ...golden-case fields}]}
"""

import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from aiquality.errors import SetupError
from aiquality.test_data import GoldenCase

MIN_CATCH_RATE = 0.85         # of human FAILs, the judge must also fail at least this share
MIN_LEAVE_ALONE_RATE = 0.80   # of human PASSes, the judge must also pass at least this share
SPLITS = ("tune", "holdout", "all")
GATING_SPLITS = ("holdout", "all")
STATUS_QUALIFIED, STATUS_NOT_QUALIFIED, STATUS_UNVALIDATED = "qualified", "not_qualified", "unvalidated"


@dataclass
class LabelledAnswer:
    """One answer a person has labelled PASS or FAIL."""

    case: GoldenCase
    answer: str
    human_label: str
    category: str = "uncategorised"
    split: str = ""
    label_reason: Optional[str] = None
    failure_type: Optional[str] = None

    @property
    def id(self) -> str:
        return self.case.id

    @classmethod
    def from_dict(cls, data: dict) -> "LabelledAnswer":
        return cls(case=GoldenCase.from_dict(data), answer=str(data.get("answer", "")),
                   human_label=str(data.get("human_label", "")), category=data.get("category", "uncategorised"),
                   split=data.get("split", ""), label_reason=data.get("label_reason"),
                   failure_type=data.get("failure_type"))


@dataclass
class ValidationRun:
    judge_version: str
    split: str
    overall: dict
    by_category: dict
    disagreements: list[dict]
    errored: list[tuple[str, str]] = field(default_factory=list)
    qualified: Optional[bool] = None          # None for a tuning run: it is not a qualification
    skipped_unlabelled: int = 0

    def to_row(self) -> dict:
        return {"timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "judge_version": self.judge_version, "split": self.split, "overall": self.overall,
                "by_category": self.by_category, "disagreement_ids": [d["id"] for d in self.disagreements],
                "errored_ids": [case_id for case_id, _ in self.errored],
                "bars": {"min_catch_rate": MIN_CATCH_RATE, "min_leave_alone_rate": MIN_LEAVE_ALONE_RATE},
                "qualified": self.qualified}


def load_labels(path, split: str = "all") -> tuple[list[LabelledAnswer], int]:
    """The labelled answers of one split, and how many cases were skipped for having no label yet."""
    path = Path(path)
    if split not in SPLITS:
        raise SetupError(f"split must be one of {', '.join(SPLITS)}")
    try:
        cases = json.loads(path.read_text(encoding="utf-8"))["cases"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise SetupError(f"could not read judge labels {path}: {error}")
    if split != "all":
        cases = [c for c in cases if c.get("split") == split]
    labelled = [LabelledAnswer.from_dict(c) for c in cases if c.get("human_label") in ("PASS", "FAIL")]
    return labelled, len(cases) - len(labelled)


def run_judge(judge, items: list[LabelledAnswer], retries: int = 2, wait_seconds: float = 1.0):
    """{id: verdict} for every answer the judge graded; calls that kept failing are left out and
    listed, so a network glitch never counts as a right or wrong verdict."""
    verdicts, errored = {}, []
    for item in items:
        for attempt in range(retries + 1):
            try:
                verdicts[item.id] = judge.verdict(item.case, item.answer)
                break
            except Exception as error:  # noqa: BLE001  (any failure of the call is infrastructure)
                if attempt == retries:
                    errored.append((item.id, str(error)[:120]))
                else:
                    time.sleep(wait_seconds)
    return verdicts, errored


def score(items, verdicts: dict) -> dict:
    scored = [i for i in items if i.id in verdicts]
    human_fail = [i for i in scored if i.human_label == "FAIL"]
    human_pass = [i for i in scored if i.human_label == "PASS"]
    caught = sum(1 for i in human_fail if not verdicts[i.id].passed)
    left_alone = sum(1 for i in human_pass if verdicts[i.id].passed)
    return {"n": len(scored), "human_fail": len(human_fail), "human_pass": len(human_pass),
            "catch_rate": _rate(caught, len(human_fail)), "leave_alone_rate": _rate(left_alone, len(human_pass)),
            "agreement": _rate(caught + left_alone, len(scored))}


def by_category(items, verdicts: dict) -> dict:
    groups = defaultdict(list)
    for item in items:
        groups[item.category].append(item)
    return {category: score(group, verdicts) for category, group in sorted(groups.items())}


def disagreements(items, verdicts: dict) -> list[dict]:
    found = []
    for item in items:
        verdict = verdicts.get(item.id)
        if verdict is None:
            continue
        judge_label = "PASS" if verdict.passed else "FAIL"
        if judge_label != item.human_label:
            found.append({"id": item.id, "category": item.category, "human": item.human_label,
                          "judge": judge_label, "human_reason": item.label_reason,
                          "judge_reason": verdict.reason, "failure_type": item.failure_type})
    return found


def qualifies(overall: dict) -> bool:
    catch, leave_alone = overall["catch_rate"], overall["leave_alone_rate"]
    return (catch is not None and leave_alone is not None
            and catch >= MIN_CATCH_RATE and leave_alone >= MIN_LEAVE_ALONE_RATE)


def validate_judge(judge, items: list[LabelledAnswer], split: str, skipped_unlabelled: int = 0) -> ValidationRun:
    ids = [item.id for item in items]
    duplicates = sorted({case_id for case_id in ids if ids.count(case_id) > 1})
    if duplicates:
        raise SetupError(f"every labelled answer needs its own id; repeated: {', '.join(duplicates)}")
    verdicts, errored = run_judge(judge, items)
    overall = score(items, verdicts)
    return ValidationRun(judge_version=judge.version, split=split, overall=overall,
                         by_category=by_category(items, verdicts), disagreements=disagreements(items, verdicts),
                         errored=errored, qualified=qualifies(overall) if split in GATING_SPLITS else None,
                         skipped_unlabelled=skipped_unlabelled)


def save_run(run: ValidationRun, results_path) -> Path:
    path = Path(results_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(run.to_row()) + "\n")
    return path


def judge_status(version: str, results_path) -> str:
    """'qualified', 'not_qualified' or 'unvalidated' for this exact judge version, from its latest
    held-back run. A new model or rubric is a new version, so it is unvalidated again."""
    try:
        rows = [json.loads(line) for line in Path(results_path).read_text(encoding="utf-8").splitlines()
                if line.strip()]
    except FileNotFoundError:
        return STATUS_UNVALIDATED
    runs = [r for r in rows if r.get("judge_version") == version and r.get("split") in GATING_SPLITS]
    if not runs:
        return STATUS_UNVALIDATED
    return STATUS_QUALIFIED if runs[-1].get("qualified") else STATUS_NOT_QUALIFIED


def render_validation(run: ValidationRun) -> str:
    lines = [f"judge {run.judge_version} · split {run.split}", "",
             f"{'':14} {'n':>3} {'fails':>6} {'catches':>8} {'leaves good':>12}", "-" * 47]
    for category, s in list(run.by_category.items()) + [("ALL", run.overall)]:
        if category == "ALL":
            lines.append("-" * 47)
        lines.append(f"{category:14} {s['n']:>3} {s['human_fail']:>6} {_percent(s['catch_rate']):>8} "
                     f"{_percent(s['leave_alone_rate']):>12}")
    if run.overall["human_fail"]:
        lines.append(f"\nsmall-sample note: {run.overall['human_fail']} human FAILs, so one case moves the catch "
                     f"rate by about {1 / run.overall['human_fail']:.0%}. A direction, not a verdict.")
    if run.skipped_unlabelled:
        lines.append(f"skipped {run.skipped_unlabelled} case(s) with no human label yet")
    if run.errored:
        lines.append(f"{len(run.errored)} judge call(s) failed (infrastructure, not quality) and were left out")
    if run.disagreements:
        lines.append(f"\ndisagreements ({len(run.disagreements)}):")
        for d in run.disagreements:
            lines += [f"  {d['id']} [{d['category']}] person {d['human']} vs judge {d['judge']}",
                      f"      person: {d['human_reason']}", f"      judge:  {d['judge_reason']}"]
    bars = f"bars: catches >= {MIN_CATCH_RATE:.0%}, leaves good alone >= {MIN_LEAVE_ALONE_RATE:.0%}"
    if run.qualified is None:
        lines.append(f"\ntuning run: improve the judge with the disagreements; not a qualification ({bars})")
    else:
        lines.append(f"\nJUDGE: {'QUALIFIED to gate' if run.qualified else 'NOT QUALIFIED to gate'} ({bars})")
    return "\n".join(lines)


def _rate(numerator: int, denominator: int) -> Optional[float]:
    return round(numerator / denominator, 3) if denominator else None


def _percent(value) -> str:
    return "  n/a" if value is None else f"{value:5.0%}"
