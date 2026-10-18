"""teams/aeroassist/policy_limits.py: every ruling at and around its boundary, the tool's handling of
missing facts, and the check that the limits in code are the limits in policies.md."""

import re
from pathlib import Path

import pytest

import policy_limits as limits
from policy_limits import (cabin_baggage_ruling, check_policy_limits, checked_baggage_ruling,
                           date_change_ruling, refund_ruling, run_tool, special_assistance_ruling,
                           web_check_in_ruling)

POLICIES_FILE = Path(__file__).resolve().parents[1] / "teams" / "aeroassist" / "policies.md"


@pytest.mark.parametrize("hours, outcome", [(3, "full refund"), (24, "full refund"),
                                            (24.5, "taxes and statutory charges only"),
                                            (120, "taxes and statutory charges only")])
def test_refund_window_includes_its_boundary(hours, outcome):
    assert refund_ruling(hours).outcome == outcome


@pytest.mark.parametrize("hours, outcome", [(60, "not open yet"), (48.5, "not open yet"), (48, "open"),
                                            (30, "open"), (3, "open"), (2, "the policy doesn't say"),
                                            (1.5, "closed"), (0, "already departed")])
def test_web_check_in_opens_at_48_hours_and_the_2_hour_close_is_left_open(hours, outcome):
    assert web_check_in_ruling(hours).outcome == outcome


def test_web_check_in_says_when_it_opens_and_closes():
    assert "opens in 12 hours" in web_check_in_ruling(60).explanation
    assert "in 28 hours" in web_check_in_ruling(30).explanation


@pytest.mark.parametrize("hours, outcome", [(6, "allowed"), (4, "allowed"), (3.5, "not allowed"),
                                            (2, "not allowed"), (-1, "already departed")])
def test_date_change_cutoff_includes_exactly_4_hours(hours, outcome):
    assert date_change_ruling(hours).outcome == outcome


def test_an_allowed_date_change_names_its_charges():
    assert "change fee plus any fare difference" in date_change_ruling(6).explanation


@pytest.mark.parametrize("hours, outcome", [(72, "in time"), (48, "in time"),
                                            (47, "best-effort, not guaranteed"),
                                            (20, "best-effort, not guaranteed")])
def test_special_assistance_notice_includes_exactly_48_hours(hours, outcome):
    assert special_assistance_ruling(hours).outcome == outcome


@pytest.mark.parametrize("cabin, kg, outcome", [("economy", 15, "no charge"), ("economy", 18, "₹1,500 excess charge"),
                                                ("business", 30, "no charge"), ("business", 34, "₹2,000 excess charge")])
def test_checked_baggage_charge_is_the_excess_times_the_rate(cabin, kg, outcome):
    assert checked_baggage_ruling(cabin, kg).outcome == outcome


@pytest.mark.parametrize("cabin, bags, kg, outcome", [("economy", 1, 7, "within the allowance"),
                                                      ("economy", 1, 12, "over the allowance"),
                                                      ("economy", 2, 6, "over the allowance"),
                                                      ("business", 2, 10, "within the allowance")])
def test_cabin_baggage_checks_count_and_weight(cabin, bags, kg, outcome):
    assert cabin_baggage_ruling(cabin, bags, kg).outcome == outcome


def test_the_tool_rules_on_each_topic_asked_for():
    rulings = check_policy_limits({"topics": ["date_change", "web_check_in"], "hours_until_departure": 6})
    assert [(r["policy"], r["outcome"]) for r in rulings] == [("P5", "allowed"), ("P4", "open")]


def test_the_tool_never_answers_missing_a_topic_without_a_figure_gets_the_rule():
    [ruling] = check_policy_limits({"topics": ["refund"]})
    assert ruling["outcome"] == "depends on a time not given" and "within 24 hours of booking" in ruling["explanation"]
    assert "unknown topic" in check_policy_limits({"topics": ["meals"]})[0]["error"]
    assert check_policy_limits({}) == [] and check_policy_limits({"topics": []}) == []


@pytest.mark.parametrize("topic, more_than, less_than, outcome", [
    ("special_assistance", None, 48, "best-effort, not guaranteed"),     # "tomorrow"
    ("web_check_in", 300, None, "not open yet"),                         # "in about two weeks"
    ("date_change", 144, None, "allowed"),                               # "in a week"
    ("refund", 100, None, "taxes and statutory charges only"),           # "booked last week"
    ("web_check_in", None, 48, "depends on the exact time"),             # "tomorrow": open unless within 2 hours
    ("date_change", 2, 6, "depends on the exact time"),                  # "in a few hours"
    ("web_check_in", 2, 48, "open"),
])
def test_a_time_range_gets_one_outcome_or_depends(topic, more_than, less_than, outcome):
    from policy_limits import time_range_ruling
    assert time_range_ruling(topic, more_than, less_than).outcome == outcome


