"""teams/aeroassist/labelling.py: labels for the judge's held-back answers, in an order that keeps them honest."""

import json
from datetime import date, timedelta

import pytest

import live_session as ls
from labelling import LabellingError, Labels

DAY1 = date(2026, 12, 1)


@pytest.fixture
def labels(tmp_path):
    ls.run_session(tmp_path, dry_run=True, log=lambda *_: None)
    return Labels(tmp_path)


def label_all(labels, day=DAY1):
    for case_id, item in labels.items.items():
        if item["decision"] == "PASS":
            labels.label(case_id, "PASS", "pass", "answers from the policy", today=day)
        else:
            labels.label(case_id, "FAIL", "1", "states the wrong window", today=day)


def test_the_held_back_answers_are_one_per_case_and_carry_no_verdict(labels):
    assert sorted(ls._base_id(i) for i in labels.items) == sorted(ls.HELD_BACK)
    assert all(set(item) == {"id", "question", "answer", "decision", "decision_flags"} for item in labels.items.values())


@pytest.mark.parametrize("label, rule, reason, message", [
    ("PASS", "", "fine", "rubric rule"), ("FAIL", "9", "x", "rubric rule"), ("FAIL", "pass", "x", "supports PASS"),
    ("PASS", "pass", "", "one-line reason"), ("PASS", "pass", "two\nlines", "one-line reason")])
def test_a_label_without_its_rule_and_a_one_line_reason_is_refused(labels, label, rule, reason, message):
    with pytest.raises(LabellingError, match=message):
        labels.label("GD23", label, rule, reason, today=DAY1)


def test_flags_point_at_labels_that_disagree_with_the_expected_decision_and_change_nothing(labels):
    right = next(i for i, item in labels.items.items() if item["decision"] == "PASS")
    labels.label(right, "FAIL", "3", "invents a fee", today=DAY1)
    assert any(f.startswith(f"{right}: labelled FAIL (rule 3), but its decision is right") for f in labels.flags())
    assert labels.state["first"][right]["label"] == "FAIL"


def test_the_relabel_waits_a_week_is_seeded_and_hides_the_first_labels(labels, tmp_path):
    label_all(labels)
    with pytest.raises(LabellingError, match="wait 7 days"):
        labels.relabel_sample(today=DAY1 + timedelta(days=6))
    later = DAY1 + timedelta(days=7)
    sample = labels.relabel_sample(today=later)
    assert len(sample) == 6 and sample == Labels(tmp_path).relabel_sample(today=later)   # the stored seed
    shown = labels.to_relabel(today=later)
    assert all(set(row) == {"id", "question", "answer"} for row in shown)


def test_judge_agreement_only_after_the_freeze_and_only_on_unchanged_labels(labels):
    label_all(labels)
    with pytest.raises(LabellingError, match="freeze the labels first"):
        labels.judge_agreement()
    later = DAY1 + timedelta(days=8)
    sample = labels.relabel_sample(today=later)
    for case_id in sample:
        first = labels.state["first"][case_id]
        flipped = ("FAIL", "1") if first["label"] == "PASS" and case_id == sample[0] else (first["label"], first["rule"])
        labels.label(case_id, flipped[0], flipped[1], "read again", today=later, second=True)
    with pytest.raises(LabellingError, match="settle every disagreement"):
        labels.freeze(today=later)
    if labels.disagreements():
        labels.settle(sample[0], "PASS", "the first reading was right")
    sha = labels.freeze(today=later)
    result = labels.judge_agreement()
    assert result["labels_sha"] == sha and result["n"] > 0 and result["relabel"].endswith(f"of {len(sample)}")
    with pytest.raises(LabellingError, match="frozen"):
        labels.label(sample[1], "PASS", "pass", "again", today=later)
    labels.state["first"][sample[1]]["label"] = "FAIL" if labels.state["first"][sample[1]]["label"] == "PASS" else "PASS"
    with pytest.raises(LabellingError, match="changed after the freeze"):
        labels.judge_agreement()


def test_labels_are_kept_on_disk(labels, tmp_path):
    labels.label("GD23", "PASS", "pass", "answers from the policy", today=DAY1)
    assert json.loads((tmp_path / "labels.json").read_text())["first"]["GD23"]["rule"] == "pass"
