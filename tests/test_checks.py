"""Checks: phrase matching, the built-in checks, the registry, and how results are summarised."""

import pytest

from aiquality import AgentResponse, Check, GoldenCaseBuilder, register_check
from aiquality.checks import CheckStatus, create_check, summarise
from aiquality.checks.phrase_matching import find_phrase
from aiquality.config import CheckSettings
from aiquality.evaluation import evaluate_runs
from aiquality.runner import CaseRun


@pytest.mark.parametrize("text, phrase, found", [
    ("It costs 1000 rupees", "100", False),          # no substring match inside a number
    ("Feel the freedom", "free", False),             # no substring match inside a word
    ("This is FREE today", "free", True),            # any case
    ("A full\n refund is due", "full refund", True),  # any spacing between words
    ("Call 24/7", "24/7", True),
    ("can't override it", "can't override", True),
    ("closes 2 hours before departure", "2 hour", True),   # a simple plural still counts
    ("two boxes", "box", True),
    ("100s of bags", "100", True),
    ("within the 24-hour window", "24 hour", True),         # a hyphen counts as a space
    ("within 24 hours of booking", "24 hour", True),
    ("treated as a no show", "no-show", True),
    ("web check-in is **closed**", "web check-in is closed", True),   # markdown emphasis is read through
    ("a *full* refund", "full refund", True),
    ("is**closed**", "is closed", True),
    ("isclosed", "is closed", False),
])
def test_whole_word_matching(text, phrase, found):
    assert (find_phrase(text, phrase) is not None) is found


def test_negation_is_flagged_but_not_understood():
    match = find_phrase("Your refund is not approved yet.", "approved")
    assert match is not None and match.follows_negation          # still a match: meaning needs a judge
    assert not find_phrase("A no-show gets a full refund.", "full refund").follows_negation
    assert find_phrase("Refunds approved here.", "approved").sentence == "Refunds approved here."


def test_alternatives_with_uppercase_or():
    from aiquality.checks.phrase_matching import find_any, split_alternatives
    assert split_alternatives("connect OR escalate") == ["connect", "escalate"]
    assert split_alternatives("this or that") == ["this or that"]          # lowercase "or" is just text
    assert find_any("I'll escalate this to a person.", "connect OR escalate").phrase == "escalate"
    assert find_any("Please wait.", "connect OR escalate") is None


def case(**fields):
    builder = GoldenCaseBuilder("C1", "Question?")
    builder.must_include(*fields.get("must_include", []))
    builder.must_not_include(*fields.get("must_not_include", []))
    return builder.build()


def test_required_phrases():
    check = create_check("required_phrases")
    assert check.evaluate(case(must_include=["24 hours"]), AgentResponse("Within 24 hours.")).status == CheckStatus.PASS
    failed = check.evaluate(case(must_include=["24 hours", "fee"]), AgentResponse("Within 24 hours."))
    assert failed.status == CheckStatus.FAIL and "'fee'" in failed.reason
    assert check.evaluate(case(), AgentResponse("x")).status == CheckStatus.NOT_APPLICABLE
    either = case(must_include=["connect OR escalate"])
    assert check.evaluate(either, AgentResponse("I can escalate this.")).status == CheckStatus.PASS


def test_forbidden_phrases_show_the_sentence_and_flag_negation():
    check = create_check("forbidden_phrases")
    result = check.evaluate(case(must_not_include=["approved"]), AgentResponse("Sorry. It is not approved."))
    assert result.status == CheckStatus.FAIL
    assert "possible false alarm" in result.reason and result.evidence == "It is not approved."
    plain = check.evaluate(case(must_not_include=["approved"]), AgentResponse("Approved! Enjoy."))
    assert "possible false alarm" not in plain.reason


def test_response_time():
    check = create_check("response_time", max_ms=100)
    assert check.evaluate(case(), AgentResponse("x", latency_ms=50)).status == CheckStatus.PASS
    assert check.evaluate(case(), AgentResponse("x", latency_ms=500)).status == CheckStatus.FAIL
    assert check.evaluate(case(), AgentResponse("x")).status == CheckStatus.NOT_APPLICABLE


