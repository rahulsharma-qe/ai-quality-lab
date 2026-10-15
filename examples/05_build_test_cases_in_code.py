"""Example 05: build golden cases in code instead of a file.

Useful for generated cases (every product × every country), or for tests.
Run:  python examples/05_build_test_cases_in_code.py
"""

from aiquality import GoldenCaseBuilder

refund_case = (GoldenCaseBuilder("R1", "I booked 3 hours ago. Can I get a full refund?")
               .category("happy").priority("high")
               .must_include("24 hours", "full refund")
               .must_not_include("non-refundable")
               .for_client("meridian-airways")
               .build())

follow_up_case = (GoldenCaseBuilder("R2", "And what if it had been 30 hours?")
                  .category("edge")
                  .after_turns(("user", "I booked 3 hours ago. Can I get a full refund?"),
                               ("assistant", "Yes, within 24 hours of booking a full refund is available."))
                  .must_include("24 hours")
                  .must_not_include("full refund approved")
                  .must_not_do("promise an exception to the refund policy")
                  .build())

# Generated cases: the same question for every cabin class.
generated = [GoldenCaseBuilder(f"BAG-{cabin.upper()}", f"What is the cabin baggage allowance in {cabin}?")
             .category("happy").must_include(cabin).build()
             for cabin in ("economy", "business", "first")]

for case in [refund_case, follow_up_case, *generated]:
    turns = len(case.conversation_history)
    print(f"{case.id:<14} {case.category:<6} client={case.client} earlier turns={turns} "
          f"must_include={case.must_include}")
