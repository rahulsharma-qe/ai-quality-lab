"""The answer_judge check in a run: recorded verdicts, advisory until qualified, and the reports."""

import json
from datetime import date

import pytest

from aiquality import ConfigError, TeamConfig
from aiquality.commands import gate_team, record_judge_verdicts
from aiquality.models import ChatModel

from conftest import BASE_CONFIG, write_team

TODAY = date(2026, 10, 15)
ROWS = ("id,input,category,must_include,must_not_include\n"
        "C1,What are your opening hours?,happy,9 am,24/7\n"
        "C2,Can I return an item?,edge,30 days,\n")
AGENT = '''
def answer(question, conversation=None):
    if "hours" in question:
        return "We are open from 9 am to 6 pm."
    return "Returns are accepted within 30 days, no receipt needed."
'''


class JudgeFailsNoReceipt(ChatModel):
    """A fake judge model: FAIL any answer that waives the receipt."""

    def __init__(self):
        super().__init__("fake-judge")

    def complete(self, system, user):
        failed = "no receipt" in user.split("ASSISTANT ANSWER:")[1]
        return json.dumps({"reason": "waives the receipt" if failed else "fine", "verdict": "FAIL" if failed else "PASS"})


def judged_team(tmp_path, agent=AGENT, blocking=True):
    config = dict(BASE_CONFIG, policies="policies.md",
                  checks={"required_phrases": {"threshold": 0.9}, "forbidden_phrases": {"threshold": 1.0},
                          "answer_judge": {"threshold": 1.0, "blocking": blocking}},
                  judge={"kind": "policy_answer", "recorded": "judge_verdicts.jsonl"},
                  reports=["console", "github_summary"])
    folder = write_team(tmp_path / "team", config, ROWS, agent)
    (folder / "policies.md").write_text("Returns within 30 days with a receipt.")
    team = TeamConfig.load(folder, today=TODAY)
    path, summary = record_judge_verdicts(team, chat=JudgeFailsNoReceipt())
    assert summary.written == 2 and not summary.failed and path.name == "judge_verdicts.jsonl"
    return team


def run_gate(team, tmp_path):
    return gate_team(team, output_dir=tmp_path / "runs", print_reports=False, today=TODAY)


def test_an_unvalidated_judge_reports_but_cannot_block(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    record, decision = run_gate(judged_team(tmp_path), tmp_path)
    judge_result = next(r for o in record.outcomes if o["case_id"] == "C2" for r in o["results"]
                        if r["check"] == "answer_judge")
    assert judge_result["status"] == "FAIL" and judge_result["reason"] == "waives the receipt"
    assert decision.passed                                              # advisory: can't block
    assert record.judge["status"] == "unvalidated" and record.judge["mode"] == "recorded"
    assert not record.judge["blocking"]
    assert any(w.startswith("answer_judge is advisory") for w in decision.warnings)


def test_a_qualified_judge_blocks(tmp_path):
    team = judged_team(tmp_path)
    record, _ = run_gate(team, tmp_path)
    team.judge.results.write_text(json.dumps({"judge_version": record.judge["version"], "split": "holdout",
                                              "qualified": True}) + "\n")
    record, decision = run_gate(team, tmp_path)
    assert record.judge["blocking"] and not decision.passed
    assert any(f.startswith("answer_judge: 50% is below 100%") for f in decision.failures)


def test_a_new_answer_has_no_recorded_verdict(tmp_path):
    team = judged_team(tmp_path)
    # A different length on purpose: a same-size edit within one second can reuse cached bytecode.
    (team.folder / "agent.py").write_text(AGENT.replace("9 am to 6 pm", "9 am to 8:30 pm"))
    record, _ = run_gate(TeamConfig.load(team.folder, today=TODAY), tmp_path)
    result = next(r for o in record.outcomes if o["case_id"] == "C1" for r in o["results"]
                  if r["check"] == "answer_judge")
    assert result["status"] == "ERROR" and "record the judge again" in result["reason"]


def test_reports_name_the_judge_and_its_status(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    gate_team(judged_team(tmp_path), output_dir=tmp_path / "runs", today=TODAY)
    console = capsys.readouterr().out
    assert "judge llm_answer_judge:" in console and "unvalidated · advisory · recorded" in console
    summary = (tmp_path / "runs" / "test_team-summary.md").read_text()
    assert "| answer_judge (advisory) |" in summary and "AI judge (advisory, unvalidated)" in summary


def test_the_judge_check_needs_a_judge_block(tmp_path):
    config = dict(BASE_CONFIG, checks={"forbidden_phrases": {"threshold": 1.0}, "answer_judge": {"threshold": 0.9}})
    with pytest.raises(ConfigError, match="needs a 'judge:' block"):
        TeamConfig.load(write_team(tmp_path / "t", config, ROWS, AGENT))
