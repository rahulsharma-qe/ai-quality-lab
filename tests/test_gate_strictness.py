"""What the gate must not let slip: a misspelled column, a check with nothing to check, a priority
written in another case, an answer missing from the recording."""

import json

from aiquality.cli import EXIT_QUALITY_FAILURE, EXIT_SETUP_ERROR, main

from conftest import AGENT_CODE, BASE_CONFIG, GOLDEN_ROWS, write_team


def test_a_misspelled_column_is_a_setup_error_that_names_the_right_one(tmp_path, capsys):
    rows = GOLDEN_ROWS.replace("must_include,", "must_includ,")
    folder = write_team(tmp_path / "t", dict(BASE_CONFIG), rows, AGENT_CODE)
    assert main(["gate", "--team", str(folder), "--output-dir", str(tmp_path / "out")]) == EXIT_SETUP_ERROR
    assert "'must_includ' is not a field: did you mean 'must_include'?" in capsys.readouterr().err


def test_a_blocking_check_with_no_case_fails_the_gate(tmp_path, capsys):
    rows = "id,input,category,must_not_include\nC1,What are your opening hours?,happy,24/7\n"
    folder = write_team(tmp_path / "t", dict(BASE_CONFIG), rows, AGENT_CODE)
    assert main(["gate", "--team", str(folder), "--output-dir", str(tmp_path / "out")]) == EXIT_QUALITY_FAILURE
    assert "required_phrases: no applicable case, so no evidence it passes (it blocks" in capsys.readouterr().out


def test_a_priority_bar_counts_a_priority_written_in_capitals(tmp_path, capsys):
    rows = ("id,input,category,priority,must_include,must_not_include\n"
            "C1,What are your opening hours?,happy,High,9 am,24/7\n"
            + "".join(f"C{n},Can I return an item?,edge,low,30 days,never\n" for n in range(2, 7)))
    config = dict(BASE_CONFIG, priority_bars={"high": 1.0})        # 5 of 6 pass: above the 0.9 average
    agent = AGENT_CODE.replace("We are open from 9 am to 6 pm.", "We are open all day.")
    folder = write_team(tmp_path / "t", config, rows, agent)
    assert main(["gate", "--team", str(folder), "--output-dir", str(tmp_path / "out")]) == EXIT_QUALITY_FAILURE
    assert "high-priority cases: 1 of 1 failed (C1)" in capsys.readouterr().out


def test_an_answer_missing_from_the_recording_is_a_setup_error(tmp_path, capsys):
    recording = tmp_path / "t" / "recorded.jsonl"
    config = dict(BASE_CONFIG, agent={"adapter": "recorded_responses", "path": "recorded.jsonl"})
    folder = write_team(tmp_path / "t", config, GOLDEN_ROWS)
    recording.write_text(json.dumps({"case_id": "C1", "question": "What are your opening hours?",
                                     "answer_text": "9 am to 6 pm"}) + "\n")
    assert main(["gate", "--team", str(folder), "--output-dir", str(tmp_path / "out")]) == EXIT_SETUP_ERROR
    assert "1 case(s) have no recorded answer (C2): the golden set changed since the recording" in \
        capsys.readouterr().err
