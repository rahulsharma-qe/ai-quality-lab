"""A team's judge: the config block, validation against labels, and status per judge version."""

import json

import pytest

from aiquality import ConfigError, TeamConfig
from aiquality.cli import EXIT_OK, EXIT_QUALITY_FAILURE, main
from aiquality.judges.validation import judge_status
from aiquality.judging import build_judge, team_judge_status, validate_team_judge
from aiquality.models import ChatModel

from conftest import AGENT_CODE, BASE_CONFIG, GOLDEN_ROWS, write_team

LABELS = {"cases": [
    {"id": "L1", "input": "Refund after 3 days?", "answer": "Only taxes are refundable.", "human_label": "PASS",
     "category": "edge", "split": "holdout", "must_include": ["taxes"]},
    {"id": "L2", "input": "Refund after 3 days?", "answer": "Sure, full refund!", "human_label": "FAIL",
     "category": "edge", "split": "holdout", "must_include": ["taxes"]},
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
    # The phrase judge passes L1 (says 'taxes') and fails L2 (doesn't): both agree with the person.
    assert main(["validate-judge", "--team", str(config.folder), "--split", "holdout", "--kind", "phrase"]) == EXIT_OK
    assert "QUALIFIED to gate" in capsys.readouterr().out
    (config.folder / "labels.json").write_text(json.dumps({"cases": [dict(LABELS["cases"][0], human_label="FAIL")]}))
    assert main(["validate-judge", "--team", str(config.folder), "--split", "holdout",
                 "--kind", "phrase"]) == EXIT_QUALITY_FAILURE


def test_no_judge_block_is_a_clear_config_error(tmp_path):
    config = TeamConfig.load(write_team(tmp_path / "t", dict(BASE_CONFIG), GOLDEN_ROWS, AGENT_CODE))
    with pytest.raises(ConfigError, match="no 'judge' block"):
        build_judge(config)
