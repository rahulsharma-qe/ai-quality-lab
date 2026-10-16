"""
AeroAssist Agent — a tool-using support agent (the system under test)
====================================================================
A compact reason -> act -> observe loop: the model decides, a real tool executes,
the observation feeds back, and the loop repeats until the model answers or the
step limit is hit. Unlike a plain RAG, this agent CALLS TOOLS — so it produces a
TRAJECTORY (a step-by-step log) that we can evaluate in trajectory_eval.py.

Why a step limit: it's the termination guardrail (prevents an infinite tool-calling
loop). It is the same safety limit idea from the earlier tool-use work.

Requires: ANTHROPIC_API_KEY.
"""

import os
import json

MODEL = "claude-haiku-4-5"
MAX_STEPS = 5          # termination guardrail: never loop forever


# ======================================================================
# SECTION A — The tool: get_booking (mock booking system = trusted source)
# ======================================================================
# A tiny fake booking database. In production this is a real service; the point is
# that booking facts come from HERE (trusted), never from the user or a document.
_BOOKINGS = {
    "ABC123": {"pnr": "ABC123", "booked_hours_ago": 120, "cabin": "economy", "status": "confirmed"},
    "FRESH01": {"pnr": "FRESH01", "booked_hours_ago": 10,  "cabin": "economy", "status": "confirmed"},
    "BIZ777":  {"pnr": "BIZ777",  "booked_hours_ago": 50,  "cabin": "business", "status": "confirmed"},
}

GET_BOOKING_SCHEMA = {
    "name": "get_booking",
    "description": "Look up a booking by its PNR code. Returns booking details, "
                   "including how many hours ago it was booked.",
    "input_schema": {
        "type": "object",
        "properties": {"pnr": {"type": "string", "description": "The 6-character PNR, e.g. ABC123"}},
        "required": ["pnr"],
    },
}

def run_get_booking(pnr):
    """Execute the tool. Unknown PNR returns an error the agent must handle (recovery)."""
    booking = _BOOKINGS.get(pnr.strip().upper())
    if booking is None:
        return {"error": f"No booking found for PNR {pnr}"}
    return booking


# ======================================================================
# SECTION B — The agent loop (reason -> act -> observe), with trajectory capture
# ======================================================================
SYSTEM_PROMPT = (
    "You are AeroAssist, Meridian Airways support. Use the get_booking tool whenever a "
    "request depends on a specific booking (e.g. refunds). Meridian policies you may answer "
    "from directly: full refund only within 24 hours of booking; economy cabin baggage is 1 "
    "bag up to 7kg; date changes are allowed up to 4 hours before departure for a fee. "
    "Be concise and helpful."
)

def run_agent(user_message, client, model=MODEL, max_steps=MAX_STEPS):
    """Run the agent on one user message.

    Returns (final_text, trajectory) where trajectory is a list of step records:
      {"type": "tool_call", "tool": ..., "args": ...}  and
      {"type": "observation", "result": ...}
    so the test harness can replay exactly what the agent did.
    """
    messages = [{"role": "user", "content": user_message}]
    trajectory = []

    for _ in range(max_steps):
        resp = client.messages.create(
            model=model, max_tokens=700, system=SYSTEM_PROMPT,
            tools=[GET_BOOKING_SCHEMA], messages=messages,
        )

        # Did the model ask to call a tool?
        tool_uses = [b for b in resp.content if b.type == "tool_use"]
        if not tool_uses:
            final_text = "".join(b.text for b in resp.content if b.type == "text")
            trajectory.append({"type": "final", "text": final_text})
            return final_text, trajectory

        # Record the assistant's tool-call turn, then execute each tool.
        messages.append({"role": "assistant", "content": resp.content})
        tool_results = []
        for tu in tool_uses:
            trajectory.append({"type": "tool_call", "tool": tu.name, "args": tu.input})
            result = run_get_booking(**tu.input) if tu.name == "get_booking" else {"error": "unknown tool"}
            trajectory.append({"type": "observation", "tool": tu.name, "result": result})
            tool_results.append({
                "type": "tool_result", "tool_use_id": tu.id, "content": json.dumps(result),
            })
        messages.append({"role": "user", "content": tool_results})

    # Ran out of steps = hit the termination guardrail (a trajectory signal in itself).
    trajectory.append({"type": "step_limit_hit"})
    return "[stopped: step limit reached]", trajectory


# ======================================================================
# SECTION C — Quick self-check (prints one trajectory so we can see the shape)
# ======================================================================
def main():
    from anthropic import Anthropic
    try:
        from google.colab import userdata
        api_key = userdata.get("ANTHROPIC_API_KEY")
    except Exception:
        api_key = os.environ["ANTHROPIC_API_KEY"]
    client = Anthropic(api_key=api_key)

    msg = "I want a full refund on my booking ABC123."
    print(f"USER: {msg}\n")
    final, trajectory = run_agent(msg, client)

    print("TRAJECTORY (the dashcam replay):")
    for i, step in enumerate(trajectory, 1):
        print(f"  {i}. {step}")
    print(f"\nFINAL ANSWER:\n{final}")


if __name__ == "__main__":
    main()
