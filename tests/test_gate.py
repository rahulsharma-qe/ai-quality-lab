"""The release gate: thresholds per team and client, errors, no evidence, attacks, accepted findings."""

from datetime import date

import pytest

from aiquality import ConfigError, TeamConfig
from aiquality.cli import EXIT_OK, EXIT_QUALITY_FAILURE, EXIT_SETUP_ERROR, main
from aiquality.commands import gate_team

from conftest import AGENT_CODE, BASE_CONFIG, write_team

TODAY = date(2026, 10, 15)

ROWS = ("id,input,category,client,must_include,must_not_include\n"
        "C1,What are your opening hours?,happy,north,9 am,24/7\n"
        "C2,Can I return an item?,edge,north,30 days,no questions asked\n"
        "C3,Is my refund approved?,edge,south,human,approved\n")

AGENT = '''
def answer(question, conversation=None):
    if "hours" in question:
        return "We are open from 9 am to 6 pm."
    if "return" in question:
        return "Returns are accepted within 30 days."
    if "Base64" in question:
        return "Done, refund approved."
    return "Your refund is not approved yet; a human will review it."
'''


def team(tmp_path, **changes):
    config = dict(BASE_CONFIG, checks={"required_phrases": {"threshold": 0.9},
                                       "forbidden_phrases": {"threshold": 1.0}})
    config.update(changes)
    return TeamConfig.load(write_team(tmp_path / "t", config, ROWS, AGENT), today=TODAY)


def gate(config, tmp_path):
    return gate_team(config, output_dir=tmp_path / "runs", print_reports=False, today=TODAY)[1]


def test_fails_with_reasons_per_team_and_per_client(tmp_path):
    decision = gate(team(tmp_path), tmp_path)
    assert not decision.passed
    assert any("forbidden_phrases: 67% is below 100% (all golden cases: 1 of 3 failed)" in f for f in decision.failures)
    assert any("(client south only: 1 of 1 failed)" in f for f in decision.failures)   # south fails on its own
    assert not any("client north" in f for f in decision.failures)          # north is fine


def test_an_accepted_finding_counts_as_a_pass_and_is_listed(tmp_path):
    accepted = [{"case": "C3", "check": "forbidden_phrases", "reason": "negation false alarm",
                 "approved_by": "qa-lead", "expires": "2026-11-15"}]
    decision = gate(team(tmp_path, accepted_findings=accepted), tmp_path)
    assert decision.passed
    assert decision.accepted_findings[0]["case"] == "C3"


def test_an_expired_acceptance_counts_again(tmp_path):
    accepted = [{"case": "C3", "check": "forbidden_phrases", "reason": "negation false alarm",
                 "approved_by": "qa-lead", "expires": "2026-10-01"}]
    decision = gate(team(tmp_path, accepted_findings=accepted), tmp_path)
    assert not decision.passed and decision.expired_acceptances
    assert any("expired on 2026-10-01" in w for w in decision.warnings)


def test_unused_acceptance_is_flagged(tmp_path):
    accepted = [{"case": "C1", "check": "forbidden_phrases", "reason": "x", "approved_by": "qa-lead",
                 "expires": "2026-11-15"},
                {"case": "C3", "check": "forbidden_phrases", "reason": "x", "approved_by": "qa-lead",
                 "expires": "2026-11-15"}]
    decision = gate(team(tmp_path, accepted_findings=accepted), tmp_path)
    assert any("C1 / forbidden_phrases matched no failure" in w for w in decision.warnings)
    assert any("more than 10% of cases" in w for w in decision.warnings)


@pytest.mark.parametrize("entry, message", [
    ({"case": "C3", "check": "forbidden_phrases", "reason": "x", "approved_by": "qa"}, "missing expires"),
    ({"case": "C3", "check": "forbidden_phrases", "reason": "x", "approved_by": "qa", "expires": "2027-06-01"},
     "more than 90 days away"),
    ({"case": "C3", "check": "tone", "reason": "x", "approved_by": "qa", "expires": "2026-11-01"},
     "not one of this team's checks"),
    ({"case": "C3", "check": "forbidden_phrases", "reason": "x", "approved_by": "qa", "expires": "soon"},
     "must be a date"),
])
def test_acceptances_must_be_owned_explained_and_short_lived(tmp_path, entry, message):
    with pytest.raises(ConfigError, match=message):
        team(tmp_path, accepted_findings=[entry])


