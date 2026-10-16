"""
Trajectory Evaluation — test the agent's JOURNEY, not just its answer
====================================================================
Runs the AeroAssist agent on scenarios and grades the TRAJECTORY (the step log)
on the checks that matter for an agent:

  per-step   : right tool?  right arguments?
  whole-run  : did it terminate (no infinite loop)?
  COMPLETENESS: did a multi-intent message get EVERY intent answered, or did one
               silently vanish?  (the star check — caught only with messy input)

A correct-looking final answer can still hide a wrong path or a dropped intent,
which is exactly why we replay the trajectory instead of trusting the destination.

Requires: ANTHROPIC_API_KEY, aeroassist_agent.py (same folder).
"""

import os
import json
from aeroassist_agent import run_agent

MODEL = "claude-haiku-4-5"


# ======================================================================
# SECTION A — Trajectory inspectors (read the step log)
# ======================================================================
def tool_calls(trajectory, tool_name=None):
    """All tool-call steps (optionally for one tool)."""
    return [s for s in trajectory
            if s["type"] == "tool_call" and (tool_name is None or s["tool"] == tool_name)]

def terminated_cleanly(trajectory):
    """True if the agent finished with an answer (did NOT hit the step limit)."""
    return trajectory[-1]["type"] == "final"


# ======================================================================
# SECTION B — Completeness judge (did every intent get answered?)
# ======================================================================
def judge_completeness(client, intents, final_answer, model=MODEL):
    """For each intent, decide whether the final answer addresses it. Returns a
    list of (intent, addressed_bool). This is how we catch a silently dropped intent."""
    system = ('Decide, for each listed intent, whether the answer addresses it at all. '
              'Return ONLY JSON: {"results":[{"intent":"<text>","addressed":true|false}]}.')
    user = f"Intents:\n" + "\n".join(f"- {i}" for i in intents) + f"\n\nAnswer:\n{final_answer}"
    out = client.messages.create(model=model, max_tokens=400, system=system,
                                 messages=[{"role": "user", "content": user}])
    text = out.content[0].text.strip()
    text = text[text.find("{"): text.rfind("}") + 1]
    results = json.loads(text)["results"]
    return [(r["intent"], bool(r["addressed"])) for r in results]


# ======================================================================
# SECTION C — The scenarios (one clean, one messy multi-intent)
# ======================================================================
SCENARIOS = [
    {
        "id": "S1-single",
        "message": "I want a full refund on my booking ABC123.",
        "expect_tool": "get_booking",
        "expect_pnr": "ABC123",
        "intents": ["refund eligibility for booking ABC123"],
    },
    {
        "id": "S2-multi-intent",   # the star: 3 asks in one messy message
        "message": ("Hi, a few things — can I get a refund on ABC123? "
                    "Also what's the cabin baggage allowance in economy? "
                    "And how do I change my flight date?"),
        "expect_tool": "get_booking",
        "expect_pnr": "ABC123",
        "intents": [
            "refund eligibility for booking ABC123",
            "economy cabin baggage allowance",
            "how to change the flight date",
        ],
    },
]


# ======================================================================
# SECTION D — Run each scenario and grade its trajectory
# ======================================================================
def grade(scenario, client):
    final, trajectory = run_agent(scenario["message"], client)

    # per-step: right tool + right args
    calls = tool_calls(trajectory, scenario["expect_tool"])
    tool_ok = len(calls) > 0
    args_ok = tool_ok and calls[0]["args"].get("pnr", "").upper() == scenario["expect_pnr"]

    # whole-run: terminated (no infinite loop)
    term_ok = terminated_cleanly(trajectory)

    # completeness: every intent answered?
    completeness = judge_completeness(client, scenario["intents"], final)
    dropped = [i for i, ok in completeness if not ok]

    print(f"\n{'='*64}\n[{scenario['id']}]  {scenario['message'][:70]}...")
    print(f"  tool called ({scenario['expect_tool']}) : {'✅' if tool_ok else '❌'}")
    print(f"  args correct (pnr={scenario['expect_pnr']}) : {'✅' if args_ok else '❌'}")
    print(f"  terminated (no loop)        : {'✅' if term_ok else '❌'}")
    print(f"  completeness ({len(scenario['intents'])} intents)      : "
          + ("✅ all answered" if not dropped else f"❌ DROPPED: {dropped}"))
    return {"id": scenario["id"], "tool_ok": tool_ok, "args_ok": args_ok,
            "term_ok": term_ok, "dropped": dropped}


def main():
    from anthropic import Anthropic
    try:
        from google.colab import userdata
        api_key = userdata.get("ANTHROPIC_API_KEY")
    except Exception:
        api_key = os.environ["ANTHROPIC_API_KEY"]
    client = Anthropic(api_key=api_key)

    print("Trajectory evaluation — grading the journey, not just the destination")
    results = [grade(s, client) for s in SCENARIOS]

    dropped_any = [r["id"] for r in results if r["dropped"]]
    print(f"\n{'='*64}\nSUMMARY: {len(results)} scenarios graded. "
          + (f"Silent intent-drops in: {dropped_any}" if dropped_any
             else "No dropped intents this run."))
    print("(Re-run to see context-sensitivity: a dropped intent may appear only sometimes.)")
    return results


if __name__ == "__main__":
    results = main()
