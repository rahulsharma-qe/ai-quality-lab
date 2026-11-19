"""Coverage per policy: how many golden cases test each policy, read from expected_sources; and the
lint rule that checks those ids against the policies file without newly failing a prose policies file."""

import pytest

from aiquality import GoldenCaseBuilder, GoldenSet
from aiquality.cli import EXIT_OK, main
from aiquality.test_data.lint import lint_team
from aiquality.test_data.policy_coverage import count_policy_coverage, read_policies, render_policy_coverage


def golden(*cases):
    return GoldenSet(name="g", version="1", cases=list(cases))


def case(case_id, sources=(), priority="medium"):
    return GoldenCaseBuilder(case_id, "a question").expected_sources(*sources).priority(priority).build()


def policies_file(tmp_path, text):
    path = tmp_path / "policies.md"
    path.write_text(text, encoding="utf-8")
    return read_policies(path)


@pytest.mark.parametrize("separator", ["—", "–", "-", ":"])
def test_each_separator_gives_the_id_and_the_title(tmp_path, separator):
    policies = policies_file(tmp_path, f"# Policies\n\n## P1 {separator} Refunds\ntext\n")
    assert [(p.id, p.title) for p in policies.policies] == [("P1", "Refunds")]


def test_a_colon_inside_the_title_stays_in_the_title(tmp_path):
    policies = policies_file(tmp_path, "## P2 — Baggage: Cabin\n### Not covered\n")
    assert [(p.id, p.title) for p in policies.policies] == [("P2", "Baggage: Cabin")]


def test_counts_cases_and_high_priority_cases_and_names_a_policy_with_no_case(tmp_path):
    policies = policies_file(tmp_path, "## P1 — Refunds\n## P2 — Baggage\n## P3 — Seats\n")
    coverage = count_policy_coverage(policies, golden(case("C1", ["P1"], "high"), case("C2", ["P1", "P2"]), case("C3")))
    assert {r.policy.id: (r.case_ids, r.high_priority) for r in coverage.rows} == \
        {"P1": (["C1", "C2"], 1), "P2": (["C2"], 0), "P3": ([], 0)}
    report = render_policy_coverage(coverage)
    assert "not covered" in next(line for line in report.splitlines() if line.startswith("P3"))
    assert "not covered: P3" in report


def test_an_unknown_source_gives_one_warning_per_id_naming_its_cases(tmp_path):
    policies = policies_file(tmp_path, "## P1 — Refunds\n")
    golden_set = golden(case("C1", ["P1", "System rule"]), case("C2", ["System rule"]), case("C3", ["P9"]))
    expected = ["'System rule' in expected_sources matches no '## <ID> — <title>' heading in policies.md; "
                "named by C1, C2",
                "'P9' in expected_sources matches no '## <ID> — <title>' heading in policies.md; named by C3"]
    assert lint_team(golden_set, policies) == expected
    report = render_policy_coverage(count_policy_coverage(policies, golden_set))
    assert [line for line in report.splitlines() if line.startswith("warning:")] == [f"warning: {w}" for w in expected]


def test_a_duplicate_id_is_a_warning_with_and_without_expected_sources(tmp_path):
    policies = policies_file(tmp_path, "## P1 — Refunds\n## P1: Refunds again\n")
    message = "policies.md: duplicate policy id 'P1'; each '## <ID> — <title>' heading needs its own id"
    assert lint_team(golden(case("C1", ["P1"])), policies) == [message]
    assert lint_team(golden(case("C1")), policies) == [message]


def test_prose_headings_that_look_like_ids_only_warn(tmp_path, monkeypatch, capsys):
    """A team whose expected_sources name its own documents, and whose prose headings read as ids,
    is warned, not failed: lint never fails a team on policy ids."""
    monkeypatch.chdir(tmp_path)
    assert main(["new-team", "starter"]) == EXIT_OK
    folder = tmp_path / "teams" / "starter"
    (folder / "policies.md").write_text("## Refunds — how they work\n## Refunds — exceptions\n", encoding="utf-8")
    config = folder / "team.yaml"
    config.write_text(config.read_text(encoding="utf-8") + "\npolicies: policies.md\n", encoding="utf-8")
    golden_csv = folder / "golden_set.csv"
    header, first, *rest = golden_csv.read_text(encoding="utf-8").splitlines()
    golden_csv.write_text("\n".join([header + ",expected_sources", first + ",kb-1042"] + [r + "," for r in rest]) + "\n",
                          encoding="utf-8")
    capsys.readouterr()
    assert main(["lint", "--team", "starter"]) == EXIT_OK
    out = capsys.readouterr().out
    assert "duplicate policy id 'Refunds'" in out and "'kb-1042' in expected_sources matches no" in out
    assert main(["coverage", "--team", "starter"]) == EXIT_OK


def test_a_prose_policies_file_passes_lint_unchanged(tmp_path):
    prose = policies_file(tmp_path, "# Our rules\nRefunds are given within 7 days.\n## Refunds\nAsk a person.\n")
    assert prose.policies == []
    assert lint_team(golden(case("C1")), prose) == []


def test_a_prose_policies_file_warns_when_expected_sources_are_used(tmp_path):
    prose = policies_file(tmp_path, "Refunds are given within 7 days.\n")
    assert lint_team(golden(case("C1", ["P1"])), prose) == [
        "policies.md has no '## <ID> — <title>' headings, so the expected_sources ids can't be checked"]
    assert render_policy_coverage(count_policy_coverage(prose, golden(case("C1", ["P1"])))) == \
        "policies.md has no '## <ID> — <title>' headings; coverage can't be counted"


def test_no_case_with_expected_sources_prints_one_line(tmp_path):
    policies = policies_file(tmp_path, "## P1 — Refunds\n")
    assert render_policy_coverage(count_policy_coverage(policies, golden(case("C1")))) == \
        "no golden case lists expected_sources; coverage can't be counted"


def test_the_command_reports_and_exits_0_for_both_teams(capsys):
    assert main(["coverage", "--team", "aeroassist"]) == EXIT_OK
    assert "every policy is tested by at least one case" in capsys.readouterr().out
    assert main(["coverage", "--team", "post_order_support"]) == EXIT_OK
    assert capsys.readouterr().out.strip() == "no golden case lists expected_sources; coverage can't be counted"


def test_a_starter_team_with_no_policies_key_still_passes_gate_and_lint(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["new-team", "starter"]) == EXIT_OK
    assert main(["gate", "--team", "starter"]) == EXIT_OK
    assert main(["lint", "--team", "starter"]) == EXIT_OK
    capsys.readouterr()
    assert main(["coverage", "--team", "starter"]) == EXIT_OK
    assert capsys.readouterr().out.strip() == "team.yaml has no policies: key; coverage can't be counted"
