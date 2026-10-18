"""Meridian Airways' limits, decided in code: every policy rule that has a number in it.

policies.md is the text that people and the model read; this file is what decides. A test reads
policies.md and checks that every number here matches it, so the two can't drift apart.

The model gives the facts it read in the conversation (hours until departure, hours since booking,
cabin class, weights); code gives the ruling; the model words it. The facts still come from the
passenger's message, so code makes the arithmetic reliable, not the facts true. In a real system
the times would come from the booking system, as the refund decision does in demos/guardrail_fix.py.

    check_policy_limits({"topics": ["date_change"], "hours_until_departure": 6})
    -> [{"policy": "P5", "topic": "date_change", "outcome": "allowed", "explanation": "..."}]

When a fact isn't exact, the model gives what it knows ("tomorrow" is less than 48 hours away) and
the ruling covers that range: one outcome if the whole range falls in one case, otherwise "depends"
with the rule, so the agent can answer for each case instead of asking the passenger for a figure.
A topic with no figure at all gets the rule itself. The tool never answers "missing".
"""

from dataclasses import asdict, dataclass

# Part of the agent's version, like the policies' version: the same agent with different limits code
# is a different agent. 1: Run 6 (exact facts only, "missing" otherwise). 2: Run 7 (ranges, partial facts).
LIMITS_VERSION = "2"

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


def cabin_baggage_ruling(cabin_class: str, bag_count: int = None, total_kg: float = None) -> Ruling:
    """Rules on what is known: the bag count, the total weight, or both."""
    bags, kg = CABIN_BAG_LIMITS[cabin_class]
    cabin = cabin_class.title()
    allowance = f"the allowance of {bags} bag(s) up to {kg} kg in total"
    if bag_count is None and total_kg is None:
        return Ruling("P2", "cabin_baggage", "depends on the bags", f"{cabin}: {allowance}.")
    known = ", ".join(part for part in (
        None if bag_count is None else f"{bag_count} cabin bag(s)",
        None if total_kg is None else f"{_kg(total_kg)} in total") if part)
    if (bag_count is not None and bag_count > bags) or (total_kg is not None and total_kg > kg):
        return Ruling("P2", "cabin_baggage", "over the allowance",
                      f"{cabin}: {known}, over {allowance}; oversized or overweight cabin bags must be "
                      "checked in.")
    if bag_count is not None and total_kg is not None:
        return Ruling("P2", "cabin_baggage", "within the allowance", f"{cabin}: {known}, within {allowance}.")
    if total_kg is None:
        return Ruling("P2", "cabin_baggage", f"within the allowance if they weigh up to {kg} kg in total",
                      f"{cabin}: {known} is within the {bags}-bag allowance; together they may weigh up to "
                      f"{kg} kg.")
    return Ruling("P2", "cabin_baggage", f"within the allowance if it is no more than {bags} bag(s)",
                  f"{cabin}: {known} is within the {kg} kg allowance; the allowance is {bags} bag(s).")


def checked_baggage_ruling(cabin_class: str, total_kg: float = None) -> Ruling:
    allowance = CHECKED_ALLOWANCE_KG[cabin_class]
    if total_kg is None:
        return Ruling("P3", "checked_baggage", "depends on the weight",
                      f"{cabin_class.title()}: free checked allowance {allowance} kg; excess baggage is "
                      f"₹{EXCESS_BAGGAGE_RATE_INR} per kg over it.")
    if total_kg <= allowance:
        return Ruling("P3", "checked_baggage", "no charge",
                      f"{cabin_class.title()}: {_kg(total_kg)} checked, within the free allowance of "
                      f"{allowance} kg.")
    excess = total_kg - allowance
    return Ruling("P3", "checked_baggage", f"₹{excess * EXCESS_BAGGAGE_RATE_INR:,.0f} excess charge",
                  f"{cabin_class.title()}: {_kg(total_kg)} checked, {_kg(excess)} over the free allowance of "
                  f"{allowance} kg, at ₹{EXCESS_BAGGAGE_RATE_INR} per kg: ₹{excess * EXCESS_BAGGAGE_RATE_INR:,.0f}.")


# --- Rulings on a range of time, or on no time at all --------------------------------------------

RULE_TEXT = {
    "refund": (f"A full refund is available when the booking is cancelled within {FULL_REFUND_WINDOW_HOURS} hours "
               f"of booking (exactly {FULL_REFUND_WINDOW_HOURS} hours still qualifies); after that, only applicable "
               "taxes and statutory charges are refundable."),
    "web_check_in": (f"Web check-in opens {WEB_CHECK_IN_OPENS_HOURS} hours before departure and closes "
                     f"{WEB_CHECK_IN_CLOSES_HOURS} hours before departure; after it closes, check-in is only at "
                     "the airport counter."),
    "date_change": (f"Date changes can be made until {DATE_CHANGE_CUTOFF_HOURS} hours before departure (exactly "
                    f"{DATE_CHANGE_CUTOFF_HOURS} hours still qualifies), for a change fee plus any fare difference; "
                    f"no changes can be made in the last {DATE_CHANGE_CUTOFF_HOURS} hours."),
    "special_assistance": (f"Wheelchair or medical assistance must be requested at least {ASSISTANCE_NOTICE_HOURS} "
                           f"hours before departure (exactly {ASSISTANCE_NOTICE_HOURS} hours still qualifies); "
                           f"requests inside {ASSISTANCE_NOTICE_HOURS} hours are best-effort and not guaranteed."),
}

