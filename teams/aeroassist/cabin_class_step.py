"""Agent v7: when a cabin-baggage question gives no class, the answer names both classes' allowance.

stated_facts.py drops a class the passenger didn't state, so the tool rules for each class. The model
still sometimes words only one class (GD07 in Run 8: "2 cabin bags" in 1 answer of 3). So code checks
that the answer names each class with its bag count and its weight, and if one is missing, adds one
fixed sentence built from the limits in code (CABIN_BAG_LIMITS), so it can't drift from policies.md:

    cabin_class_step("No. You can carry 1 cabin bag up to 7 kg in economy.", tool_calls_without_a_class)
    -> ("No. You can carry 1 cabin bag up to 7 kg in economy.\\n\\nEconomy allows 1 cabin bag up to 7 kg; "
        "Business allows 2 cabin bags up to 10 kg in total.",
        {"economy_named": True, "business_named": False, "sentence_added": True})

When the model said it in other words, the sentence may repeat it; that is accepted and counted.
"""

import re

import policy_limits

_NUMBER_WORDS = {1: "one", 2: "two", 7: "seven", 10: "ten"}
_SENTENCE_END = re.compile(r"(?<=[.!?;])\s+")


def _sentence() -> str:
    parts = []
    for cabin_class, (bags, kg) in policy_limits.CABIN_BAG_LIMITS.items():
        bag_word = "cabin bag" if bags == 1 else "cabin bags"
        total = "" if bags == 1 else " in total"
        parts.append(f"{cabin_class.title()} allows {bags} {bag_word} up to {kg} kg{total}")
    return "; ".join(parts) + "."


BOTH_CLASSES_SENTENCE = _sentence()


def _number(value: int) -> str:
    word = _NUMBER_WORDS.get(value)
    return rf"(?:{value}|{word})" if word else str(value)


def _names_allowance(text: str, cabin_class: str) -> bool:
    """A sentence with the class word, its bag count ("1 cabin bag", "one bag") and its weight ("7 kg", "7kg")."""
    bags, kg = policy_limits.CABIN_BAG_LIMITS[cabin_class]
    class_word = re.compile(rf"\b{cabin_class}\b", re.I)
    count = re.compile(rf"\b{_number(bags)}\s+(?:cabin\s+)?bags?\b", re.I)
    weight = re.compile(rf"\b{_number(kg)}\s?kg\b", re.I)
    return any(class_word.search(s) and count.search(s) and weight.search(s) for s in _SENTENCE_END.split(text))


def _no_class_on_cabin_baggage(tool_calls: list) -> bool:
    for call in tool_calls or []:
        arguments = call.get("arguments") or {}
        if call.get("name") == policy_limits.TOOL_NAME and "cabin_baggage" in (arguments.get("topics") or []):
            return arguments.get("cabin_class") not in policy_limits.CABIN_CLASSES
    return False


def cabin_class_step(answer_text: str, tool_calls: list) -> tuple[str, dict]:
    """The answer with both classes' cabin allowance, and what code found ({} when the step doesn't apply)."""
    if not _no_class_on_cabin_baggage(tool_calls):
        return answer_text, {}
    text = answer_text or ""
    named = {cabin_class: _names_allowance(text, cabin_class) for cabin_class in policy_limits.CABIN_BAG_LIMITS}
    added = not all(named.values())
    if added:
        text = f"{text}\n\n{BOTH_CLASSES_SENTENCE}" if text else BOTH_CLASSES_SENTENCE
    return text, {**{f"{cabin_class}_named": found for cabin_class, found in named.items()}, "sentence_added": added}
