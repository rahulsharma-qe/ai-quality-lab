"""One test case in a golden set, and the golden set itself."""

from dataclasses import dataclass, field
from typing import Optional

LIST_FIELDS = ("must_include", "must_not_include", "must_not_do", "dimensions")
KNOWN_FIELDS = (
    "id", "input", "category", "priority", "reference_answer", "expected_behaviour",
    "must_include", "must_not_include", "must_not_do", "expected_tool_calls",
    "client", "conversation_history", "dimensions",
)


@dataclass
class GoldenCase:
    """A question with what a good answer must and must not contain.

    must_include      literal phrases a good answer contains
    must_not_include  literal phrases a good answer never contains (cheap, blocking signal)
    must_not_do       descriptions of forbidden behaviour, checked by a judge, not by phrases
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
    client: Optional[str] = None
    conversation_history: list[dict] = field(default_factory=list)
    dimensions: list[str] = field(default_factory=list)
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
        if problems:
            raise ValueError("; ".join(problems))

        known = {k: data[k] for k in KNOWN_FIELDS if k in data and data[k] is not None}
        extra = {k: v for k, v in data.items() if k not in KNOWN_FIELDS}
        known["id"], known["input"] = case_id, question
        known["conversation_history"] = history
        return cls(**known, extra=extra)

    def to_dict(self) -> dict:
        data = {name: getattr(self, name) for name in KNOWN_FIELDS}
        data.update(self.extra)
        return data


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