# topic -> (the time fact it needs, the ruling for an exact time, the policy, the times where the outcome changes)
TIME_TOPICS = {
    "refund": ("hours_since_booking", refund_ruling, "P1", (FULL_REFUND_WINDOW_HOURS,)),
    "web_check_in": ("hours_until_departure", web_check_in_ruling, "P4",
                     (WEB_CHECK_IN_CLOSES_HOURS, WEB_CHECK_IN_OPENS_HOURS)),
    "date_change": ("hours_until_departure", date_change_ruling, "P5", (DATE_CHANGE_CUTOFF_HOURS,)),
    "special_assistance": ("hours_until_departure", special_assistance_ruling, "P8", (ASSISTANCE_NOTICE_HOURS,)),
}
_JUST_INSIDE = 0.01        # hours: a point just inside an open range's end


def time_range_ruling(topic: str, more_than: float = None, less_than: float = None) -> Ruling:
    """The ruling for a time known only as a range (both ends excluded). One outcome if the whole range
    falls in one case; otherwise 'depends', with the rule, so the answer can cover each case."""
    fact, exact_ruling, policy, changes = TIME_TOPICS[topic]
    if more_than is None and less_than is None:
        return Ruling(policy, topic, "depends on a time not given", f"No time given. {RULE_TEXT[topic]}")
    low = max(more_than or 0.0, 0.0)
    high = less_than if less_than is not None else max(changes) + 1000
    points = [low + _JUST_INSIDE, high - _JUST_INSIDE] + [point for change in changes
                                                        for point in (change - _JUST_INSIDE, change, change + _JUST_INSIDE)
                                                        if low < point < high]
    outcomes = sorted({exact_ruling(point).outcome for point in points})
    described = _describe_range(fact, more_than, less_than)
    if len(outcomes) == 1:
        return Ruling(policy, topic, outcomes[0], f"{described}: {outcomes[0]} in every case. {RULE_TEXT[topic]}")
    return Ruling(policy, topic, "depends on the exact time",
                  f"{described}: the outcome depends on the exact time ({', '.join(outcomes)}). {RULE_TEXT[topic]}")


def _describe_range(fact: str, more_than, less_than) -> str:
    subject = "Departure in" if fact == "hours_until_departure" else "Booked"
    ago = "" if fact == "hours_until_departure" else " ago"
    if more_than is not None and less_than is not None:
        return f"{subject} between {_hours(more_than)} and {_hours(less_than)}{ago}"
    if more_than is not None:
        return f"{subject} more than {_hours(more_than)}{ago}"
    return f"{subject} less than {_hours(less_than)}{ago}"


# --- The tool the agent calls --------------------------------------------------------------------

TOPICS = tuple(TIME_TOPICS) + ("cabin_baggage", "checked_baggage")

TOOL_NAME = "check_policy_limits"
_TIME_FIELDS = {}
for _fact, _what in (("hours_until_departure", "until departure"), ("hours_since_booking", "since booking")):
    _TIME_FIELDS[_fact] = {"type": "number", "description": f"Hours {_what}, when the passenger gives it."}
    _TIME_FIELDS[f"{_fact}_more_than"] = {"type": "number", "description": f"When the hours {_what} aren't exact: "
                                          "a number they are certainly more than."}
    _TIME_FIELDS[f"{_fact}_less_than"] = {"type": "number", "description": f"When the hours {_what} aren't exact: "
                                          "a number they are certainly less than."}
TOOL_SCHEMA = {
    "name": TOOL_NAME,
    "description": (
        "Decides every policy question that depends on a time, a weight or a charge: refunds by time "
        "since booking, web check-in and date changes and special assistance by time until departure, "
        "and cabin and checked baggage by class and weight. Give the topics the passenger asks about "
        "(none if the question has nothing to do with these) and whatever facts the conversation gives; "
        "leave out what it doesn't. It returns a ruling per topic, which may say the answer depends on a "
        "fact: then answer for each case. Use its ruling instead of working it out yourself."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "topics": {"type": "array", "items": {"type": "string", "enum": list(TOPICS)},
                       "description": "The policy questions to decide; empty if none apply."},
            **_TIME_FIELDS,
            "cabin_class": {"type": "string", "enum": list(CABIN_CLASSES)},
            "cabin_bag_count": {"type": "integer", "description": "Number of cabin bags."},
            "cabin_bags_total_kg": {"type": "number", "description": "Weight of all cabin bags together."},
            "checked_bags_total_kg": {"type": "number", "description": "Weight of all checked bags together."},
        },
        "required": ["topics"],
    },
}


def check_policy_limits(facts: dict) -> list[dict]:
    """The tool: one ruling per topic asked for, from whatever facts are given (exact, a range, or
    none). Baggage without a class gets a ruling for each class."""
    rulings = []
    for topic in facts.get("topics") or []:
        if topic in TIME_TOPICS:
            fact, exact_ruling, _, _ = TIME_TOPICS[topic]
            if facts.get(fact) is not None:
                rulings.append(exact_ruling(facts[fact]).to_dict())
            else:
                rulings.append(time_range_ruling(topic, facts.get(f"{fact}_more_than"),
                                                 facts.get(f"{fact}_less_than")).to_dict())
        elif topic in ("cabin_baggage", "checked_baggage"):
            cabins = [facts["cabin_class"]] if facts.get("cabin_class") in CABIN_CLASSES else list(CABIN_CLASSES)
            for cabin in cabins:
                if topic == "cabin_baggage":
                    ruling = cabin_baggage_ruling(cabin, facts.get("cabin_bag_count"), facts.get("cabin_bags_total_kg"))
                else:
                    ruling = checked_baggage_ruling(cabin, facts.get("checked_bags_total_kg"))
                rulings.append(ruling.to_dict())
        else:
            rulings.append({"topic": topic, "error": f"unknown topic; known topics: {', '.join(TOPICS)}"})
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
