"""Example 17: check what the answer decided, not which words it used.

Phrase checks fail a right answer in other words, and pass a wrong answer that has the right words.
The decision check reads the decision from the answer's opening (yes, no, depends, a hand-over, an
amount) and compares it with the case's expected_decision. When it can't tell what was decided, the
case doesn't count (NOT_APPLICABLE) and is flagged for a person, instead of a guess.

In a team config (reported until the reader has been checked against a person's reading):
    checks:
      decision: {threshold: 1.0, blocking: false}
In a golden set: "expected_decision": "yes" | "no" | "depends" | "hand_over" | "₹1500" | "yes, ₹2000",
or alternatives such as "no OR hand_over".
Run:  python examples/17_check_the_decision.py
"""

from aiquality import GoldenCaseBuilder, PythonFunctionAgent, Runner
from aiquality.checks import create_check

ANSWERS = {
    "D1": "Yes. Changes are allowed until 4 hours before departure, so you can move it.",
    # The right words are all there ("4 hours", "open"), but the decision is wrong.
    "D2": "No, you cannot check in online. Web check-in is open until 2 hours before departure.",
    "D3": "You'll pay ₹1,500: 3 kg over the 15 kg allowance at ₹500 per kg.",
    "D4": "That depends on when you booked. Within 24 hours it's a full refund; after that, taxes only.",
    "D5": "Let me look into that for you. What time is your flight?",
}


def answer(question: str, conversation=None) -> str:
    return ANSWERS[question.split(":")[0]]


cases = [
    GoldenCaseBuilder("D1", "D1: My flight is in 6 hours. Can I move it?").expected_decision("yes").build(),
    GoldenCaseBuilder("D2", "D2: My flight is in 3 hours. Can I still check in online?").expected_decision("yes").build(),
    GoldenCaseBuilder("D3", "D3: Economy, 18 kg bag. What do I pay?").expected_decision("₹1500").build(),
    GoldenCaseBuilder("D4", "D4: Can I get a full refund?").expected_decision("depends OR no").build(),
    GoldenCaseBuilder("D5", "D5: Is web check-in open?").expected_decision("yes").build(),   # unreadable
]

check = create_check("decision")
for run in Runner(PythonFunctionAgent(answer, name="sample-agent")).run(cases):
    result = check.evaluate(run.case, run.response)
    print(f"{result.case_id}  {result.status.value:<15}{result.reason}")
