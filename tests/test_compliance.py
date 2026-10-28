"""The evidence report: framework files, the evidence a run gives, the label of each control at each
risk level, and the report itself. No API key, no network."""

import json

import pytest
import yaml

from aiquality.cli import main
from aiquality.compliance import RISK_LEVELS, assess, available_frameworks, load_framework, write_report
from aiquality.compliance.evidence import gather
from aiquality.config import TeamConfig
from aiquality.errors import ConfigError
from aiquality.reporting.run_record import RunRecord

from conftest import AGENT_CODE, BASE_CONFIG, GOLDEN_ROWS, write_team


def a_run(gate_passed=True, attacks=True, checks=("no_personal_data",)) -> RunRecord:
    summaries = [{"check": name, "threshold": 1.0, "blocking": True, "passed": 4, "failed": 0, "not_applicable": 0,
                  "errors": 0, "pass_rate": 1.0, "meets_threshold": True} for name in checks]
    return RunRecord(
        command="gate", team="t", client=None, run_mode="recorded", agent_name="a", agent_version="a-1",
        golden_set_name="G", golden_set_version="1", golden_set_source="g.csv", case_count=4, summaries=summaries,
        outcomes=[{"case_id": "C1", "category": "happy"}, {"case_id": "C2", "category": "out_of_scope"}],
        attacks={"total": 2, "resisted": 2, "resistance_rate": 1.0,
                 "families": [{"family": "direct_injection", "total": 2, "resisted": 2}]} if attacks else None,
        gate_decision={"passed": gate_passed, "decision": "PASS" if gate_passed else "FAIL",
                       "failures": [] if gate_passed else ["high-priority cases: 1 of 2 failed (C1), bar 100%"],
                       "scopes": [], "priorities": [], "accepted_findings": []},
        run_id="r1", created_at="2026-10-17T15:51:56+00:00", git_commit="abc1234")


def framework(tmp_path, controls, key="test-fw"):
    path = tmp_path / f"{key}.yaml"
    path.write_text(yaml.safe_dump({"framework": key, "name": "Test", "source": "s", "link": "https://example.org",
                                    "controls": controls}))
    return load_framework(path)


def test_every_framework_that_comes_with_the_platform_loads_and_links_its_source():
    files = available_frameworks()
    assert {"eu-ai-act", "nist-ai-rmf", "iso-42001", "dpdp", "gdpr", "hipaa", "pci-dss", "owasp-llm",
            "rbi-free-ai", "hitrust"} <= set(files)
    for key, path in files.items():
        loaded = load_framework(path)
        assert loaded.link.startswith("https://") and loaded.controls, key
        for control in loaded.controls:
            assert bool(control.evidence) != bool(control.outside_the_tool), (key, control.id)


@pytest.mark.parametrize("control, problem", [
    ({"id": "X", "title": "t", "asks": "a", "evidence": ["release_gate"], "outside_the_tool": "why"},
     "give either 'evidence' or 'outside_the_tool'"),
    ({"id": "X", "title": "t", "asks": "a"}, "give either 'evidence' or 'outside_the_tool'"),
    ({"id": "X", "title": "t", "asks": "a", "evidence": ["vibes"]}, "unknown evidence 'vibes'"),
    ({"id": "X", "title": "t", "asks": "a", "evidence": ["run_records"], "applies_when": ["severe"]},
     "unknown risk level 'severe'"),
])
def test_a_control_the_report_could_overstate_is_refused(tmp_path, control, problem):
    with pytest.raises(ConfigError, match=problem.replace("(", r"\(").replace(")", r"\)")):
        framework(tmp_path, [control])


def test_each_control_gets_a_label_at_each_risk_level(tmp_path):
    fw = framework(tmp_path, [
        {"id": "Gate", "title": "t", "asks": "a", "applies_when": ["high"], "evidence": ["release_gate"]},
        {"id": "Attacks", "title": "t", "asks": "a", "evidence": ["attack_resistance"]},
        {"id": "Fair", "title": "t", "asks": "a", "applies_when": ["high"], "evidence": ["check:counterfactual_fairness"]},
        {"id": "Both", "title": "t", "asks": "a", "evidence": ["attack_resistance", "check:ai_disclosure"]},
        {"id": "Policy", "title": "t", "asks": "a", "outside_the_tool": "an organisation's process"},
    ])
    labels = {r.control.id: r.labels for r in assess(a_run(gate_passed=False), [fw], "limited").results}
    assert labels["Gate"] == {"minimal": "practice", "limited": "practice", "high": "miss"}       # evidence shows a FAIL
    assert labels["Attacks"] == {level: "covered" for level in RISK_LEVELS}
    assert labels["Fair"] == {"minimal": "not_required", "limited": "not_required", "high": "gap"}
    assert labels["Both"]["limited"] == "gap"                        # one of two named evidences is missing
    assert labels["Policy"] == {level: "outside" for level in RISK_LEVELS}


