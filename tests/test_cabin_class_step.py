"""teams/aeroassist/cabin_class_step.py (agent v7): when no class is given, the answer names both
classes' cabin allowance; if the model words only one, code adds one fixed sentence from the limits."""

import pytest

from cabin_class_step import BOTH_CLASSES_SENTENCE, cabin_class_step

NO_CLASS = [{"name": "check_policy_limits", "arguments": {"topics": ["cabin_baggage"], "cabin_bag_count": 3}}]


def test_the_sentence_is_built_from_the_limits_in_code():
    assert BOTH_CLASSES_SENTENCE == "Economy allows 1 cabin bag up to 7 kg; Business allows 2 cabin bags up to 10 kg in total."


def test_both_classes_named_adds_nothing():
    answer = "No. Economy allows 1 cabin bag up to 7 kg, and Business allows 2 cabin bags up to 10 kg in total."
    text, step = cabin_class_step(answer, NO_CLASS)
    assert text == answer and step == {"economy_named": True, "business_named": True, "sentence_added": False}


def test_economy_only_gets_the_sentence():
    text, step = cabin_class_step("No. You can carry 1 cabin bag up to 7 kg in economy.", NO_CLASS)
    assert text == f"No. You can carry 1 cabin bag up to 7 kg in economy.\n\n{BOTH_CLASSES_SENTENCE}"
    assert step == {"economy_named": True, "business_named": False, "sentence_added": True}


def test_numbers_in_words_and_close_units_count():
    answer = "No. In economy it's one cabin bag, 7kg. In business it's two cabin bags, 10kg total."
    _, step = cabin_class_step(answer, NO_CLASS)
    assert step["sentence_added"] is False


def test_a_stated_class_or_no_cabin_baggage_topic_doesnt_fire():
    stated = [{"name": "check_policy_limits", "arguments": {"topics": ["cabin_baggage"], "cabin_class": "economy"}}]
    assert cabin_class_step("Economy allows 1 cabin bag.", stated) == ("Economy allows 1 cabin bag.", {})
    other = [{"name": "check_policy_limits", "arguments": {"topics": ["checked_baggage"]}}]
    assert cabin_class_step("15 kg checked.", other) == ("15 kg checked.", {})
    assert cabin_class_step("Hello.", []) == ("Hello.", {})


def test_a_class_removed_by_code_counts_as_not_stated():
    removed = [{"name": "check_policy_limits", "arguments": {"topics": ["cabin_baggage"], "removed_by_code": ["cabin_class"]}}]
    _, step = cabin_class_step("Economy allows 1 cabin bag up to 7 kg.", removed)
    assert step["sentence_added"] is True


@pytest.mark.parametrize("answer", ["Economy: 7 kg.", "Business allows 10 kg."])
def test_a_class_without_its_bag_count_isnt_named(answer):
    _, step = cabin_class_step(answer, NO_CLASS)
    assert step["sentence_added"] is True
