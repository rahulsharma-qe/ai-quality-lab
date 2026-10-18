"""Only facts the passenger stated reach the limits tool.

The model fills in the tool's facts from the conversation, and sometimes fills in one the passenger
never gave: a cabin class, most often, so a passenger who didn't say "economy" gets economy's
allowance as if they had. Code checks the cabin class against what the passenger wrote and drops it
when it isn't there; the tool then rules for each class, as it does when no class is given.

    keep_stated_facts("check_policy_limits", {"topics": ["cabin_baggage"], "cabin_class": "economy"},
                      "Can I bring 3 cabin bags?")
    -> ({"topics": ["cabin_baggage"]}, ["cabin_class"])

Times and weights aren't checked here: the model may turn "tomorrow" into a range, so the words
differ from the numbers by design. A class has no such reading; it is said or it isn't.
"""

import re

import policy_limits

_CLASS_WORDS = {cabin_class: re.compile(rf"\b{cabin_class}\b", re.I) for cabin_class in policy_limits.CABIN_CLASSES}


def keep_stated_facts(tool_name: str, arguments: dict, passenger_text: str) -> tuple[dict, list]:
    """The arguments without facts the passenger didn't state, and the names of the facts removed."""
    if tool_name != policy_limits.TOOL_NAME:
        return arguments, []
    cabin_class = arguments.get("cabin_class")
    if cabin_class and not _class_is_stated(cabin_class, passenger_text):
        return {name: value for name, value in arguments.items() if name != "cabin_class"}, ["cabin_class"]
    return arguments, []


def _class_is_stated(cabin_class: str, passenger_text: str) -> bool:
    words = _CLASS_WORDS.get(str(cabin_class).lower())
    return bool(words and words.search(passenger_text or ""))