def test_evidence_reads_the_run_record_and_says_what_is_missing():
    run = a_run(attacks=False)
    assert gather("check:no_personal_data", run).summary == "no_personal_data: 4 of 4 passed (100%, bar 100%)"
    assert gather("check:ai_disclosure", run).summary == "No check named ai_disclosure in this team's run."
    assert not gather("attack_resistance", run).found
    assert gather("release_gate", a_run(gate_passed=False)).met is False
    assert not gather("production_monitoring", run).found


def test_the_report_comes_as_html_markdown_and_json_from_one_set_of_data(tmp_path):
    fw = framework(tmp_path, [{"id": "Attacks", "title": "Robust", "asks": "a", "evidence": ["attack_resistance"]},
                              {"id": "Disclose", "title": "Say it is an AI", "asks": "a",
                               "evidence": ["check:ai_disclosure"]}])
    run = a_run()
    run.description = "An agent </script><b>"
    paths = write_report(assess(run, [fw], "limited"), tmp_path / "out")
    html, md, data = (path.read_text() for path in paths)
    report = json.loads(data)
    assert [c["labels"]["limited"] for c in report["controls"]] == ["covered", "gap"]
    assert "## Not shown to be met" in md and "Test Disclose**, Say it is an AI" in md
    assert "</script><b>" not in html and "<\\/script>" in html               # data can't close the script
    assert "fonts.googleapis" not in html and "<script src" not in html       # one file, nothing to fetch
    assert report["run"]["created_at"] == "17-10-2026, 15:51 UTC"


def test_a_team_file_replaces_the_built_in_one_with_the_same_name(tmp_path):
    team = tmp_path / "team"
    (team / "frameworks").mkdir(parents=True)
    (team / "frameworks" / "gdpr.yaml").write_text("framework: gdpr\n")
    assert available_frameworks(team)["gdpr"] == team / "frameworks" / "gdpr.yaml"
    assert available_frameworks(team)["dpdp"].parent.name == "frameworks"


def test_team_yaml_names_known_frameworks_and_a_risk_level(tmp_path):
    config = dict(BASE_CONFIG, compliance={"risk_level": "severe", "frameworks": ["eu-ai-act", "sox"]})
    folder = write_team(tmp_path / "t", config, GOLDEN_ROWS, AGENT_CODE)
    with pytest.raises(ConfigError) as error:
        TeamConfig.load(folder)
    problems = "\n".join(error.value.problems)
    assert "'compliance.risk_level' must be one of minimal, limited, high" in problems
    assert "unknown framework 'sox'" in problems


def test_the_evidence_command_after_a_gate_run(tmp_path, capsys):
    config = dict(BASE_CONFIG, checks={"required_phrases": {"threshold": 0.9}, "forbidden_phrases": {"threshold": 1.0},
                                       "no_personal_data": {"threshold": 1.0}},
                  compliance={"risk_level": "limited", "frameworks": ["eu-ai-act", "owasp-llm"]})
    folder = write_team(tmp_path / "test_team", config, GOLDEN_ROWS, AGENT_CODE)
    runs = tmp_path / "runs"
    main(["gate", "--team", str(folder), "--output-dir", str(runs)])
    capsys.readouterr()
    assert main(["evidence", "--team", str(folder), "--output-dir", str(runs)]) == 0
    out = capsys.readouterr().out
    assert "risk level limited" in out and "EU AI Act Art. 50(1), Tell people they are talking to an AI" in out
    assert (runs / "evidence" / "test_team" / "index.html").is_file()
    assert main(["evidence", "--team", str(folder), "--output-dir", str(runs), "--as", "high"]) == 0
    assert "risk level high (what if: team.yaml says limited)" in capsys.readouterr().out


def test_the_evidence_command_without_a_compliance_block_says_what_to_add(team_folder, tmp_path, capsys):
    assert main(["evidence", "--team", str(team_folder), "--output-dir", str(tmp_path)]) == 2
    assert "has no 'compliance:' block" in capsys.readouterr().err
