"""End to end: runner, evaluate, record and replay, run records, redaction and the command line."""

import json

import pytest

from aiquality import PythonFunctionAgent, RecordedResponsesAgent, TeamConfig, evaluate_team, record_team
from aiquality.cli import EXIT_OK, EXIT_SETUP_ERROR, main
from aiquality.errors import SetupError
from aiquality.reporting import load_run_records
from aiquality.runner import Runner
from aiquality.test_data import GoldenCaseBuilder

from conftest import AGENT_CODE, BASE_CONFIG, GOLDEN_ROWS, write_team


def test_runner_keeps_going_after_one_failure():
    cases = [GoldenCaseBuilder(f"C{i}", f"q{i}").build() for i in range(5)]

    def agent(question):
        if question == "q2":
            raise TimeoutError("slow")
        return "ok"

    runs = Runner(PythonFunctionAgent(agent), max_error_rate=0.2).run(cases)
    assert [r.succeeded for r in runs] == [True, True, False, True, True]
    assert "TimeoutError" in runs[2].error


def test_too_many_failures_is_a_setup_error_not_a_quality_result():
    cases = [GoldenCaseBuilder(f"C{i}", f"q{i}").build() for i in range(4)]

    def broken(question):
        raise ConnectionError("agent down")

    with pytest.raises(SetupError, match="4 of 4 agent calls failed"):
        Runner(PythonFunctionAgent(broken), max_error_rate=0.2).run(cases)


def test_evaluate_writes_a_complete_run_record(team_folder, tmp_path, capsys):
    record = evaluate_team(TeamConfig.load(team_folder), output_dir=tmp_path / "runs")
    assert "required_phrases" in capsys.readouterr().out
    saved = load_run_records(tmp_path / "runs" / "run_records.jsonl")[0]
    assert saved.run_id == record.run_id and saved.schema_version == "1"
    assert saved.run_mode == "live" and saved.agent_version == "test-agent-1" and saved.case_count == 2
    assert {s["check"]: s["pass_rate"] for s in saved.summaries} == {"required_phrases": 1.0, "forbidden_phrases": 1.0}


def test_record_live_then_replay_without_the_live_agent(tmp_path):
    config = dict(BASE_CONFIG, agent={"adapter": "recorded_responses", "path": "recorded.jsonl"},
                  live_agent={"adapter": "python_function", "file": "agent.py", "function": "answer"})
    folder = write_team(tmp_path / "team", config, GOLDEN_ROWS, AGENT_CODE)
    team = TeamConfig.load(folder)
    path, summary = record_team(team)
    assert path == folder / "recorded.jsonl" and summary.written == 2

    (folder / "agent.py").unlink()            # the live agent is gone; the replay still works
    record = evaluate_team(team, output_dir=tmp_path / "runs", print_reports=False)
    assert record.run_mode == "recorded" and record.agent_version == "recorded:test-agent-1"


def test_personal_data_is_redacted_in_run_records(tmp_path):
    config = dict(BASE_CONFIG, checks={"forbidden_phrases": {"threshold": 1.0}})
    agent_code = 'def answer(q):\n    return "Write to jane.doe@example.com or call +91 98765 43210."\n'
    folder = write_team(tmp_path / "team", config, GOLDEN_ROWS, agent_code)
    evaluate_team(TeamConfig.load(folder), output_dir=tmp_path / "runs", print_reports=False)
    text = (tmp_path / "runs" / "run_records.jsonl").read_text()
    assert "jane.doe@example.com" not in text and "98765" not in text
    assert "[REDACTED-EMAIL]" in text and "[REDACTED-PHONE]" in text


def test_cli_new_team_then_evaluate(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["new-team", "claims_demo", "--format", "json"]) == EXIT_OK
    assert (tmp_path / "teams" / "claims_demo" / "team.json").is_file()
    assert main(["evaluate", "--team", "claims_demo"]) == EXIT_OK
    out = capsys.readouterr().out
    assert "MEETS" in out and "BELOW" not in out          # the starter team passes out of the box
    record = json.loads((tmp_path / "aiquality-runs" / "run_records.jsonl").read_text())
    assert record["team"] == "claims_demo"


def test_cli_setup_problems_exit_2(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["evaluate", "--team", "no_such_team"]) == EXIT_SETUP_ERROR
    assert "SETUP ERROR" in capsys.readouterr().err
    write_team(tmp_path / "teams" / "bad", dict(BASE_CONFIG, checks={}), GOLDEN_ROWS, AGENT_CODE)
    assert main(["evaluate", "--team", "bad"]) == EXIT_SETUP_ERROR


def test_cli_list_checks(capsys):
    assert main(["list-checks"]) == EXIT_OK
    assert "forbidden_phrases" in capsys.readouterr().out


def test_replay_agent_is_a_drop_in_agent(tmp_path):
    path = tmp_path / "r.jsonl"
    path.write_text(json.dumps({"question": "Hi?", "answer_text": "Hello"}) + "\n")
    assert RecordedResponsesAgent(path).answer("hi?").answer_text == "Hello"
