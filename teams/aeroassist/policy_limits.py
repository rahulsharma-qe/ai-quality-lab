"""Meridian Airways' limits, decided in code: every policy rule that has a number in it.

policies.md is the text that people and the model read; this file is what decides. A test reads
policies.md and checks that every number here matches it, so the two can't drift apart.

The model gives the facts it read in the conversation (hours until departure, hours since booking,
cabin class, weights); code gives the ruling; the model words it. The facts still come from the
passenger's message, so code makes the arithmetic reliable, not the facts true. In a real system
the times would come from the booking system, as the refund decision does in demos/guardrail_fix.py.

    check_policy_limits({"topics": ["date_change"], "hours_until_departure": 6})
    -> [{"policy": "P5", "topic": "date_change", "outcome": "allowed", "explanation": "..."}]
"""

from dataclasses import asdict, dataclass

# --- The limits (each one is checked against policies.md by tests/test_policy_limits.py) ---------
FULL_REFUND_WINDOW_HOURS = 24          # P1: full refund within 24 hours of booking, boundary included
CABIN_BAG_LIMITS = {"economy": (1, 7), "business": (2, 10)}      # P2: (bags, kg in total)
CHECKED_ALLOWANCE_KG = {"economy": 15, "business": 30}           # P3: free checked allowance
EXCESS_BAGGAGE_RATE_INR = 500          # P3: per kg over the free allowance
WEB_CHECK_IN_OPENS_HOURS = 48          # P4: opens 48 hours before departure
WEB_CHECK_IN_CLOSES_HOURS = 2          # P4: closes 2 hours before departure
DATE_CHANGE_CUTOFF_HOURS = 4           # P5: changes until 4 hours before departure, boundary included
ASSISTANCE_NOTICE_HOURS = 48           # P8: at least 48 hours before departure, boundary included

CABIN_CLASSES = tuple(CHECKED_ALLOWANCE_KG)


@dataclass
class Ruling:
    """One decision: which policy, on what topic, the outcome in a word or two, and why."""

    policy: str
    topic: str
    outcome: str
    explanation: str

    def to_dict(self) -> dict:
        return asdict(self)


# --- One function per rule ----------------------------------------------------------------------

def refund_ruling(hours_since_booking: float) -> Ruling:
    if hours_since_booking <= FULL_REFUND_WINDOW_HOURS:
        return Ruling("P1", "refund", "full refund",
                      f"Booked {_hours(hours_since_booking)} ago: within the {FULL_REFUND_WINDOW_HOURS}-hour "
                      "window, so cancelling now gives a full refund of the amount paid, fees and taxes included.")
    return Ruling("P1", "refund", "taxes and statutory charges only",
                  f"Booked {_hours(hours_since_booking)} ago: past the {FULL_REFUND_WINDOW_HOURS}-hour window, "
                  "so no full refund; only applicable taxes and statutory charges are refundable.")


def web_check_in_ruling(hours_until_departure: float) -> Ruling:
    opens, closes = WEB_CHECK_IN_OPENS_HOURS, WEB_CHECK_IN_CLOSES_HOURS
    if hours_until_departure <= 0:
        return _departed("P4", "web_check_in")
    if hours_until_departure > opens:
        return Ruling("P4", "web_check_in", "not open yet",
                      f"Departure in {_hours(hours_until_departure)}: web check-in opens {opens} hours before "
                      f"departure, so it opens in {_hours(hours_until_departure - opens)}.")
    if hours_until_departure > closes:
        return Ruling("P4", "web_check_in", "open",
                      f"Departure in {_hours(hours_until_departure)}: web check-in is open (it opened {opens} "
                      f"hours before departure) and closes {closes} hours before departure, in "
                      f"{_hours(hours_until_departure - closes)}.")
    if hours_until_departure == closes:
        return Ruling("P4", "web_check_in", "the policy doesn't say",
                      f"Departure in exactly {closes} hours, the moment web check-in closes. The policy doesn't "
                      "say whether check-in is still open at that moment. Once web check-in has closed, "
                      "check-in is only at the airport counter.")
    return Ruling("P4", "web_check_in", "closed",
                  f"Departure in {_hours(hours_until_departure)}: web check-in closed {closes} hours before "
                  "departure; check-in is only at the airport counter.")


def date_change_ruling(hours_until_departure: float) -> Ruling:
    cutoff = DATE_CHANGE_CUTOFF_HOURS
    if hours_until_departure <= 0:
        return _departed("P5", "date_change")
    if hours_until_departure >= cutoff:
        return Ruling("P5", "date_change", "allowed",
                      f"Departure in {_hours(hours_until_departure)}: date changes can be made until {cutoff} "
                      "hours before departure, so a change is allowed. It costs a change fee plus any fare "
                      "difference.")
    return Ruling("P5", "date_change", "not allowed",
                  f"Departure in {_hours(hours_until_departure)}: inside the last {cutoff} hours before "
                  "departure, when no date changes can be made.")


def special_assistance_ruling(hours_until_departure: float) -> Ruling:
    notice = ASSISTANCE_NOTICE_HOURS
    if hours_until_departure <= 0:
        return _departed("P8", "special_assistance")
    if hours_until_departure >= notice:
        return Ruling("P8", "special_assistance", "in time",
                      f"Departure in {_hours(hours_until_departure)}: a request made now is at least {notice} "
                      "hours before departure, which the policy requires.")
    return Ruling("P8", "special_assistance", "best-effort, not guaranteed",
                  f"Departure in {_hours(hours_until_departure)}: a request made now is inside {notice} hours "
                  "of departure, so it is best-effort and not guaranteed.")


