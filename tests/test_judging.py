"""A team's judge: the config block, validation against labels, and status per judge version."""

import json

import pytest

from aiquality import ConfigError, GoldenCaseBuilder, TeamConfig
from aiquality.cli import EXIT_OK, EXIT_QUALITY_FAILURE, main
from aiquality.errors import SetupError
from aiquality.judges import PhraseJudge
from aiquality.judges.validation import LabelledAnswer, judge_status, render_validation, validate_judge
from aiquality.judging import build_judge, team_judge_status, validate_team_judge
from aiquality.models import ChatModel

from conftest import AGENT_CODE, BASE_CONFIG, GOLDEN_ROWS, write_team

def held_back(number: int, label: str) -> dict:
    """A held-back labelled answer: a PASS says 'taxes'; a FAIL promises a full refund."""
    answer = "Only taxes are refundable." if label == "PASS" else "Sure, full refund!"
    return {"id": f"H{label[0]}{number}", "input": "Refund after 3 days?", "answer": answer, "human_label": label,
            "category": "edge", "split": "holdout", "must_include": ["taxes"]}


# Five of each in the held-back half: the fewest a qualification takes.
LABELS = {"cases": [held_back(n, "PASS") for n in range(1, 6)] + [held_back(n, "FAIL") for n in range(1, 6)] + [
    {"id": "L3", "input": "Pets?", "answer": "A human agent will help.", "human_label": "PASS",
     "category": "out_of_scope", "split": "tune"},
    {"id": "L4", "input": "Pets?", "answer": "not labelled yet", "split": "holdout"},
]}


class VerdictByAnswer(ChatModel):
    """A fake judge model: FAIL when the answer contains 'full refund', otherwise PASS."""

    def __init__(self):
        super().__init__("fake-judge-model")

    def complete(self, system, user):
        failed = "full refund" in user.split("ASSISTANT ANSWER:")[1]
        return json.dumps({"reason": "scripted", "verdict": "FAIL" if failed else "PASS"})


def judged_team(tmp_path, **judge):
    folder = write_team(tmp_path / "team", dict(BASE_CONFIG, policies="policies.md",
                                                judge={"kind": "policy_answer", "labels": "labels.json", **judge}),
                        GOLDEN_ROWS, AGENT_CODE)
    (folder / "policies.md").write_text("Full refund within 24 hours of booking; after that, taxes only.")
    (folder / "labels.json").write_text(json.dumps(LABELS))
    (folder / "rubric.md").write_text("Grade against the policy. Return JSON.")
    return TeamConfig.load(folder)


def test_judge_block_problems_are_listed(tmp_path):
    folder = write_team(tmp_path / "t", dict(BASE_CONFIG, judge={"kind": "policy_answer", "labels": "nope.json",
                                                                  "colour": "blue"}), GOLDEN_ROWS, AGENT_CODE)
    with pytest.raises(ConfigError) as error:
        TeamConfig.load(folder)
    message = str(error.value)
    assert "'judge.colour' is not a judge setting" in message
    assert "add 'policies: <file>'" in message and "judge labels file not found" in message


def test_validation_is_saved_and_decides_the_status(tmp_path):
    config = judged_team(tmp_path, rubric="rubric.md", rubric_version="r1")
    judge = build_judge(config, chat=VerdictByAnswer())
    assert judge.version.startswith("llm_answer_judge:") and ":r1:" in judge.version
    assert team_judge_status(config, judge) == "unvalidated"
    run = validate_team_judge(config, "holdout", judge=judge)
    assert run.overall["catch_rate"] == 1.0 and run.overall["leave_alone_rate"] == 1.0 and run.qualified
    assert run.skipped_unlabelled == 1
    assert team_judge_status(config, judge) == "qualified"
    assert judge_status("some-other-version", config.judge.results) == "unvalidated"


def test_a_tuning_run_is_not_a_qualification(tmp_path):
    config = judged_team(tmp_path)
    run = validate_team_judge(config, "tune", judge=build_judge(config, chat=VerdictByAnswer()))
    assert run.qualified is None and team_judge_status(config, build_judge(config, chat=VerdictByAnswer())) \
        == "unvalidated"


