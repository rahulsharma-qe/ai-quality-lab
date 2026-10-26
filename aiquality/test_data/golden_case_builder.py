"""Build golden cases in code, one readable line per detail.

    case = (GoldenCaseBuilder("R1", "Can I get a full refund 3 hours after booking?")
            .category("happy").priority("high")
            .must_include("24 hours", "full refund")
            .must_not_include("non-refundable")
            .build())
"""

from aiquality.test_data.golden_case import GoldenCase


class GoldenCaseBuilder:
    def __init__(self, case_id: str, question: str):
        self._data = {"id": case_id, "input": question,
                      "must_include": [], "must_not_include": [], "must_not_do": [],
                      "expected_sources": [], "conversation_history": []}

    def category(self, name: str) -> "GoldenCaseBuilder":
        self._data["category"] = name
        return self

    def priority(self, level: str) -> "GoldenCaseBuilder":
        self._data["priority"] = level
        return self

    def reference_answer(self, text: str) -> "GoldenCaseBuilder":
        self._data["reference_answer"] = text
        return self

    def must_include(self, *phrases: str) -> "GoldenCaseBuilder":
        self._data["must_include"].extend(phrases)
        return self

    def must_not_include(self, *phrases: str) -> "GoldenCaseBuilder":
        self._data["must_not_include"].extend(phrases)
        return self

    def must_not_do(self, *behaviours: str) -> "GoldenCaseBuilder":
        self._data["must_not_do"].extend(behaviours)
        return self

    def expected_decision(self, decision: str) -> "GoldenCaseBuilder":
        """What a good answer decides: "yes", "no", "depends", "hand_over", "₹1500", "yes, ₹2000",
        or alternatives joined by " OR "."""
        self._data["expected_decision"] = decision
        return self

    def disclosure(self, moment: str) -> "GoldenCaseBuilder":
        """The moment the ai_disclosure check tests: "first_reply" or "asked"."""
        self._data["disclosure"] = moment
        return self

    def expected_sources(self, *source_ids: str) -> "GoldenCaseBuilder":
        """Ids of the documents a good answer needs, e.g. "P1"; checked by expected_sources."""
        self._data["expected_sources"].extend(source_ids)
        return self

    def for_client(self, client: str) -> "GoldenCaseBuilder":
        self._data["client"] = client
        return self

    def after_turns(self, *turns: tuple[str, str]) -> "GoldenCaseBuilder":
        """Earlier conversation as (role, content) pairs, oldest first."""
        self._data["conversation_history"].extend({"role": r, "content": c} for r, c in turns)
        return self

    def build(self) -> GoldenCase:
        return GoldenCase.from_dict(self._data)
