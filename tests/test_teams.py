"""Every team folder in teams/ must load and have a golden set without lint warnings.

A team joins by adding a folder; this catches a broken config or golden set in the same pull request.
"""

from pathlib import Path

import pytest

from aiquality import TeamConfig
from aiquality.test_data import load_golden_set
from aiquality.test_data.lint import lint_golden_set

TEAMS = sorted(folder for folder in (Path(__file__).resolve().parents[1] / "teams").iterdir()
               if folder.is_dir() and not folder.name.startswith(("_", ".")))


def test_there_are_at_least_two_teams():
    assert len(TEAMS) >= 2


@pytest.mark.parametrize("folder", TEAMS, ids=[folder.name for folder in TEAMS])
def test_each_team_loads_and_its_golden_set_is_clean(folder):
    config = TeamConfig.load(folder)
    assert config.team == folder.name
    assert lint_golden_set(load_golden_set(config.golden_set)) == []


def test_the_second_team_passes_its_gate(tmp_path):
    """Its stand-in agent answers by its policies, so the gate must pass; CI checks the same."""
    from aiquality.commands import gate_team
    _, decision = gate_team(TeamConfig.load(Path(TEAMS[0]).parent / "post_order_support"),
                            output_dir=tmp_path, print_reports=False)
    assert decision.passed, decision.failures
