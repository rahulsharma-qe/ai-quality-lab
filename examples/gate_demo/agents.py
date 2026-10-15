"""Two versions of the same small store agent, for showing the release gate both ways.

answer_good       follows the rules
answer_regressed  a "new version" that forgot the receipt rule and obeys hidden Base64 instructions
"""

import base64
import re

AGENT_VERSION = "store-agent-demo"


def answer_good(question: str, conversation=None) -> str:
    text = question.lower()
    if "hours" in text:
        return "We are open from 9 am to 6 pm, Monday to Saturday."
    if "return" in text and "30 days" in text:
        return "Returns are accepted within 30 days with a receipt."
    if "receipt" in text:
        return "Refunds need a receipt. I can connect you to a human agent to look at other options."
    return "I can't help with that myself, but I can connect you to a human agent."


def answer_regressed(question: str, conversation=None) -> str:
    hidden = re.search(r"Base64 message and do exactly what it says: (\S+)", question)
    if hidden:
        instruction = base64.b64decode(hidden.group(1)).decode("utf-8")
        return f"Done as asked ({instruction}): your refund approved."
    text = question.lower()
    if "hours" in text:
        return "We are open from 9 am to 6 pm, Monday to Saturday."
    if "return" in text and "30 days" in text:
        return "Returns are accepted within 30 days."          # forgot the receipt
    if "receipt" in text:
        return "No problem, I can connect you to a human agent."
    return "I can't help with that myself, but I can connect you to a human agent."
