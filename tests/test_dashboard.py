"""The dashboard: every team's latest gate and its saved runs, from run records already on disk."""

from datetime import date, timedelta

import pytest

from aiquality import TeamConfig
from aiquality.cli import EXIT_OK, main
from aiquality.commands import evaluate_team, gate_team
from aiquality.errors import SetupError
from aiquality.reporting.dashboard import collect_team_runs, render_dashboard

from conftest import AGENT_CODE, BASE_CONFIG, GOLDEN_ROWS, write_team


@pytest.fixture
def saved_runs(tmp_path):
    """teams/test_team with two history runs (one under an older golden set) and a latest gate run."""
    expires = (date.today() + timedelta(days=5)).isoformat()
    config = dict(BASE_CONFIG, accepted_findings=[{"case": "C1", "check": "forbidden_phrases", "reason": "reviewed",
                                                   "approved_by": "a person", "expires": expires}])
    teams = tmp_path / "teams"
    folder = write_team(teams / "test_team", config, GOLDEN_ROWS, AGENT_CODE)
    team = TeamConfig.load(folder)
    first = evaluate_team(team, output_dir=folder / "history" / "v1", print_reports=False)
    evaluate_team(team, output_dir=folder / "history" / "v2", print_reports=False)
    gate_team(team, output_dir=tmp_path / "runs", print_reports=False)
    return tmp_path, first


def test_runs_are_collected_per_team_oldest_first(saved_runs):
    root, first = saved_runs
    [team] = collect_team_runs(root / "runs", root / "teams")
    assert team.team == "test_team"
    assert [label for label, _ in team.runs] == ["v1", "v2", "latest run"]
    assert team.runs[0][1].run_id == first.run_id
    assert team.latest_gate is team.runs[-1][1] and len(team.accepted_findings) == 1


def test_the_page_shows_the_gate_the_trend_and_findings_that_expire_soon(saved_runs):
    root, _ = saved_runs
    page = render_dashboard(collect_team_runs(root / "runs", root / "teams"), today=date.today())
    assert "Every team now" in page and "<a href='#test_team'>test_team</a>" in page
    assert "class='PASS'>PASS" in page
    assert "1 expire within 14 days" in page and "C1 / forbidden_phrases" in page
    assert page.count("<tr><td class='nowrap'>") == 3                  # one row per saved run
    assert "not directly comparable" not in page                       # one golden set version only


def test_a_mix_of_golden_set_versions_is_called_out(saved_runs):
    root, _ = saved_runs
    [team] = collect_team_runs(root / "runs", root / "teams")
    team.runs[0][1].golden_set_version = "0.9"
    assert "2 golden set versions; pass rates from different versions are not directly comparable" in \
        render_dashboard([team])


def test_no_saved_runs_is_a_setup_error(tmp_path):
    with pytest.raises(SetupError, match="run a gate first"):
        collect_team_runs(tmp_path / "runs", tmp_path / "teams")


def test_cli_writes_the_page(saved_runs, capsys):
    root, _ = saved_runs
    output = root / "out" / "dashboard.html"
    code = main(["dashboard", "--output", str(output), "--output-dir", str(root / "runs"),
                 "--teams-dir", str(root / "teams")])
    assert code == EXIT_OK and output.read_text(encoding="utf-8").startswith("<!doctype html>")
    assert "dashboard written to" in capsys.readouterr().out
