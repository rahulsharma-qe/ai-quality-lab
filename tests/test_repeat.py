"""Repeat checks: ask chosen cases several times, count each check's passes, list what varies."""

import itertools

import pytest

from aiquality import PythonFunctionAgent, TeamConfig, evaluate_team
from aiquality.cli import EXIT_OK, EXIT_SETUP_ERROR, main
from aiquality.commands import repeat_team
from aiquality.errors import ConfigError, SetupError
from aiquality.judges.base import Judge, JudgeVerdict
from aiquality.reporting import (RepeatRow, changed_cases, load_repeat_rows, render_repeats, summarise_repeats)

from conftest import AGENT_CODE, BASE_CONFIG, GOLDEN_ROWS, write_team

FLAKY_AGENT = '''
import itertools
AGENT_VERSION = "flaky-1"
_hours = itertools.cycle(["We are open from 9 am to 6 pm.", "We are open 24/7."])

def answer(question):
    if "hours" in question:
        return next(_hours)
    return "Returns are accepted within 30 days."
'''


def _row(case_id, repeat, **statuses):
    results = [{"check": check, "status": status, "reason": "", "flags": []} for check, status in statuses.items()]
    return RepeatRow(case_id, repeat, "agent-1", "answer", None, None, results)


def test_summary_counts_each_check_on_its_own():
    rows = [_row("C1", 1, required_phrases="PASS", answer_judge="PASS"),
            _row("C1", 2, required_phrases="PASS", answer_judge="FAIL"),
            _row("C1", 3, required_phrases="PASS", answer_judge="PASS"),
            _row("C2", 1, required_phrases="NOT_APPLICABLE", answer_judge="FAIL"),
            _row("C2", 2, required_phrases="NOT_APPLICABLE", answer_judge="FAIL"),
            _row("C2", 3, required_phrases="NOT_APPLICABLE", answer_judge="FAIL")]
    summary = summarise_repeats(rows)
    assert summary.times == 3 and summary.case_ids == ["C1", "C2"]
    assert summary.count("C1", "answer_judge").text() == "2/3 *"
    assert summary.count("C1", "required_phrases").text() == "3/3"
    assert summary.count("C2", "required_phrases").text() == "-"          # never gave a verdict
    assert summary.varying_cases("answer_judge") == ["C1"]
    assert summary.judged_cases("required_phrases") == ["C1"]
    text = render_repeats(summary)
    assert "answer_judge: 1 of 2 cases: C1" in text and "required_phrases: 0 of 1 cases" in text


def test_failed_calls_are_shown_next_to_the_case():
    rows = [_row("C1", 1, required_phrases="PASS"),
            RepeatRow("C1", 2, "agent-1", None, "TimeoutError: slow", None, [])]
    summary = summarise_repeats(rows)
    assert summary.errors == {"C1": 1}
    assert "(1 call(s) failed)" in render_repeats(summary)


def test_repeat_team_asks_each_case_times_and_saves_every_answer(tmp_path):
    folder = write_team(tmp_path / "team", dict(BASE_CONFIG), GOLDEN_ROWS, FLAKY_AGENT)
    output = tmp_path / "repeat.jsonl"
    path, summary = repeat_team(TeamConfig.load(folder), ["C1", "C2"], times=3, output_path=output)
    rows = load_repeat_rows(path)
    assert path == output and len(rows) == 6
    assert [(r.case_id, r.repeat) for r in rows[:2]] == [("C1", 1), ("C2", 1)]
    assert rows[0].agent_version == "flaky-1" and rows[0].tool_calls is None
    # the hours answer alternates: right, wrong, right
    assert summary.count("C1", "forbidden_phrases").text() == "2/3 *"
    assert summary.count("C2", "forbidden_phrases").text() == "3/3"
    assert summary.varying_cases("forbidden_phrases") == ["C1"]

    repeat_team(TeamConfig.load(folder), ["C2"], times=1, output_path=output)
    assert len(load_repeat_rows(output)) == 1           # each run starts the file afresh