def cabin_baggage_ruling(cabin_class: str, bag_count: int, total_kg: float) -> Ruling:
    bags, kg = CABIN_BAG_LIMITS[cabin_class]
    if bag_count <= bags and total_kg <= kg:
        return Ruling("P2", "cabin_baggage", "within the allowance",
                      f"{cabin_class.title()}: {bag_count} cabin bag(s), {_kg(total_kg)} in total, within the "
                      f"allowance of {bags} bag(s) up to {kg} kg in total.")
    return Ruling("P2", "cabin_baggage", "over the allowance",
                  f"{cabin_class.title()}: {bag_count} cabin bag(s), {_kg(total_kg)} in total, over the "
                  f"allowance of {bags} bag(s) up to {kg} kg in total; oversized or overweight cabin bags must "
                  "be checked in.")


def checked_baggage_ruling(cabin_class: str, total_kg: float) -> Ruling:
    allowance = CHECKED_ALLOWANCE_KG[cabin_class]
    if total_kg <= allowance:
        return Ruling("P3", "checked_baggage", "no charge",
                      f"{cabin_class.title()}: {_kg(total_kg)} checked, within the free allowance of "
                      f"{allowance} kg.")
    excess = total_kg - allowance
    return Ruling("P3", "checked_baggage", f"₹{excess * EXCESS_BAGGAGE_RATE_INR:,.0f} excess charge",
                  f"{cabin_class.title()}: {_kg(total_kg)} checked, {_kg(excess)} over the free allowance of "
                  f"{allowance} kg, at ₹{EXCESS_BAGGAGE_RATE_INR} per kg: ₹{excess * EXCESS_BAGGAGE_RATE_INR:,.0f}.")


# --- The tool the agent calls --------------------------------------------------------------------

TOPICS = {
    "refund": ("hours_since_booking",),
    "web_check_in": ("hours_until_departure",),
    "date_change": ("hours_until_departure",),
    "special_assistance": ("hours_until_departure",),
    "cabin_baggage": ("cabin_class", "cabin_bag_count", "cabin_bags_total_kg"),
    "checked_baggage": ("cabin_class", "checked_bags_total_kg"),
}

TOOL_NAME = "check_policy_limits"
TOOL_SCHEMA = {
    "name": TOOL_NAME,
    "description": (
        "Decides every policy question that depends on a time, a weight or a charge: refunds by time "
        "since booking, web check-in and date changes and special assistance by time until departure, "
        "and cabin and checked baggage by class and weight. Give the topics and the facts from the "
        "conversation; it returns a ruling per topic. Use its ruling in your answer instead of working "
        "it out yourself."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "topics": {"type": "array", "items": {"type": "string", "enum": list(TOPICS)},
                       "description": "The policy questions to decide."},
            "hours_until_departure": {"type": "number", "description": "Hours from now until departure."},
            "hours_since_booking": {"type": "number", "description": "Hours since the booking was made."},
            "cabin_class": {"type": "string", "enum": list(CABIN_CLASSES)},
            "cabin_bag_count": {"type": "integer", "description": "Number of cabin bags."},
            "cabin_bags_total_kg": {"type": "number", "description": "Weight of all cabin bags together."},
            "checked_bags_total_kg": {"type": "number", "description": "Weight of all checked bags together."},
        },
        "required": ["topics"],
    },
}

_RULINGS = {
    "refund": lambda f: refund_ruling(f["hours_since_booking"]),
    "web_check_in": lambda f: web_check_in_ruling(f["hours_until_departure"]),
    "date_change": lambda f: date_change_ruling(f["hours_until_departure"]),
    "special_assistance": lambda f: special_assistance_ruling(f["hours_until_departure"]),
    "cabin_baggage": lambda f: cabin_baggage_ruling(f["cabin_class"], f["cabin_bag_count"], f["cabin_bags_total_kg"]),
    "checked_baggage": lambda f: checked_baggage_ruling(f["cabin_class"], f["checked_bags_total_kg"]),
}


def check_policy_limits(facts: dict) -> list[dict]:
    """The tool: one ruling per topic asked for. A missing fact, or a cabin class that isn't given,
    is said plainly instead of guessed; baggage without a class gets a ruling for each class."""
    rulings = []
    for topic in facts.get("topics") or []:
        if topic not in TOPICS:
            rulings.append({"topic": topic, "error": f"unknown topic; known topics: {', '.join(TOPICS)}"})
            continue
        needed = [name for name in TOPICS[topic] if name != "cabin_class"]
        missing = [name for name in needed if facts.get(name) is None]
        if missing:
            rulings.append({"topic": topic, "error": f"missing: {', '.join(missing)}"})
        elif "cabin_class" in TOPICS[topic] and facts.get("cabin_class") not in CABIN_CLASSES:
            rulings.extend(_RULINGS[topic]({**facts, "cabin_class": cabin}).to_dict() for cabin in CABIN_CLASSES)
        else:
            rulings.append(_RULINGS[topic](facts).to_dict())
    return rulings


def run_tool(name: str, arguments: dict) -> list[dict]:
    """Run a tool call from the model by name."""
    if name != TOOL_NAME:
        return [{"error": f"unknown tool {name!r}"}]
    return check_policy_limits(arguments)


# --- Wording helpers ------------------------------------------------------------------------------

def _departed(policy: str, topic: str) -> Ruling:
    return Ruling(policy, topic, "already departed", "The departure time has passed.")


def _hours(value: float) -> str:
    return f"{value:g} hour" + ("" if value == 1 else "s")


def _kg(value: float) -> str:
    return f"{value:g} kg"