def test_a_team_can_add_its_own_check():
    @register_check("offers_human_handover_test")
    class OffersHumanHandover(Check):
        description = "Answer offers a person."

        def evaluate(self, case, response):
            if "human" in response.answer_text.lower():
                return self.passed(case)
            return self.failed(case, "no hand-over offered")

    assert create_check("offers_human_handover_test").evaluate(case(), AgentResponse("A human will help")).status \
        == CheckStatus.PASS
    with pytest.raises(ValueError):
        @register_check("offers_human_handover_test")
        class Duplicate(Check):
            def evaluate(self, case, response):
                return self.passed(case)


def test_unknown_check_lists_what_exists():
    with pytest.raises(KeyError, match="required_phrases"):
        create_check("nope")


def test_errors_and_buggy_checks_never_count_as_a_pass():
    @register_check("always_crashes_test")
    class AlwaysCrashes(Check):
        def evaluate(self, case, response):
            raise ZeroDivisionError("bug")

    runs = [CaseRun(case(must_include=["x"]), AgentResponse("x")), CaseRun(case(must_include=["x"]), error="timeout")]
    settings = {"required_phrases": CheckSettings("required_phrases", 0.9),
                "always_crashes_test": CheckSettings("always_crashes_test", 0.9)}
    evaluation = evaluate_runs(runs, settings)
    required = evaluation.summaries["required_phrases"]
    assert (required.passed, required.errors, required.pass_rate) == (1, 1, 1.0)
    crashed = evaluation.summaries["always_crashes_test"]
    assert crashed.errors == 2 and crashed.pass_rate is None and crashed.meets_threshold is None


def test_summary_pass_rate_ignores_not_applicable():
    results = [create_check("required_phrases").evaluate(case(must_include=["a"]), AgentResponse("a")),
               create_check("required_phrases").evaluate(case(), AgentResponse("a"))]
    summary = summarise("required_phrases", results, threshold=1.0, blocking=True)
    assert (summary.passed, summary.not_applicable, summary.pass_rate, summary.meets_threshold) == (1, 1, 1.0, True)


def test_no_personal_data_check_never_echoes_the_data():
    check = create_check("no_personal_data")
    leaked = check.evaluate(case(), AgentResponse("Call her on +91 98765 43210 or mail jane@example.com"))
    assert leaked.status == CheckStatus.FAIL and "1 phone" in leaked.reason and "1 email" in leaked.reason
    assert "98765" not in leaked.reason and "jane" not in leaked.reason
    assert check.evaluate(case(), AgentResponse("Your booking ABC123 costs Rs 500.")).status == CheckStatus.PASS
    assert check.safety and create_check("forbidden_phrases").safety and not create_check("required_phrases").safety


def test_expected_sources_checks_retrieval_on_its_own():
    check = create_check("expected_sources")
    case = GoldenCaseBuilder("S1", "Refund after 3 days?").expected_sources("P1", "P6").build()
    found = AgentResponse("...", retrieved_documents=["## P1 — Refund\n- 24 hours", "## P6 — No-show"])
    partly = AgentResponse("...", retrieved_documents=["## P10 — Pets", "## P6 — No-show"])
    assert check.evaluate(case, found).status == CheckStatus.PASS
    result = check.evaluate(case, partly)
    assert result.status == CheckStatus.FAIL and result.reason == "not retrieved: 'P1'"   # P10 is not P1
    assert result.evidence == "retrieved: P10 — Pets, P6 — No-show"
    assert check.evaluate(case, AgentResponse("...", retrieved_documents=[])).status == CheckStatus.FAIL


def test_expected_sources_is_not_applicable_without_evidence():
    check = create_check("expected_sources")
    case = GoldenCaseBuilder("S1", "Refund?").expected_sources("P1").build()
    no_documents_reported = AgentResponse("...")                       # None: the adapter can't see them
    assert check.evaluate(case, no_documents_reported).status == CheckStatus.NOT_APPLICABLE
    nothing_expected = GoldenCaseBuilder("S2", "Hello").build()
    assert check.evaluate(nothing_expected, AgentResponse("...", retrieved_documents=["x"])).status \
        == CheckStatus.NOT_APPLICABLE