def test_a_given_judge_grades_every_repeat(tmp_path):
    class AlternatingJudge(Judge):
        version = "alternating-1"
        _verdicts = itertools.cycle([True, False])

        def verdict(self, case, answer_text):
            return JudgeVerdict(next(self._verdicts), "alternating")

    config = dict(BASE_CONFIG, judge={"kind": "phrase"},
                  checks={**BASE_CONFIG["checks"], "answer_judge": {"threshold": 0.8}})
    folder = write_team(tmp_path / "team", config, GOLDEN_ROWS, AGENT_CODE)
    _, summary = repeat_team(TeamConfig.load(folder), ["C1"], times=2, output_path=tmp_path / "r.jsonl",
                             judge=AlternatingJudge())
    assert summary.count("C1", "answer_judge").text() == "1/2 *"
    assert summary.count("C1", "required_phrases").text() == "2/2"


def test_repeat_setup_problems_are_config_errors(tmp_path, team_folder):
    config = TeamConfig.load(team_folder)
    with pytest.raises(SetupError, match="no case with id C9"):
        repeat_team(config, ["C1", "C9"], output_path=tmp_path / "r.jsonl")
    with pytest.raises(SetupError, match="no cases to repeat"):
        repeat_team(config, [], output_path=tmp_path / "r.jsonl")
    with pytest.raises(SetupError, match="--times"):
        repeat_team(config, ["C1"], times=0, output_path=tmp_path / "r.jsonl")
    recorded = write_team(tmp_path / "recorded", dict(BASE_CONFIG, agent={"adapter": "recorded_responses",
                                                                          "path": "recorded.jsonl"}), GOLDEN_ROWS)
    (recorded / "recorded.jsonl").write_text("", encoding="utf-8")
    with pytest.raises(ConfigError, match="recorded answers are the same every time"):
        repeat_team(TeamConfig.load(recorded), ["C1"], output_path=tmp_path / "r.jsonl")


def test_changed_cases_lists_cases_whose_result_differs(team_folder, tmp_path):
    config = TeamConfig.load(team_folder)

    def run(answer_function):
        return evaluate_team(config, agent=PythonFunctionAgent(answer_function), output_dir=tmp_path / "runs",
                             print_reports=False)

    before = run(lambda q: "We are open from 9 am to 6 pm." if "hours" in q else "Returns: 30 days.")
    after = run(lambda q: "We are open 24/7." if "hours" in q else "Returns: 30 days.")
    assert changed_cases(before, after) == ["C1"]
    assert changed_cases(before, before) == []


def test_cli_repeat_with_cases_and_changed_between(tmp_path, capsys):
    folder = write_team(tmp_path / "team", dict(BASE_CONFIG), GOLDEN_ROWS, AGENT_CODE)
    runs_a, runs_b = tmp_path / "a", tmp_path / "b"
    assert main(["evaluate", "--team", str(folder), "--output-dir", str(runs_a)]) == EXIT_OK
    (folder / "agent.py").write_text(FLAKY_AGENT.replace('"We are open from 9 am to 6 pm.", ', ""), encoding="utf-8")
    assert main(["evaluate", "--team", str(folder), "--output-dir", str(runs_b)]) == EXIT_OK
    capsys.readouterr()
    code = main(["repeat", "--team", str(folder), "--cases", "C2", "--changed-between", str(runs_a), str(runs_b),
                 "--times", "2", "--output-dir", str(tmp_path / "out")])
    out = capsys.readouterr().out
    assert code == EXIT_OK
    assert "1 cases changed between the two runs: C1" in out
    assert "asking 2 cases 2 times: 4 answers" in out
    assert len(load_repeat_rows(tmp_path / "out" / "repeat_check.jsonl")) == 4


def test_cli_repeat_unknown_case_exits_2(team_folder, tmp_path, capsys):
    code = main(["repeat", "--team", str(team_folder), "--cases", "C9", "--output-dir", str(tmp_path)])
    assert code == EXIT_SETUP_ERROR
    assert "no case with id C9" in capsys.readouterr().err
