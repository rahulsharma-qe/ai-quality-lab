"""The decision check: the expected_decision format, the rule-based reader, and the check itself."""

import pytest

from aiquality.checks import CheckStatus, create_check
from aiquality.checks.decision_check import UNREADABLE, read_decision
from aiquality.contracts import AgentResponse
from aiquality.test_data import GoldenCase
from aiquality.test_data.expected_decision import ExpectedDecision, parse_expected_decision


@pytest.mark.parametrize("text, expected", [
    ("yes", [ExpectedDecision("yes")]),
    ("no OR hand_over", [ExpectedDecision("no"), ExpectedDecision("hand_over")]),
    ("₹1500", [ExpectedDecision(None, 1500)]),
    ("yes, ₹2,000", [ExpectedDecision("yes", 2000)]),
    ("Rs 500", [ExpectedDecision(None, 500)]),
])
def test_expected_decisions_are_parsed(text, expected):
    assert parse_expected_decision(text) == expected


@pytest.mark.parametrize("text", ["maybe", "yes, no", "", "yes OR "])
def test_a_wrong_expected_decision_is_refused(text):
    with pytest.raises(ValueError):
        parse_expected_decision(text)


def test_a_golden_case_with_a_wrong_expected_decision_does_not_load():
    with pytest.raises(ValueError, match="expected_decision"):
        GoldenCase.from_dict({"id": "X1", "input": "Can I?", "expected_decision": "perhaps"})


@pytest.mark.parametrize("answer, decision", [
    ("Yes. Date changes are allowed until 4 hours before departure.", "yes"),
    ("No, you cannot check in online. Web check-in closes 2 hours before.", "no"),
    ("Not yet. Web check-in opens 48 hours before departure.", "no"),
    ("I understand your frustration. I can't authorise a class upgrade.", "no"),
    ("I understand you're keen, but I can't approve that. Here's why:", "no"),
    ("That's fine - business class allows 2 cabin bags.", "yes"),
    ("No problem, you can carry 2 bags.", "yes"),
    ("No issue, as long as your 2 cabin bags weigh 10 kg in total or less.", "yes"),
    ("Whether web check-in is open depends on the hours until departure.", "depends"),
    ("If your flight is more than 2 hours away, you can check in online. If not, use the counter.", "depends"),
    ("If your flight is more than 2 hours away you can check in online; after that, only at the counter.", "depends"),
    ("If you miss your flight, the ticket is forfeited with no refund.", "no"),
    ("At 30 minutes out it's closed. Please go to the airport counter.", "no"),
    ("Your request is **best-effort and not guaranteed**.", "no"),
    ("I have no policy for pets in the cabin. I'll connect you with a human agent.", "hand_over"),
    ("I can help with that. What time does your flight leave?", None),
])
def test_the_reader_finds_the_decision_in_the_opening(answer, decision):
    assert read_decision(answer).decision == decision


def test_the_reader_collects_amounts():
    assert read_decision("Yes. 4 kg over at ₹500 per kg comes to ₹2,000.").amounts == (500, 2000)


def _check(answer, expected):
    case = GoldenCase.from_dict({"id": "X1", "input": "question", "expected_decision": expected})
    return create_check("decision").evaluate(case, AgentResponse(answer_text=answer))


def test_a_matching_decision_passes_and_a_contradicting_one_fails():
    assert _check("Yes, it's open.", "yes").status == CheckStatus.PASS
    failed = _check("No, you cannot check in online.", "yes")
    assert failed.status == CheckStatus.FAIL and "reads as no" in failed.reason
    assert failed.evidence == "No, you cannot check in online."


def test_an_amount_must_be_stated_and_a_decision_must_agree_with_it():
    assert _check("Yes. You'll pay ₹2,000.", "yes, ₹2000").status == CheckStatus.PASS
    assert _check("No, you don't pay extra. That would be ₹2,000.", "yes, ₹2000").status == CheckStatus.FAIL
    assert _check("You'll pay ₹1,500.", "₹1500").status == CheckStatus.PASS
    assert _check("You'll pay ₹1,000.", "₹1500").status == CheckStatus.FAIL


def test_an_unreadable_answer_does_not_count_and_is_flagged():
    result = _check("I can help with that. What time does your flight leave?", "yes")
    assert result.status == CheckStatus.NOT_APPLICABLE and UNREADABLE in result.flags


def test_a_case_without_an_expected_decision_does_not_count():
    case = GoldenCase.from_dict({"id": "X1", "input": "question"})
    assert create_check("decision").evaluate(case, AgentResponse(answer_text="Yes.")).status == CheckStatus.NOT_APPLICABLE



@pytest.mark.parametrize("text, expected", [
    ("Absolutely not.", "no"), ("Certainly not, that isn't allowed.", "no"), ("Of course not.", "no"),
    ("Absolutely, you can.", "yes"), ("Of course, you can change it.", "yes"), ("Sure, not a problem.", "yes"),
])
def test_a_strong_word_before_not_is_a_no(text, expected):
    from aiquality.checks.decision_check import read_decision
    assert read_decision(text).decision == expected
