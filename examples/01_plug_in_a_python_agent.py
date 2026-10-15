"""Example 01: plug in an agent that is a Python function.

Your function can return plain text, a dict, or an AgentResponse. The platform
measures response time for you. Run:  python examples/01_plug_in_a_python_agent.py
"""

from aiquality import AgentResponse, PythonFunctionAgent, ToolCall
from sample_store_agent import answer as sample_store_answer


# 1. A function that returns plain text: the simplest case.
text_agent = PythonFunctionAgent(sample_store_answer, name="sample-store", version="sample-store-1")
response = text_agent.answer("What are your opening hours?")
print("1. text agent      ->", response.answer_text, f"({response.latency_ms} ms)")


# 2. A function that also reports evidence (tools it called, documents it read) as a dict.
def booking_agent(question: str) -> dict:
    return {
        "answer_text": "Your booking ABC123 was made 10 hours ago, so a full refund is available.",
        "tool_calls": [{"name": "get_booking", "arguments": {"pnr": "ABC123"}}],
        "retrieved_documents": ["P1: full refund within 24 hours of booking."],
    }


response = PythonFunctionAgent(booking_agent, name="booking-agent").answer("Refund for ABC123?")
print("2. dict agent      ->", response.answer_text)
print("   tools called    ->", [call.name for call in response.tool_calls])


# 3. A multi-turn agent: give the function a second parameter and it receives the earlier turns.
def multi_turn_agent(question: str, conversation) -> AgentResponse:
    turns = len(conversation or [])
    return AgentResponse(answer_text=f"(I can see {turns} earlier turns) {sample_store_answer(question)}",
                         tool_calls=[ToolCall("lookup_order", {"order": "A1"})])


history = [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello! How can I help?"}]
response = PythonFunctionAgent(multi_turn_agent).answer("Can I return a jacket?", history)
print("3. multi-turn agent->", response.answer_text)
