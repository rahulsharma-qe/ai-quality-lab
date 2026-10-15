"""Example 13: check that the agent found the right documents, separately from its answer.

A retrieval agent can fail in two places: it fetches the wrong documents, or it fetches the
right ones and then reasons badly. The expected_sources check looks only at the first step:
every id in a case's expected_sources must appear in a document the agent retrieved.
An agent that doesn't report its documents gets NOT_APPLICABLE, never a pass.

In a team config (diagnostic, so the answer checks decide the release):
    checks:
      expected_sources: {threshold: 0.9, blocking: false}
In a golden set: an "expected_sources" list, or a CSV column such as  P1|P6
Run:  python examples/13_check_retrieved_sources.py
"""

from aiquality import GoldenCaseBuilder, PythonFunctionAgent, Runner
from aiquality.checks import create_check

POLICIES = [
    "R1 Refunds: a full refund within 24 hours of booking.",
    "B1 Baggage: one cabin bag up to 7 kg.",
    "C1 Changes: allowed up to 4 hours before departure.",
]


def answer(question: str) -> dict:
    """A deliberately naive retriever: the one policy sharing the most words with the question."""
    words = set(question.lower().split())
    best = max(POLICIES, key=lambda policy: len(words & set(policy.lower().split())))
    return {"answer_text": f"From our policy: {best}", "retrieved_documents": [best]}


cases = [
    GoldenCaseBuilder("S1", "How much cabin baggage can I bring?").expected_sources("B1").build(),
    # Mentions timing, so the naive retriever picks the change policy instead of the refund policy.
    GoldenCaseBuilder("S2", "Can I cancel and get my money back up to 4 hours before departure?")
    .expected_sources("R1").build(),
    GoldenCaseBuilder("S3", "Hello!").build(),                       # nothing expected: NOT_APPLICABLE
]

check = create_check("expected_sources")
for run in Runner(PythonFunctionAgent(answer, name="naive-retriever")).run(cases):
    result = check.evaluate(run.case, run.response)
    print(f"{result.case_id}  {result.status.value:<15}{result.reason}"
          + (f"  ({result.evidence})" if result.evidence else ""))
