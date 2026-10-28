"""What the gate must not let slip: a misspelled column, a check with nothing to check, a priority
written in another case, an answer missing from the recording."""

import json

from aiquality.cli import EXIT_QUALITY_FAILURE, EXIT_SETUP_ERROR, main

from conftest import AGENT_CODE, BASE_CONFIG, GOLDEN_ROWS, write_team


def test_a_misspelled_column_is_a_setup_error_that_names_the_right_one(tmp_path, capsys):
    rows = GOLDEN_ROWS.replace("must_include,", "must_includ,")
    folder = write_team(tmp_path / "t", dict(BASE_CONFIG), rows, AGENT_CODE)
    assert main(["gate", "--team", str(folder), "--output-dir", str(tmp_path / "out")]) == EXIT_SETUP_ERROR
    err = capsys.readouterr().err
    assert "'must_includ' is not a field: did you mean 'must_include'?" in err and "such as note_must_includ)" in err


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


def test_a_secret_in_the_agent_url_is_refused_without_printing_it(tmp_path, capsys):
    config = dict(BASE_CONFIG, agent={"adapter": "http_endpoint",
                                      "url": "https://qa:hunter2pass@agent.example/chat?key=sk-ant-123"})
    folder = write_team(tmp_path / "t", config, GOLDEN_ROWS)
    assert main(["gate", "--team", str(folder), "--output-dir", str(tmp_path / "out")]) == EXIT_SETUP_ERROR
    err = capsys.readouterr().err
    assert "'agent.url' holds a secret (https://***@agent.example/chat?key=***)" in err
    assert "hunter2pass" not in err and "sk-ant-123" not in err


def test_setup_problems_are_messages_with_exit_2_not_tracebacks(tmp_path, capsys, monkeypatch):
    assert main(["new-team", "again", "--teams-dir", str(tmp_path)]) == 0
    assert main(["new-team", "again", "--teams-dir", str(tmp_path)]) == EXIT_SETUP_ERROR
    assert "already exists: pick another name" in capsys.readouterr().err
    import builtins
    real_import = builtins.__import__

    def no_anthropic(name, *args, **kwargs):
        if name == "anthropic":
            raise ModuleNotFoundError("No module named 'anthropic'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_anthropic)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    from aiquality.models.chat_model import AnthropicChat
    from aiquality.errors import SetupError
    import pytest
    with pytest.raises(SetupError, match="the model client isn't installed"):
        AnthropicChat("a-model")


def test_query_names_that_only_contain_a_secret_word_are_left_alone():
    from aiquality.adapters.http_endpoint_agent import shown_url
    assert shown_url("https://x.example/a?keyword=refund&monkey=1&postcode=560043") == \
        "https://x.example/a?keyword=refund&monkey=1&postcode=560043"
    assert shown_url("https://x.example/a?apiKey=s3cr3t&lang=en") == "https://x.example/a?apiKey=***&lang=en"


def test_ordinary_extra_columns_are_kept_as_notes():
    from aiquality.test_data.golden_case import GoldenCase
    case = GoldenCase.from_dict({"id": "C1", "input": "q", "sub_category": "a", "subcategory": "b",
                                 "expected_tools": "c", "expected_behavior": "d", "dimension": "e", "clients": "f"})
    assert set(case.extra) == {"sub_category", "subcategory", "expected_tools", "expected_behavior", "dimension",
                               "clients"}


def test_ordinary_query_names_in_the_agent_url_are_allowed():
    from aiquality.adapters.http_endpoint_agent import shown_url
    url = "https://x.example/a?keyword=refund&tokenizer=bpe&key_id=public&postcode=560043"
    assert shown_url(url) == url
