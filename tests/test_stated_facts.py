"""teams/aeroassist/stated_facts.py: a cabin class reaches the limits tool only if the passenger said it."""

from stated_facts import keep_stated_facts

TOOL = "check_policy_limits"


def test_an_unstated_cabin_class_is_removed():
    arguments = {"topics": ["cabin_baggage"], "cabin_class": "economy", "cabin_bag_count": 3}
    assert keep_stated_facts(TOOL, arguments, "Let me carry 3 cabin bags") == (
        {"topics": ["cabin_baggage"], "cabin_bag_count": 3}, ["cabin_class"])


def test_a_stated_cabin_class_is_kept_in_any_case_and_from_an_earlier_turn():
    arguments = {"topics": ["checked_baggage"], "cabin_class": "business", "checked_bags_total_kg": 34}
    assert keep_stated_facts(TOOL, arguments, "I fly Business. Now I have 34 kg.") == (arguments, [])


def test_a_class_word_inside_another_word_does_not_count():
    arguments = {"topics": ["cabin_baggage"], "cabin_class": "business"}
    assert keep_stated_facts(TOOL, arguments, "I'm travelling for businesses")[1] == ["cabin_class"]


def test_arguments_without_a_class_and_other_tools_are_untouched():
    assert keep_stated_facts(TOOL, {"topics": ["refund"], "hours_since_booking": 3}, "refund?") == (
        {"topics": ["refund"], "hours_since_booking": 3}, [])
    assert keep_stated_facts("other_tool", {"cabin_class": "economy"}, "hi") == ({"cabin_class": "economy"}, [])