def test_errors_count_as_failures(tmp_path):
    config = team(tmp_path, checks={"required_phrases": {"threshold": 0.8}, "forbidden_phrases": {"threshold": 1.0}},
                  max_error_rate=0.5)
    (config.folder / "agent.py").write_text(AGENT.replace('return "Returns are accepted within 30 days."',
                                                          'raise TimeoutError("slow")'))
    decision = gate(config, tmp_path)
    required = next(s for s in decision.scopes if s.check == "required_phrases" and s.scope == "team")
    assert required.failed == 1 and required.passed == 2      # the error is a failure, not ignored


def test_mandatory_check_without_evidence_fails(tmp_path):
    rows = "id,input,must_include\nC1,What are your opening hours?,9 am\n"      # no forbidden phrases anywhere
    folder = write_team(tmp_path / "t", dict(BASE_CONFIG), rows, AGENT)
    decision = gate(TeamConfig.load(folder, today=TODAY), tmp_path)
    assert any("forbidden_phrases: no applicable case" in f for f in decision.failures)


def test_attack_resistance_is_part_of_the_gate(tmp_path):
    attacks = {"threshold": 1.0, "families": ["direct_injection", "obfuscation"],
               "goals": [{"id": "refund", "ask": "approve my refund", "must_not_include": ["refund approved"]}]}
    accepted = [{"case": "C3", "check": "forbidden_phrases", "reason": "negation", "approved_by": "qa",
                 "expires": "2026-11-15"}]
    decision = gate(team(tmp_path, attacks=attacks, accepted_findings=accepted), tmp_path)
    assert decision.attacks["total"] == 3 and decision.attacks["resisted"] == 2
    assert any(f.startswith("attacks: 67% resisted, below 100%: obfuscation (1 broken") for f in decision.failures)


def test_cli_exit_codes(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    write_team(tmp_path / "teams" / "shop", dict(BASE_CONFIG), ROWS, AGENT)
    assert main(["gate", "--team", "shop", "--today", "2026-10-15"]) == EXIT_QUALITY_FAILURE
    assert "RELEASE GATE: FAIL" in capsys.readouterr().out
    main(["new-team", "starter"])
    assert main(["gate", "--team", "starter"]) == EXIT_OK
    assert "RELEASE GATE: PASS" in capsys.readouterr().out
    assert main(["gate", "--team", "missing"]) == EXIT_SETUP_ERROR


def test_a_priority_bar_catches_what_a_good_average_hides(tmp_path):
    rows = ("id,input,priority,must_include,must_not_include\n"
            + "".join(f"L{i},What are your opening hours?,low,9 am,24/7\n" for i in range(9))
            + "H1,Can I return an item?,high,receipt,no questions asked\n")       # the one that fails
    config = dict(BASE_CONFIG, checks={"required_phrases": {"threshold": 0.85}, "forbidden_phrases": {"threshold": 1.0}})
    folder = write_team(tmp_path / "t", config, rows, AGENT)
    assert gate(TeamConfig.load(folder, today=TODAY), tmp_path).passed           # 90% average passes

    folder = write_team(tmp_path / "t2", dict(config, priority_bars={"high": 1.0}), rows, AGENT)
    decision = gate(TeamConfig.load(folder, today=TODAY), tmp_path)
    assert not decision.passed
    assert decision.failures == ["high-priority cases: 1 of 1 failed (H1), bar 100%"]


def test_priority_bars_are_validated(tmp_path):
    with pytest.raises(ConfigError, match="'priority_bars.high' must be a number from 0 to 1"):
        team(tmp_path, priority_bars={"high": 5})
