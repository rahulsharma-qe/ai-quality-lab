"""The human review queue: after every run, the findings a person should look at, and why.

A check matches words and a judge reads meaning; where they disagree, or a check flags its own
doubt, a person decides. The queue collects those cases with the question, the answer, both
opinions and, for a likely false alarm, a ready-to-paste accepted finding. The decision goes into
the team config through a reviewed pull request, so it stays owned, explained and dated.

What lands in the queue (golden cases only; findings already accepted are left out):
  check_vs_judge       a check failed, the judge passed: possibly a false alarm
  judge_only           the judge failed, every blocking check passed: possibly a hidden error
  possible_false_alarm a check flagged its own doubt (e.g. a forbidden phrase right after "not")
  acceptance_expiring  an accepted finding expires soon: fix the case or review it again

It is a file, a report section and a command, not a review app.
"""

import json
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from aiquality.checks.phrase_checks import POSSIBLE_FALSE_ALARM
from aiquality.errors import SetupError
from aiquality.reporting.run_record import RUN_RECORDS_FILE, RunRecord, load_run_records
from aiquality.dates import parse_day, shown_day

FAILING = ("FAIL", "ERROR")
EXPIRING_WITHIN_DAYS = 7
ACCEPTANCE_DAYS = 30
WHY = {
    "check_vs_judge": "the check failed but the judge passed it: possibly a false alarm",
    "judge_only": "the judge failed it but every blocking check passed: possibly a hidden error",
    "possible_false_alarm": "the check doubts its own match (right after a negation word)",
    "acceptance_expiring": "an accepted finding expires soon: fix the case or review it again",
}


@dataclass
class ReviewItem:
    case_id: str
    check: str
    kind: str                       # one of WHY's keys
    why: str
    priority: str
    question: str
    answer: str
    finding: str                    # what the check (or judge) said
    judge: Optional[str] = None     # the judge's verdict and reason, when a judge took part
    accept_snippet: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


def build_review_queue(record: RunRecord, today: Optional[date] = None) -> list[ReviewItem]:
    today = today or date.today()
    gate = record.gate_decision or {}
    accepted = {(a["case"], a["check"]) for a in gate.get("accepted_findings", [])}
    judge_check = (record.judge or {}).get("check")
    blocking = {s["check"] for s in record.summaries if s.get("blocking", True)}
    items = []
    for outcome in record.outcomes:
        if outcome.get("category") == "attack":
            continue
        results = {r["check"]: r for r in outcome["results"]}
        judge = results.get(judge_check)
        judge_text = f"{judge['status']}: {judge['reason']}" if judge else None
        for result in outcome["results"]:
            key = (outcome["case_id"], result["check"])
            if result["check"] == judge_check or key in accepted or result["status"] != "FAIL":
                continue
            if judge and judge["status"] == "PASS":
                items.append(_item(outcome, result, "check_vs_judge", judge_text, today))
            elif _doubts_itself(result):
                items.append(_item(outcome, result, "possible_false_alarm", judge_text, today))
        others_pass = all(r["status"] not in FAILING for name, r in results.items()
                          if name in blocking and name != judge_check)
        if judge and judge["status"] == "FAIL" and others_pass:
            items.append(_item(outcome, judge, "judge_only", judge_text, today, snippet=False))
    items += _expiring(record, gate, today)
    return items


def render_review_queue(items: list[ReviewItem], team: str) -> str:
    if not items:
        return f"review queue · team {team}: nothing needs a person"
    lines = [f"review queue · team {team}: {len(items)} item(s) need a person", ""]
    for item in items:
        lines += [f"{item.case_id} · {item.check} · {item.kind} ({item.priority})", f"  why:      {item.why}",
                  f"  question: {_short(item.question)}", f"  answer:   {_short(item.answer)}",
                  f"  finding:  {item.finding}"]
        if item.judge and item.judge.split(": ", 1)[-1].strip() != item.finding.strip():   # the judge's own finding: once
            lines.append(f"  judge:    {item.judge}")
        if item.accept_snippet:
            lines += ["  if it's a false alarm, add to accepted_findings:"]
            lines += [f"    {line}" for line in item.accept_snippet.splitlines()]
        lines.append("")
    return "\n".join(lines).rstrip()


def write_review_queue(items: list[ReviewItem], path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(i.to_dict(), ensure_ascii=False) + "\n" for i in items), encoding="utf-8")
    return path


def last_run_for_team(output_dir, team: str) -> RunRecord:
    path = Path(output_dir) / RUN_RECORDS_FILE
    if not path.is_file():
        raise SetupError(f"no run records at {path}: run 'aiquality gate --team {team}' first")
    runs = [r for r in load_run_records(path) if r.team == team]
    if not runs:
        raise SetupError(f"no run for team {team} in {path}: run 'aiquality gate --team {team}' first")
    return runs[-1]


def _item(outcome, result, kind, judge_text, today, snippet=True) -> ReviewItem:
    return ReviewItem(case_id=outcome["case_id"], check=result["check"], kind=kind, why=WHY[kind],
                      priority=outcome.get("priority", "medium"), question=outcome.get("question") or "",
                      answer=outcome.get("answer_text") or "", finding=result["reason"], judge=judge_text,
                      accept_snippet=_snippet(outcome["case_id"], result["check"], today) if snippet else None)


def _expiring(record, gate, today) -> list[ReviewItem]:
    outcomes = {o["case_id"]: o for o in record.outcomes}
    items = []
    for acceptance in gate.get("accepted_findings", []):
        expires = parse_day(acceptance["expires"])
        if expires - today <= timedelta(days=EXPIRING_WITHIN_DAYS):
            outcome = outcomes.get(acceptance["case"], {})
            items.append(ReviewItem(case_id=acceptance["case"], check=acceptance["check"], kind="acceptance_expiring",
                                    why=WHY["acceptance_expiring"], priority=outcome.get("priority", "medium"),
                                    question=outcome.get("question") or "", answer=outcome.get("answer_text") or "",
                                    finding=f"accepted until {shown_day(expires)}: {acceptance['reason']}"))
    return items


def _doubts_itself(result: dict) -> bool:
    return POSSIBLE_FALSE_ALARM in result.get("flags", []) or "possible false alarm" in result.get("reason", "")


def _snippet(case_id: str, check: str, today: date) -> str:
    return (f"- case: {case_id}\n  check: {check}\n  reason: \"<why this is a false alarm>\"\n"
            f"  approved_by: <your name>\n  expires: {shown_day(today + timedelta(days=ACCEPTANCE_DAYS))}")


def _short(text: str, limit: int = 160) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit - 1] + "…"
