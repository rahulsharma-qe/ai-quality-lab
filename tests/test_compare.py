"""Comparing two runs: fixed, newly failing and still failing cases, and the compare command."""

import pytest

from aiquality import PythonFunctionAgent, TeamConfig, compare_runs, evaluate_team, pick_run
from aiquality.cli import EXIT_OK, EXIT_QUALITY_FAILURE, EXIT_SETUP_ERROR, main
from aiquality.errors import SetupError
from aiquality.reporting import render_comparison, render_comparison_markdown

from conftest import BASE_CONFIG, write_team

ROWS = ("id,input,priority,must_include,must_not_include\n"
        "C1,What are your opening hours?,high,9 am,24/7\n"
        "C2,Can I return an item?,medium,30 days,\n"
        "C3,Do you deliver on Sundays?,low,human,\n")


def old_agent(question):
    if "hours" in question:
        return "We are open from 9 am."
    return "Sorry, I don't know."                       # misses C2 and C3


def new_agent(question):
    if "hours" in question:
        return "We are open 24/7."                       # C1 now breaks
    if "return" in question:
        return "Returns within 30 days."                # C2 fixed
    return "Sorry, I don't know."                       # C3 still failing


def runs(tmp_path, rows=ROWS, new_rows=None):
    """Run the old agent, then the new one, into two run-record files; return both records."""
    config = TeamConfig.load(write_team(tmp_path / "team", dict(BASE_CONFIG), rows))
    before = evaluate_team(config, agent=PythonFunctionAgent(old_agent, version="v1"),
                           output_dir=tmp_path / "before", print_reports=False)
    if new_rows:
        config = TeamConfig.load(write_team(tmp_path / "team2", dict(BASE_CONFIG), new_rows))
    after = evaluate_team(config, agent=PythonFunctionAgent(new_agent, version="v2"),
                          output_dir=tmp_path / "after", print_reports=False)
    return before, after


def test_cases_are_sorted_into_fixed_newly_failing_and_still_failing(tmp_path):
    comparison = compare_runs(*runs(tmp_path))
    assert [c.case_id for c in comparison.fixed] == ["C2"]
    assert [c.case_id for c in comparison.newly_failing] == ["C1"]
    assert [c.case_id for c in comparison.still_failing] == ["C3"]
    assert set(comparison.newly_failing[0].failed_after) == {"required_phrases", "forbidden_phrases"}
    assert comparison.has_new_failures


def test_rates_and_both_renderings(tmp_path):
    comparison = compare_runs(*runs(tmp_path))
    required = next(c for c in comparison.checks if c.check == "required_phrases")
    assert (required.before_rate, required.after_rate, required.points) == (1 / 3, 1 / 3, 0)
    text = render_comparison(comparison)
    assert "newly failing (regressions): 1" in text and "C1" in text
    markdown = render_comparison_markdown(comparison)
    assert "| forbidden_phrases | 100% | 0% | -100 pts | 100% |" in markdown
    assert "- **fixed:** C2 (medium)" in markdown


def test_new_cases_are_listed_separately(tmp_path):
    extra = ROWS + "C4,Do you sell gift cards?,low,gift card,\n"
    comparison = compare_runs(*runs(tmp_path, new_rows=extra))
    assert comparison.only_after == ["C4"] and [c.case_id for c in comparison.new_cases_failing] == ["C4"]
    assert "C4" not in [c.case_id for c in comparison.newly_failing]       # new, so not a regression


def test_pick_run_by_default_last_or_by_id(tmp_path):
    before, after = runs(tmp_path)
    evaluate_team(TeamConfig.load(tmp_path / "team"), agent=PythonFunctionAgent(new_agent),
                  output_dir=tmp_path / "before", print_reports=False)        # a second run in the same file
    assert pick_run(tmp_path / "before", before.run_id).run_id == before.run_id
    assert pick_run(tmp_path / "before").run_id != before.run_id
    with pytest.raises(SetupError, match="no run nope"):
        pick_run(tmp_path / "before", "nope")
    with pytest.raises(SetupError, match="no run records"):
        pick_run(tmp_path / "missing")


def test_compare_command_exit_codes_and_markdown(tmp_path, capsys):
    runs(tmp_path)
    before, after = str(tmp_path / "before"), str(tmp_path / "after" / "run_records.jsonl")
    markdown = tmp_path / "comparison.md"
    assert main(["compare", before, after, "--markdown", str(markdown)]) == EXIT_OK
    assert "fixed: 1" in capsys.readouterr().out and markdown.read_text().startswith("**Before:**")
    assert main(["compare", before, after, "--fail-on-new-failures"]) == EXIT_QUALITY_FAILURE
    assert main(["compare", before, after, "--before-run", "x"]) == EXIT_SETUP_ERROR


def test_each_check_says_how_many_cases_got_better_and_worse(tmp_path):
    comparison = compare_runs(*runs(tmp_path))
    required = next(n for n in comparison.noise if n.check == "required_phrases")
    assert (required.better, required.worse) == (1, 1)            # C2 fixed, C1 broken
    assert required.verdict == "could be chance" and required.p_value == 1.0
    assert "bigger than the noise?" in render_comparison(comparison)
    assert "**Bigger than the noise?**" in render_comparison_markdown(comparison)
