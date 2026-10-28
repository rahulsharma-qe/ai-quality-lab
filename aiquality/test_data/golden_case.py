"""One test case in a golden set, and the golden set itself."""

import difflib
from dataclasses import dataclass, field
from typing import Optional

from aiquality.test_data.expected_decision import parse_expected_decision

LIST_FIELDS = ("must_include", "must_not_include", "must_not_do", "expected_sources", "dimensions")
KNOWN_FIELDS = (
    "id", "input", "category", "priority", "reference_answer", "expected_behaviour",
    "must_include", "must_not_include", "must_not_do", "expected_tool_calls", "expected_sources",
    "client", "conversation_history", "dimensions", "expected_decision", "disclosure", "counterfactual",
)
DISCLOSURE_MOMENTS = ("first_reply", "asked")
# A column close to one of these names is almost surely a typo of it, and as written the check it
# drives would run on nothing. Other columns (notes, sub_category, expected_behavior) are kept as notes.
CHECK_FIELDS = ("must_include", "must_not_include", "must_not_do", "expected_sources", "expected_decision",
                "expected_tool_calls", "disclosure", "counterfactual", "conversation_history")


@dataclass
class GoldenCase:
    """A question with what a good answer must and must not contain.

    must_include      literal phrases a good answer contains
    must_not_include  literal phrases a good answer never contains (cheap, blocking signal)
    must_not_do       descriptions of forbidden behaviour, checked by a judge, not by phrases
    expected_sources  ids of the documents a good answer needs, e.g. ["P1"] (for retrieval agents)
    expected_decision what a good answer decides: "yes", "no", "depends", "hand_over", an amount
                      like "₹1500", or alternatives joined by " OR " (see expected_decision.py)
    disclosure        "first_reply" or "asked": the moment the ai_disclosure check tests
    counterfactual    {slot: "{passenger}", vary: name}: the question is asked once per identity in the
                      team's list, and the counterfactual_fairness check compares the decisions
    client            optional tag, so results can be gated per client
    extra             any other fields from the source file, kept untouched
    """

    id: str
    input: str
    category: str = "uncategorised"
    priority: str = "medium"
    reference_answer: str = ""
    expected_behaviour: str = ""
    must_include: list[str] = field(default_factory=list)
    must_not_include: list[str] = field(default_factory=list)
    must_not_do: list[str] = field(default_factory=list)
    expected_tool_calls: Optional[object] = None
    expected_sources: list[str] = field(default_factory=list)
    client: Optional[str] = None
    conversation_history: list[dict] = field(default_factory=list)
    dimensions: list[str] = field(default_factory=list)
    expected_decision: Optional[str] = None
    disclosure: Optional[str] = None     # "first_reply" or "asked": what the ai_disclosure check tests
    counterfactual: Optional[dict] = None   # {slot: "{passenger}", vary: name}: asked once per identity
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "GoldenCase":
        """Build a case from a dict. Raises ValueError with a readable message when invalid."""
        problems = []
        case_id = str(data.get("id", "")).strip()
        question = str(data.get("input", "") or "").strip()
        if not case_id:
            problems.append("missing 'id'")
        if not question:
            problems.append("missing 'input' (the question)")
        for name in LIST_FIELDS:
            value = data.get(name)
            if value is not None and not isinstance(value, list):
                problems.append(f"'{name}' must be a list of text")
        history = data.get("conversation_history") or []
        if not isinstance(history, list):
            problems.append("'conversation_history' must be a list of {role, content} turns")
        if data.get("expected_decision") is not None:
            try:
                parse_expected_decision(data["expected_decision"])
            except ValueError as error:
                problems.append(f"'expected_decision': {error}")
        problems += _counterfactual_problems(data.get("counterfactual"), question)
        problems += [f"'{name}' is not a field: did you mean '{close[0]}'? As written the check it drives would run "
                     "on nothing, so the golden set isn't loaded. Rename it (or, if it is a note, give it a name "
                     f"such as note_{name})"
                     for name in data if name not in KNOWN_FIELDS
                     for close in [difflib.get_close_matches(str(name).strip().lower(), CHECK_FIELDS, n=1, cutoff=0.88)]
                     if close]
        if data.get("disclosure") not in (None, "", *DISCLOSURE_MOMENTS):
            problems.append(f"'disclosure' must be {' or '.join(DISCLOSURE_MOMENTS)}, not '{data['disclosure']}'")
        if problems:
            raise ValueError("; ".join(problems))

        known = {k: data[k] for k in KNOWN_FIELDS if k in data and data[k] is not None}
        if not known.get("disclosure"):
            known.pop("disclosure", None)          # an empty spreadsheet cell: nothing to test
        extra = {k: v for k, v in data.items() if k not in KNOWN_FIELDS}
        known["id"], known["input"] = case_id, question
        known["conversation_history"] = history
        return cls(**known, extra=extra)

    def to_dict(self) -> dict:
        data = {name: getattr(self, name) for name in KNOWN_FIELDS}
        data.update(self.extra)
        return data


def _counterfactual_problems(value, question: str) -> list[str]:
    if value in (None, ""):
        return []
    if not isinstance(value, dict) or not isinstance(value.get("slot"), str) or not isinstance(value.get("vary"), str):
        return ["'counterfactual' must be {slot: \"{passenger}\", vary: name}: the placeholder in the question "
                "and which identities fill it"]
    if value["slot"] not in question:
        return [f"'counterfactual.slot' {value['slot']!r} is not in the question"]
    return []


@dataclass
class GoldenSet:
    """A named, versioned list of golden cases."""

    name: str
    version: str
    cases: list[GoldenCase]
    source: str = ""

    def __len__(self) -> int:
        return len(self.cases)

    def __iter__(self):
        return iter(self.cases)
