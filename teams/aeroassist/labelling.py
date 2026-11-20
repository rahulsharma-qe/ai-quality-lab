"""Labelling the judge's held-back answers, in an order that keeps the labels honest.

The live session (live_session.py) keeps v7's first answer to every held-back case and seals the
judge's verdicts on them. This module is how a person labels those answers, then measures the judge:

  1. Label every answer PASS or FAIL against the labelling guide (labelling_guide.md), with the judge's
     verdicts hidden. A label needs the rubric rule it rests on (1-7 for a FAIL, "pass" for a PASS)
     and a one-line reason; without them it is refused.
  2. Cross-check flags, for re-reading only (a flag never changes a label): a PASS on an answer whose
     decision is wrong, a FAIL on an answer whose decision is right. Where the decision reader couldn't
     read the decision, the flag says so.
  3. Wait at least RELABEL_AFTER_DAYS days after the last first label.
  4. Label again a sample of RELABEL_SHARE of the answers, drawn with a seed stored with the labels, with
     the first labels, their reasons and the verdicts all hidden.
  5. Settle each disagreement between the two labels with a reason; changes are counted.
  6. Freeze: the labels' hash is stored. Only then are the sealed verdicts read and the judge's
     agreement computed, with the platform's own scoring (aiquality/judges/validation.py). A label
     changed after the freeze doesn't count for this judge version.

Everything is kept in labels.json in the session folder.
"""

import hashlib
import json
import math
import random
from datetime import date
from pathlib import Path
from typing import Optional

from aiquality.dates import parse_day, shown_day
from aiquality.judges.base import JudgeVerdict
from aiquality.judges.validation import MIN_CATCH_RATE, MIN_LEAVE_ALONE_RATE, LabelledAnswer, qualifies, score
from aiquality.test_data import GoldenCase

from live_session import HELD_BACK, V7, _base_id

RULES = {"pass": "PASS", **{str(n): "FAIL" for n in range(1, 8)}}       # the rubric's rule -> the label it supports
RELABEL_AFTER_DAYS = 7
RELABEL_SHARE = 0.2
LABELS_FILE = "labels.json"


class LabellingError(ValueError):
    """A step done out of order, or a label without what it needs."""


