"""Checks on what the agent looked up, separately from what it answered.

A retrieval agent can go wrong in two places: it fetches the wrong documents, or it fetches
the right ones and then reasons badly. Checking the documents on their own tells the two apart.
"""

from aiquality.checks.base import Check
from aiquality.checks.phrase_matching import find_any
from aiquality.checks.registry import register_check

TITLE_LENGTH = 40


@register_check("expected_sources")
class ExpectedSources(Check):
    description = ("Every id in expected_sources appears in a document the agent retrieved "
                   "(whole words, so 'P1' matches '## P1 Refunds' but not 'P10'). Diagnoses retrieval; "
                   "usually set blocking: false so the answer checks decide the release.")

    def evaluate(self, case, response):
        if not case.expected_sources:
            return self.not_applicable(case, "case has no expected_sources")
        if response.retrieved_documents is None:
            return self.not_applicable(case, "the agent does not report the documents it retrieved")
        documents = response.retrieved_documents
        missing = [source for source in case.expected_sources
                   if not any(find_any(document, source) for document in documents)]
        retrieved = ", ".join(_title(document) for document in documents) or "nothing"
        if missing:
            return self.failed(case, f"not retrieved: {', '.join(repr(s) for s in missing)}",
                               evidence=f"retrieved: {retrieved}")
        return self.passed(case, f"retrieved: {', '.join(case.expected_sources)}")


def _title(document: str) -> str:
    """The first line of a document, without Markdown heading marks, cut to a readable length."""
    first_line = document.strip().splitlines()[0].lstrip("# ").strip() if document.strip() else ""
    return first_line if len(first_line) <= TITLE_LENGTH else first_line[:TITLE_LENGTH - 1] + "…"