def test_a_range_ruling_carries_the_rule_so_the_answer_can_cover_each_case():
    [ruling] = check_policy_limits({"topics": ["web_check_in"], "hours_until_departure_less_than": 48})
    assert "Departure in less than 48 hours" in ruling["explanation"] and "closes 2 hours before" in ruling["explanation"]


def test_an_exact_time_wins_over_a_range():
    facts = {"topics": ["date_change"], "hours_until_departure": 6, "hours_until_departure_less_than": 3}
    assert check_policy_limits(facts)[0]["outcome"] == "allowed"


@pytest.mark.parametrize("cabin, bags, kg, outcome", [
    ("economy", 2, None, "over the allowance"),
    ("business", 2, None, "within the allowance if they weigh up to 10 kg in total"),
    ("economy", None, 12, "over the allowance"),
    ("business", None, 8, "within the allowance if it is no more than 2 bag(s)"),
    ("economy", None, None, "depends on the bags"),
])
def test_cabin_baggage_rules_on_the_count_or_the_weight_alone(cabin, bags, kg, outcome):
    assert cabin_baggage_ruling(cabin, bags, kg).outcome == outcome


def test_checked_baggage_without_a_weight_states_the_allowance():
    assert checked_baggage_ruling("economy").outcome == "depends on the weight"


def test_baggage_without_a_class_gets_a_ruling_for_each_class():
    rulings = check_policy_limits({"topics": ["checked_baggage"], "checked_bags_total_kg": 20})
    assert [r["outcome"] for r in rulings] == ["₹2,500 excess charge", "no charge"]


def test_run_tool_refuses_an_unknown_tool():
    assert run_tool("issue_refund", {}) == [{"error": "unknown tool 'issue_refund'"}]
    assert run_tool(limits.TOOL_NAME, {"topics": ["refund"], "hours_since_booking": 2})[0]["outcome"] == "full refund"


def test_the_tool_schema_lists_every_topic():
    assert limits.TOOL_SCHEMA["input_schema"]["properties"]["topics"]["items"]["enum"] == list(limits.TOPICS)


# --- The limits in code must be the limits in policies.md ----------------------------------------

def _policy_text(policy_id: str) -> str:
    text = POLICIES_FILE.read_text(encoding="utf-8").replace("**", "")
    section = re.search(rf"^## {policy_id} .*?(?=^## |^---|\Z)", text, re.M | re.S)
    assert section, f"{policy_id} not found in policies.md"
    return section.group(0)


@pytest.mark.parametrize("policy_id, sentence", [
    ("P1", f"within {limits.FULL_REFUND_WINDOW_HOURS} hours of booking"),
    ("P2", f"Economy: {limits.CABIN_BAG_LIMITS['economy'][0]} cabin bag up to {limits.CABIN_BAG_LIMITS['economy'][1]} kg"),
    ("P2", f"Business: {limits.CABIN_BAG_LIMITS['business'][0]} cabin bags up to {limits.CABIN_BAG_LIMITS['business'][1]} kg total"),
    ("P3", f"Economy free allowance: {limits.CHECKED_ALLOWANCE_KG['economy']} kg"),
    ("P3", f"Business: {limits.CHECKED_ALLOWANCE_KG['business']} kg"),
    ("P3", f"₹{limits.EXCESS_BAGGAGE_RATE_INR} per kg"),
    ("P4", f"Opens {limits.WEB_CHECK_IN_OPENS_HOURS} hours before departure"),
    ("P4", f"closes {limits.WEB_CHECK_IN_CLOSES_HOURS} hours before departure"),
    ("P5", f"until {limits.DATE_CHANGE_CUTOFF_HOURS} hours before departure (exactly {limits.DATE_CHANGE_CUTOFF_HOURS} hours still qualifies)"),
    ("P8", f"at least {limits.ASSISTANCE_NOTICE_HOURS} hours before departure (exactly {limits.ASSISTANCE_NOTICE_HOURS} hours still qualifies)"),
])
def test_every_limit_in_code_is_stated_in_the_policy(policy_id, sentence):
    assert sentence in _policy_text(policy_id)


def test_the_refund_boundary_in_code_is_the_inclusive_one_the_policy_states():
    assert "exactly 24h qualifies" in _policy_text("P1") and refund_ruling(24).outcome == "full refund"


def test_the_tool_description_gives_the_model_no_golden_case_wording():
    """The model reads the tool's description: examples taken from golden or held-out cases would teach
    it those cases, not the rule (the same guard the agent's rules have)."""
    import json
    text = json.dumps(limits.TOOL_SCHEMA).lower()
    assert [w for w in ("tomorrow", "two weeks", "last week", "few hours", "yesterday") if w in text] == []
