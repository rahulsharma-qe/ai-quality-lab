"""teams/aeroassist/labelling.py: labels for the judge's held-back answers, in an order that keeps them honest."""

import json
from datetime import date, timedelta

import pytest

import live_session as ls
from aiquality.judges.recorded import answer_sha
from labelling import LabellingError, Labels, seal_held_back_cache

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


# --- Labelling outside the notebook: an export of question and answer only, and labels that name the
# --- exact answer they were given for, with the person's own note kept word for word -----------------

def test_the_export_holds_only_number_question_answer_and_its_sha_in_a_fixed_order(labels, tmp_path):
    path = labels.export_for_labelling(tmp_path / "to_label.json")
    rows = json.loads(path.read_text(encoding="utf-8"))
    assert [row["item"] for row in rows] == list(range(1, 28))
    shas = [row["answer_sha"] for row in rows]
    by_case = [answer_sha(labels.items[i]["answer"]) for i in sorted(labels.items)]
    assert sorted(shas) == sorted(by_case) and shas != by_case          # shuffled by the stored seed
    assert all(set(row) == {"item", "question", "answer", "answer_sha"} for row in rows)
    assert "GD" not in path.read_text(encoding="utf-8").split('"question"')[0]      # no case ids
    assert rows == json.loads(labels.export_for_labelling(tmp_path / "again.json").read_text(encoding="utf-8"))


def test_a_label_names_the_answer_it_was_given_for_and_keeps_the_note_verbatim(labels, tmp_path):
    [first, *_] = json.loads(labels.export_for_labelling(tmp_path / "x.json").read_text(encoding="utf-8"))
    labels.label_answer(first["answer_sha"], "PASS", "pass", "P4 se sahi hai, 48 ghante", "Answers from P4.", today=DAY1)
    [row] = labels.state["first"].values()
    assert row["answer_sha"] == first["answer_sha"] and row["note"] == "P4 se sahi hai, 48 ghante"
    assert row["reason"] == "Answers from P4."
    with pytest.raises(LabellingError, match="no held-back answer"):
        labels.label_answer("0000000000000000", "PASS", "pass", "x", "x", today=DAY1)


def test_the_relabel_export_is_the_sample_only_in_a_new_order_and_takes_second_labels(labels, tmp_path):
    label_all(labels)
    later = DAY1 + timedelta(days=7)
    rows = json.loads(labels.export_for_relabelling(tmp_path / "again.json", today=later).read_text(encoding="utf-8"))
    sample = labels.relabel_sample(today=later)
    assert sorted(r["answer_sha"] for r in rows) == sorted(answer_sha(labels.items[i]["answer"]) for i in sample)
    assert all(set(r) == {"item", "question", "answer", "answer_sha"} for r in rows)
    first_order = [r["answer_sha"] for r in json.loads(labels.export_for_labelling(tmp_path / "x.json").read_text())
                   if r["answer_sha"] in {x["answer_sha"] for x in rows}]
    assert [r["answer_sha"] for r in rows] != first_order
    labels.label_answer(rows[0]["answer_sha"], "PASS", "pass", "theek hai", "Fine.", today=later, second=True)
    assert len(labels.state["second"]) == 1


def test_the_cached_verdicts_on_held_back_questions_move_to_the_sealed_file(tmp_path):
    cache = tmp_path / "verdict_cache.jsonl"
    cache.write_text(json.dumps({"case_id": "GD23", "verdict": "PASS"}) + "\n" +
                     json.dumps({"case_id": "GD01", "verdict": "FAIL"}) + "\n" +
                     json.dumps({"case_id": "GD61~name=Satyam Dixit", "verdict": "PASS"}) + "\n", encoding="utf-8")
    assert seal_held_back_cache(tmp_path) == {"moved": 2, "kept": 1}
    assert "GD23" not in cache.read_text() and "GD01" in cache.read_text()
    assert (tmp_path / "regraded_verdicts_sealed.jsonl").read_text().count("\n") == 2
    assert seal_held_back_cache(tmp_path) == {"moved": 0, "kept": 1}               # safe to run again


def test_the_guide_policies_and_rubric_are_frozen_with_the_labels(labels, monkeypatch, tmp_path):
    import labelling
    guide = tmp_path / "guide.md"
    guide.write_text("the guide", encoding="utf-8")
    monkeypatch.setattr(labelling, "FROZEN_TEXTS", {"labelling_guide.md": guide,
                                                    "policies.md": labelling.TEAM_FOLDER / "policies.md"})
    label_all(labels)
    assert set(labels.state["texts"]) == {"labelling_guide.md", "policies.md"}
    later = DAY1 + timedelta(days=8)
    for case_id in labels.relabel_sample(today=later):
        first = labels.state["first"][case_id]
        labels.label(case_id, first["label"], first["rule"], "read again", today=later, second=True)
    guide.write_text("the guide, edited", encoding="utf-8")
    with pytest.raises(LabellingError, match="labelling_guide.md changed"):
        labels.freeze(today=later)
    guide.write_text("the guide", encoding="utf-8")
    assert labels.freeze(today=later)


def test_the_guide_says_disclosure_and_fairness_are_not_rubric_rules():
    import labelling
    text = (labelling.TEAM_FOLDER / "labelling_guide.md").read_text(encoding="utf-8")
    assert "Label against the rubric only" in text and "not rubric rules" in text