def test_validate_judge_command_key_free_with_the_phrase_judge(tmp_path, capsys):
    config = judged_team(tmp_path)
    # The phrase judge passes the answers that say 'taxes' and fails the others: it agrees with the person.
    assert main(["validate-judge", "--team", str(config.folder), "--split", "holdout", "--kind", "phrase"]) == EXIT_OK
    assert "QUALIFIED to gate" in capsys.readouterr().out
    (config.folder / "labels.json").write_text(json.dumps({"cases": [dict(case, human_label="FAIL")
                                                                     for case in LABELS["cases"][:10]]}))
    assert main(["validate-judge", "--team", str(config.folder), "--split", "holdout",
                 "--kind", "phrase"]) == EXIT_QUALITY_FAILURE


def test_no_judge_block_is_a_clear_config_error(tmp_path):
    config = TeamConfig.load(write_team(tmp_path / "t", dict(BASE_CONFIG), GOLDEN_ROWS, AGENT_CODE))
    with pytest.raises(ConfigError, match="no 'judge' block"):
        build_judge(config)


def test_labelled_answers_need_their_own_ids():
    case = GoldenCaseBuilder("L1", "q").build()
    with pytest.raises(SetupError, match="repeated: L1"):
        validate_judge(PhraseJudge(), [LabelledAnswer(case, "a", "PASS"), LabelledAnswer(case, "b", "FAIL")], "tune")


class FailingOnRefunds(ChatModel):
    """A judge model whose calls fail for every answer that promises a full refund: an outage, not a verdict."""

    def __init__(self):
        super().__init__("fake-judge-model")

    def complete(self, system, user):
        if "full refund" in user.split("ASSISTANT ANSWER:")[1]:
            raise ConnectionError("network down")
        return VerdictByAnswer().complete(system, user)


def test_two_labels_can_not_qualify_a_judge(tmp_path):
    config = judged_team(tmp_path)
    (config.folder / "labels.json").write_text(json.dumps({"cases": [held_back(1, "PASS"), held_back(1, "FAIL")]}))
    run = validate_team_judge(config, "holdout", judge=build_judge(config, chat=VerdictByAnswer()))
    assert run.overall["agreement"] == 1.0 and run.qualified is False
    assert run.too_few_labels == "1 PASS and 1 FAIL labels; a qualification needs at least 5 of each"


def test_only_the_held_back_half_can_qualify(tmp_path):
    config = judged_team(tmp_path)
    judge = build_judge(config, chat=VerdictByAnswer())
    run = validate_team_judge(config, "all", judge=judge)
    assert run.qualified is None and team_judge_status(config, judge) == "unvalidated"
    assert "not a qualification, which only the held-back half can give" in render_validation(run)


def test_a_run_with_failed_calls_does_not_count_or_replace_a_result(tmp_path, monkeypatch):
    config = judged_team(tmp_path)
    judge = build_judge(config, chat=VerdictByAnswer())
    assert validate_team_judge(config, "holdout", judge=judge).qualified
    monkeypatch.setattr("aiquality.judges.validation.time.sleep", lambda seconds: None)
    judge.chat = FailingOnRefunds()          # the five FAIL answers can't be graded; the five PASS ones can
    run = validate_team_judge(config, "holdout", judge=judge)
    assert run.qualified is None and run.not_counted.startswith("5 of 10 judge calls failed")
    assert team_judge_status(config, judge) == "qualified"                 # the outage replaced nothing


def test_changed_labels_or_policies_make_the_judge_unvalidated(tmp_path):
    config = judged_team(tmp_path)
    judge = build_judge(config, chat=VerdictByAnswer())
    validate_team_judge(config, "holdout", judge=judge)
    assert team_judge_status(config, judge) == "qualified"
    labels = json.loads((config.folder / "labels.json").read_text())
    labels["cases"][0]["human_label"] = "FAIL"
    (config.folder / "labels.json").write_text(json.dumps(labels))
    assert team_judge_status(config, judge) == "unvalidated"
    (config.folder / "policies.md").write_text("No refunds at all.")
    assert build_judge(config, chat=VerdictByAnswer()).version != judge.version


def test_each_held_back_measurement_is_counted_and_shown(tmp_path):
    config = judged_team(tmp_path)
    judge = build_judge(config, chat=VerdictByAnswer())
    assert validate_team_judge(config, "holdout", judge=judge).measurement == 1
    second = validate_team_judge(config, "holdout", judge=judge)
    assert second.measurement == 2 and "held-back measurement 2 of this judge version" in render_validation(second)
