"""Team config: YAML and JSON, validation, company floor, and keeping secrets out."""

import pytest

from aiquality import CompanyMinimums, ConfigError, TeamConfig

from conftest import AGENT_CODE, BASE_CONFIG, GOLDEN_ROWS, write_team


def config_with(**changes):
    config = {k: (dict(v) if isinstance(v, dict) else v) for k, v in BASE_CONFIG.items()}
    config.update(changes)
    return config


def problems_for(tmp_path, config, minimums=None):
    folder = write_team(tmp_path / "team", config, GOLDEN_ROWS, AGENT_CODE)
    with pytest.raises(ConfigError) as error:
        TeamConfig.load(folder, company_minimums=minimums)
    return " | ".join(error.value.problems)


def test_yaml_and_json_load_the_same(tmp_path):
    yaml_team = TeamConfig.load(write_team(tmp_path / "a", config_with(), GOLDEN_ROWS, AGENT_CODE))
    json_team = TeamConfig.load(write_team(tmp_path / "b", config_with(), GOLDEN_ROWS, AGENT_CODE, as_json=True))
    assert yaml_team.team == json_team.team == "test_team"
    assert yaml_team.checks.keys() == json_team.checks.keys()
    assert yaml_team.golden_set.name == "golden_set.csv" and yaml_team.reports == ["console"]


def test_repo_teams_are_valid():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    assert TeamConfig.load(root / "teams" / "aeroassist").live_agent["adapter"] == "python_function"
    assert TeamConfig.load(root / "examples" / "quickstart_team").client == "sample-store"


def test_typos_and_unknown_names_are_caught(tmp_path):
    problems = problems_for(tmp_path, config_with(chekcs={}, checks={"required_phrase": {"threshold": 0.9}}))
    assert "unknown setting(s): chekcs" in problems
    assert "unknown check 'required_phrase'" in problems


def test_threshold_must_be_a_pass_rate(tmp_path):
    problems = problems_for(tmp_path, config_with(checks={"required_phrases": {"threshold": 90},
                                                          "forbidden_phrases": {"threshold": 1.0}}))
    assert "must be a number from 0 to 1" in problems


def test_company_floor_and_mandatory_checks(tmp_path):
    minimums = CompanyMinimums(mandatory_checks=["forbidden_phrases"], minimum_thresholds={"required_phrases": 0.8})
    problems = problems_for(tmp_path, config_with(checks={"required_phrases": {"threshold": 0.5}}), minimums)
    assert "below the company minimum 0.8" in problems
    assert "'forbidden_phrases' is mandatory" in problems


def test_built_in_company_floor_is_loaded():
    minimums = CompanyMinimums.load()
    assert "forbidden_phrases" in minimums.mandatory_checks


def test_secrets_never_go_in_the_config(tmp_path):
    agent = {"adapter": "http_endpoint", "url": "https://x", "api_token": "abc", "headers": {"Authorization": "Bearer abc"}}
    problems = problems_for(tmp_path, config_with(agent=agent))
    assert "'agent.api_token' looks like a secret" in problems
    assert "'agent.headers.Authorization' would put a secret in the config" in problems


def test_token_by_environment_variable_name_is_fine(tmp_path):
    agent = {"adapter": "http_endpoint", "url": "https://x", "auth_token_env": "MY_TOKEN"}
    folder = write_team(tmp_path / "team", config_with(agent=agent), GOLDEN_ROWS)
    assert TeamConfig.load(folder).agent["auth_token_env"] == "MY_TOKEN"


def test_adapter_settings_are_checked(tmp_path):
    problems = problems_for(tmp_path, config_with(agent={"adapter": "python_function", "file": "agent.py", "fn": "x"}))
    assert "'agent.function' is required" in problems
    assert "'agent.fn' is not a setting" in problems


def test_missing_files_and_unknown_reports(tmp_path):
    assert "golden_set file not found" in problems_for(tmp_path / "1", config_with(golden_set="nope.csv"))
    assert "unknown report(s): pdf" in problems_for(tmp_path / "2", config_with(reports=["pdf"]))


def test_missing_config_file(tmp_path):
    with pytest.raises(ConfigError, match="no team.yaml"):
        TeamConfig.load(tmp_path)


def test_a_team_plugin_adds_its_own_check(tmp_path):
    from aiquality import evaluate_team
    plugin = '''
from aiquality import Check, register_check

@register_check("mentions_opening_days_test")
class MentionsOpeningDays(Check):
    description = "Answer says which days."

    def evaluate(self, case, response):
        if "monday" in response.answer_text.lower():
            return self.passed(case)
        return self.failed(case, "no days mentioned")
'''
    config = config_with(plugins=["team_checks.py"],
                         checks={"forbidden_phrases": {"threshold": 1.0},
                                 "mentions_opening_days_test": {"threshold": 0.0}})
    folder = write_team(tmp_path / "team", config, GOLDEN_ROWS, AGENT_CODE)
    (folder / "team_checks.py").write_text(plugin)
    team = TeamConfig.load(folder)
    assert team.plugins[0].name == "team_checks.py"
    TeamConfig.load(folder)                                  # loading twice is fine
    record = evaluate_team(team, output_dir=tmp_path / "runs", print_reports=False)
    assert any(s["check"] == "mentions_opening_days_test" for s in record.summaries)


def test_broken_plugin_is_a_config_error(tmp_path):
    folder = write_team(tmp_path / "team", config_with(plugins=["missing.py"]), GOLDEN_ROWS, AGENT_CODE)
    with pytest.raises(ConfigError, match="plugin file not found"):
        TeamConfig.load(folder)
