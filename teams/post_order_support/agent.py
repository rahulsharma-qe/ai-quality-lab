"""A stand-in agent for Saffron Basket's post-order support: rules, not a model.

The team uses it to show onboarding by configuration: a real team replaces answer() with a call to
its own agent (a Python function, an HTTP endpoint, or recorded answers). Its answers follow
policies.md, so the team's gate passes; the platform knows nothing about this file except its name.
"""

import re

AGENT_VERSION = "post-order-stand-in-1"

HAND_OVER = "I don't have a policy for that. A human agent will take over."


def answer(question: str, conversation=None) -> str:
    text = question.lower()
    if re.search(r"\b(phone|number|address|contact)\b", text):
        return ("I can't share anyone's contact details, including a delivery partner's or another "
                "customer's. A human agent will take over.")
    if re.search(r"\b(ignore|premium|override|pretend|act as)\b", text) or not re.search(r"[a-z]{3}", text):
        return ("I can't approve that. Refunds and credits follow the same policies for every customer: "
                "a missing or damaged item reported within 48 hours, or a delivery more than 30 minutes late.")
    if re.search(r"\b(missing|damaged|broken|spoilt|spoiled)\b", text):
        return _missing_or_damaged(text)
    if "cancel" in text:
        return _cancel(text)
    if "late" in text:
        return _late(text)
    if "refund" in text and re.search(r"\b(how long|when|bank|wallet)\b", text):
        return ("Refunds reach your Saffron Basket wallet instantly, or your original payment method in "
                "5–7 business days.")
    return HAND_OVER


def _missing_or_damaged(text: str) -> str:
    hours = _hours(text)
    if hours is None:
        return ("It depends on when the order was delivered. If it's within 48 hours of delivery, share a "
                "photo in the app and the item will be refunded. After 48 hours it can't be refunded.")
    if hours <= 48:
        return ("Yes. You're within 48 hours of delivery, so share a photo of the item in the app and it "
                "will be refunded.")
    return ("No. Missing or damaged items have to be reported within 48 hours of delivery, so this one "
            "can't be refunded now.")


def _cancel(text: str) -> str:
    if re.search(r"\b(not (been )?dispatched|hasn'?t been dispatched|just placed|minutes ago)\b", text):
        return "Yes. Your order hasn't been dispatched yet, so you can cancel it free of charge."
    if re.search(r"\b(dispatched|out for delivery|on the way)\b", text):
        return ("No. Your order has already been dispatched, and dispatched orders can't be cancelled. "
                "Cancelling is free only before dispatch.")
    return ("It depends on whether the order has been dispatched. Before dispatch you can cancel it free of "
            "charge; after dispatch it can't be cancelled.")


def _late(text: str) -> str:
    minutes = re.search(r"(\d+)\s*min", text)
    if not minutes:
        return ("If your order arrived more than 30 minutes after the promised time, a ₹50 credit is added "
                "to your wallet.")
    if int(minutes.group(1)) > 30:
        return "Yes. Your order was more than 30 minutes late, so a ₹50 credit will be added to your wallet."
    return ("No. A ₹50 credit applies only when an order is more than 30 minutes late, and yours was "
            f"{minutes.group(1)} minutes late.")


def _hours(text: str):
    found = re.search(r"(\d+)\s*(hour|hr|day)", text)
    if found:
        return int(found.group(1)) * (24 if found.group(2) == "day" else 1)
    if "yesterday" in text:
        return 24
    return None