def held_back_answers(session_folder) -> list[dict]:
    """v7's first answer to each held-back case (the first identity for a counterfactual case), without the
    judge's verdict: id, question, answer and what the decision check read."""
    rows = [json.loads(line) for line in (Path(session_folder) / "answers.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()]
    latest = {(r["case_id"], r["agent_version"], r["try"]): r for r in rows}
    items, seen = [], set()
    for r in latest.values():
        base = _base_id(r["case_id"])
        if r["version"] != V7 or r["try"] != 1 or base not in HELD_BACK or base in seen or r.get("results") is None:
            continue
        seen.add(base)
        decision = next((x for x in r["results"] if x["check"] == "decision"), {})
        items.append({"id": r["case_id"], "question": r["question"], "answer": r["answer_text"] or "",
                      "decision": decision.get("status"), "decision_flags": decision.get("flags") or []})
    return sorted(items, key=lambda item: item["id"])


class Labels:
    """The labels and every step's record, in labels.json."""

    def __init__(self, session_folder):
        self.folder = Path(session_folder)
        self.path = self.folder / LABELS_FILE
        self.items = {item["id"]: item for item in held_back_answers(self.folder)}
        self.state = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {
            "seed": random.SystemRandom().randrange(1, 2**31), "first": {}, "second": {}, "settled": {},
            "frozen": None}

    def save(self) -> None:
        self.path.write_text(json.dumps(self.state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # 1. first labels --------------------------------------------------------------------------------
    def label(self, case_id: str, label: str, rule: str, reason: str, today: Optional[date] = None,
              second: bool = False) -> None:
        self._not_frozen()
        if case_id not in self.items:
            raise LabellingError(f"{case_id} is not a held-back answer")
        label, rule, reason = str(label).upper(), str(rule).lower().strip(), (reason or "").strip()
        if rule not in RULES:
            raise LabellingError(f"a label needs the rubric rule it rests on: 1-7 for a FAIL, 'pass' for a PASS "
                                 f"(got {rule!r})")
        if RULES[rule] != label:
            raise LabellingError(f"rule {rule} supports {RULES[rule]}, not {label}")
        if not reason or "\n" in reason:
            raise LabellingError("a label needs a one-line reason")
        if second and case_id not in self.relabel_sample(today):
            raise LabellingError(f"{case_id} is not in the re-label sample")
        stage = "second" if second else "first"
        self.state[stage][case_id] = {"label": label, "rule": rule, "reason": reason,
                                      "on": shown_day(today or date.today())}
        self.save()

    # 2. flags -----------------------------------------------------------------------------------------
    def flags(self) -> list[str]:
        """Labels to read again: they disagree with the decision the golden set expects. Never changes a label."""
        found = []
        for case_id, first in sorted(self.state["first"].items()):
            item = self.items[case_id]
            unreadable = item["decision"] not in ("PASS", "FAIL") or item["decision_flags"]
            note = " (the decision reader couldn't read this one; it may be wrong)" if unreadable else ""
            if first["label"] == "PASS" and item["decision"] == "FAIL":
                found.append(f"{case_id}: labelled PASS, but its decision is wrong{note}")
            elif first["label"] == "FAIL" and item["decision"] == "PASS":
                found.append(f"{case_id}: labelled FAIL (rule {first['rule']}), but its decision is right{note}")
            elif unreadable:
                found.append(f"{case_id}: the decision reader couldn't read this answer; nothing to compare")
        return found

    # 3-4. the re-label sample ------------------------------------------------------------------------
    def relabel_sample(self, today: Optional[date] = None) -> list[str]:
        missing = sorted(set(self.items) - set(self.state["first"]))
        if missing:
            raise LabellingError(f"label every answer first: {len(missing)} left ({', '.join(missing[:5])} ...)")
        last = max(parse_day(row["on"]) for row in self.state["first"].values())
        waited = ((today or date.today()) - last).days
        if waited < RELABEL_AFTER_DAYS:
            raise LabellingError(f"wait {RELABEL_AFTER_DAYS} days after the last first label ({shown_day(last)}); "
                                 f"{waited} so far")
        ids = sorted(self.items)
        return sorted(random.Random(self.state["seed"]).sample(ids, math.ceil(RELABEL_SHARE * len(ids))))

    def to_relabel(self, today: Optional[date] = None) -> list[dict]:
        """The sample, as it is shown: question and answer only (no first label, reason or verdict)."""
        return [{"id": i, "question": self.items[i]["question"], "answer": self.items[i]["answer"]}
                for i in self.relabel_sample(today) if i not in self.state["second"]]

    # 5. settle ----------------------------------------------------------------------------------------
    def disagreements(self) -> list[str]:
        return sorted(i for i, second in self.state["second"].items()
                      if second["label"] != self.state["first"][i]["label"] and i not in self.state["settled"])

    def settle(self, case_id: str, label: str, reason: str) -> None:
        self._not_frozen()
        if case_id not in self.state["second"]:
            raise LabellingError(f"{case_id} has no second label to settle")
        if not (reason or "").strip():
            raise LabellingError("settling needs a reason")
        changed = label.upper() != self.state["first"][case_id]["label"]
        self.state["settled"][case_id] = {"label": label.upper(), "reason": reason.strip(), "changed": changed}
        self.save()

    def final_labels(self) -> dict:
        labels = {i: row["label"] for i, row in self.state["first"].items()}
        labels.update({i: row["label"] for i, row in self.state["settled"].items()})
        return labels

    # 6. freeze, then the judge's agreement ------------------------------------------------------------
    def freeze(self, today: Optional[date] = None) -> str:
        self._not_frozen()
        sample = self.relabel_sample(today)
        if [i for i in sample if i not in self.state["second"]] or self.disagreements():
            raise LabellingError("re-label the whole sample and settle every disagreement before freezing")
        labels = self.final_labels()
        sha = hashlib.sha256(json.dumps(labels, sort_keys=True).encode("utf-8")).hexdigest()
        agreed = sum(self.state["second"][i]["label"] == self.state["first"][i]["label"] for i in sample)
        self.state["frozen"] = {"sha": sha, "on": shown_day(today or date.today()), "relabel_agreed": agreed,
                                "relabel_sample": len(sample),
                                "changed_when_settled": sum(row["changed"] for row in self.state["settled"].values())}
        self.save()
        return sha

    def judge_agreement(self) -> dict:
        """The judge measured against the frozen labels. Refused before the freeze or if a label changed since."""
        frozen = self.state["frozen"]
        if not frozen:
            raise LabellingError("freeze the labels first; the sealed verdicts stay sealed until then")
        labels = self.final_labels()
        if hashlib.sha256(json.dumps(labels, sort_keys=True).encode("utf-8")).hexdigest() != frozen["sha"]:
            raise LabellingError("the labels changed after the freeze; they don't count for this judge version")
        from aiquality.judges.recorded import answer_sha
        sealed = [json.loads(line) for line in (self.folder / "sealed_verdicts.jsonl").read_text(encoding="utf-8")
                  .splitlines() if line.strip()]
        by_answer = {row["answer_sha"]: row for row in sealed}
        items, verdicts, versions = [], {}, set()
        for case_id, label in labels.items():
            item = self.items[case_id]
            row = by_answer.get(answer_sha(item["answer"]))
            if row is None:
                continue
            versions.add(row["judge_version"])
            items.append(LabelledAnswer(case=GoldenCase(id=case_id, input=item["question"]), answer=item["answer"],
                                        human_label=label))
            verdicts[case_id] = JudgeVerdict(row["verdict"] == "PASS", row["reason"])
        overall = score(items, verdicts)
        return {**overall, "judge_versions": sorted(versions), "qualifies": qualifies(overall),
                "bars": {"catch_rate": MIN_CATCH_RATE, "leave_alone_rate": MIN_LEAVE_ALONE_RATE},
                "relabel": f"{frozen['relabel_agreed']} of {frozen['relabel_sample']}", "labels_sha": frozen["sha"]}

    def _not_frozen(self) -> None:
        if self.state["frozen"]:
            raise LabellingError("the labels are frozen")
