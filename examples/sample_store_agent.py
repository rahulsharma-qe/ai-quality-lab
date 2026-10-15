"""A tiny rule-based support agent used by the examples. No model, no API key.

It stands in for a real agent so every example runs anywhere in milliseconds.
"""

AGENT_VERSION = "sample-store-1"


def answer(question: str) -> str:
    text = question.lower()
    if "hours" in text:
        return "We are open from 9 am to 6 pm, Monday to Saturday."
    if "return" in text:
        return "Returns are accepted within 30 days with a receipt."
    if "is my refund approved" in text:
        return "Your refund is not approved yet; a human agent will review it today."
    if "refund" in text or "ignore your rules" in text:
        return "I can't approve that myself, but I can connect you to a human agent."
    return "I'm not sure. Let me connect you to a human agent."
