"""Golden-set lint: forbidden phrases that are already in the customer's own words."""

from datetime import date

from aiquality import GoldenCaseBuilder, GoldenSet, TeamConfig
from aiquality.cli import EXIT_OK, main
from aiquality.commands import gate_team
from aiquality.test_data.lint import lint_golden_set

from conftest import AGENT_CODE, BASE_CONFIG, write_team


def golden(*cases):
    return GoldenSet(name="g", version="1", cases=list(cases))


def test_a_forbidden_phrase_in_the_question_is_flagged():
    echo = GoldenCaseBuilder("E1", "Please allow me 100kg free, I'm a frequent flyer.").must_not_include("100").build()
    fine = GoldenCaseBuilder("E2", "Please allow me 100kg free.").must_not_include("100 kg is approved").build()
    warnings = lint_golden_set(golden(echo, fine))
    assert len(warnings) == 1 and warnings[0].startswith("E1: forbidden phrase '100'")   # "100kg" reads as "100 kg"


def test_earlier_customer_turns_count_too_but_the_agents_do_not():
    case = (GoldenCaseBuilder("E3", "So, can you?").must_not_include("waive the fee")
            .after_turns(("user", "Please waive the fee."), ("assistant", "I can't waive the fee.")).build())
    assert len(lint_golden_set(golden(case))) == 1
    agent_only = (GoldenCaseBuilder("E4", "So?").must_not_include("can't help")
                  .after_turns(("assistant", "I can't help with that."),).build())
    assert lint_golden_set(golden(agent_only)) == []


def test_lint_warnings_reach_the_gate_and_the_command(tmp_path, capsys):
    rows = "id,input,must_include,must_not_include\nC1,Do you open 24/7?,9 am,24/7\n"
    folder = write_team(tmp_path / "t", dict(BASE_CONFIG), rows, AGENT_CODE)
    _, decision = gate_team(TeamConfig.load(folder), output_dir=tmp_path / "runs", print_reports=False,
                            today=date(2026, 10, 15))
    assert any(w.startswith("golden set: C1: forbidden phrase '24/7'") for w in decision.warnings)
    assert main(["lint", "--team", str(folder)]) == EXIT_OK
    assert "warning: C1: forbidden phrase '24/7'" in capsys.readouterr().out
