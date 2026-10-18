"""Loading golden sets from JSON, CSV and Excel, and building cases in code."""

import json
from pathlib import Path

import pytest

from aiquality import GoldenCaseBuilder, GoldenSetError, load_golden_set

EXAMPLE_DATA = Path(__file__).resolve().parents[1] / "examples" / "data"
REPO_GOLDEN_SET = Path(__file__).resolve().parents[1] / "teams" / "aeroassist" / "golden_dataset.json"


def test_three_formats_give_identical_cases():
    sets = [load_golden_set(EXAMPLE_DATA / f"sample_golden_set.{ext}") for ext in ("json", "csv", "xlsx")]
    as_dicts = [[c.to_dict() for c in s.cases] for s in sets]
    assert as_dicts[0] == as_dicts[1] == as_dicts[2]
    assert sets[0].cases[2].must_not_do == ["promise a refund the policy does not allow"]


def test_repo_golden_set_loads_with_meta_and_extra_fields():
    golden = load_golden_set(REPO_GOLDEN_SET)
    assert golden.version == "1.16" and len(golden) == 58
    assert golden.cases[2].expected_sources == ["P1"]           # GD03 needs the refund policy
    assert golden.cases[2].expected_decision == "no"            # GD03 refuses a refund outside the window
    first = golden.cases[0]
    assert first.must_not_include == [] and len(first.must_not_do) == 2
    assert "retrieved_policy" in first.extra          # unknown fields are kept, not dropped


def test_repo_golden_set_has_no_lint_warnings():
    """Echoed forbidden phrases and model answers that fail their own checks are fixed, not carried."""
    from aiquality.test_data.lint import lint_golden_set
    assert lint_golden_set(load_golden_set(REPO_GOLDEN_SET)) == []


# Decision-reader limits found on the reference answers, kept visible rather than tuned away.
REFERENCE_READER_LIMITS = {
    "GD21": "reads as depends: its second 'If' offers another option (a date change), not the other case of the refund",
}


def test_repo_reference_answers_reach_their_own_expected_decision():
    """The reference answer of every case with an expected_decision passes the decision check, or the
    reader can't tell (NOT_APPLICABLE). A FAIL means the two disagree, so one of them is wrong."""
    from aiquality.checks import CheckStatus, create_check
    from aiquality.contracts import AgentResponse
    check = create_check("decision")
    failed = {}
    for case in load_golden_set(REPO_GOLDEN_SET).cases:
        if case.expected_decision and case.id not in REFERENCE_READER_LIMITS:
            result = check.evaluate(case, AgentResponse(case.reference_answer))
            if result.status == CheckStatus.FAIL:
                failed[case.id] = result.reason
    assert failed == {}


def test_plain_list_json(tmp_path):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps([{"id": "A", "input": "Hi?"}]))
    golden = load_golden_set(path)
    assert golden.version == "unversioned" and golden.cases[0].category == "uncategorised"


def test_csv_list_cells_and_conversation_history(tmp_path):
    path = tmp_path / "cases.csv"
    path.write_text('id,input,must_include,conversation_history\n'
                    'A,And now?, 24 hours | full refund ,"[{""role"": ""user"", ""content"": ""hi""}]"\n')
    case = load_golden_set(path).cases[0]
    assert case.must_include == ["24 hours", "full refund"]
    assert case.conversation_history == [{"role": "user", "content": "hi"}]


def test_every_problem_is_listed_at_once(tmp_path):
    path = tmp_path / "broken.csv"
    path.write_text("id,input\nB1,\nB1,Real question?\n,No id?\n")
    with pytest.raises(GoldenSetError) as error:
        load_golden_set(path)
    problems = error.value.problems
    assert any("missing 'input'" in p for p in problems)
    assert any("duplicate id 'B1'" in p for p in problems)
    assert any("missing 'id'" in p for p in problems)


@pytest.mark.parametrize("name, content, message", [
    ("cases.txt", "x", "unsupported file type"),
    ("cases.json", "{not json", "not valid JSON"),
    ("cases.json", '{"something": 1}', "expected a list of cases"),
    ("cases.csv", "id,input\n", "no cases found"),
])
def test_bad_files_explain_themselves(tmp_path, name, content, message):
    path = tmp_path / name
    path.write_text(content)
    with pytest.raises(GoldenSetError, match=message):
        load_golden_set(path)


def test_missing_file(tmp_path):
    with pytest.raises(GoldenSetError, match="file not found"):
        load_golden_set(tmp_path / "nope.json")


def test_builder_produces_a_valid_case():
    case = (GoldenCaseBuilder("R1", "Refund?").category("happy").priority("high")
            .must_include("24 hours").must_not_include("approved").must_not_do("promise an exception")
            .for_client("acme").after_turns(("user", "hi"), ("assistant", "hello")).build())
    assert case.client == "acme" and len(case.conversation_history) == 2
    assert case.must_not_do == ["promise an exception"]
    with pytest.raises(ValueError):
        GoldenCaseBuilder("", "").build()


def test_expected_sources_column(tmp_path):
    path = tmp_path / "cases.csv"
    path.write_text("id,input,expected_sources\nA,Refund?,P1 | P6\nB,Hi,\n")
    first, second = load_golden_set(path).cases
    assert first.expected_sources == ["P1", "P6"] and second.expected_sources == []
