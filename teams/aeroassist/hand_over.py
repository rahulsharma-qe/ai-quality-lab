"""The hand-over sentence comes from code, not from the model.

When the model writes its own hand-over, it adds what a person might do: "a human agent may be able
to discuss options", "a human agent can't override this". The policies offer neither, and the judge
fails these answers. So the model only marks that the passenger needs a person (HAND_OVER on the
last line), and code writes the hand-over:

  1. every sentence about what a human agent, a colleague or a team might do is removed;
  2. if the answer hands over (the marker, or a removed sentence that offered to connect the
     passenger), one fixed sentence is added at the end. Without that, nothing is added: a sentence
     like "a human agent can't override this" is removed, and the answer doesn't become a hand-over.

    finish_hand_over("I have no policy for pets.\\nA human agent may find options.\\nHAND_OVER")
    -> ("I have no policy for pets.\\n\\nA human agent will take over from here.",
        {"marker": True, "removed": ["A human agent may find options."]})

The step is returned with the answer, so every recorded answer shows what code changed.

Agent v7 goes one step further: code decides WHETHER to hand over (decide_hand_over). The model's
marker is only a request, kept on the record. Code hands over only when

  1. the passenger's question is out of scope: the understanding step named out_of_scope and no
     other topic (policies.md: anything outside the 8 policies is out of scope, "abstain + escalate");
  2. the passenger asks for a person, in their own words (PASSENGER_ASKS_FOR_A_PERSON);
  3. a ruling gives the outcome to staff (RULINGS_THAT_NEED_A_PERSON): no policy in policies.md 1.3
     does, so the list is empty. It is listed so the rule is visible, not invented.

Otherwise the marker is dropped and the answer stands as the policy's answer. Sentences about what a
person might do are removed as in v6, whatever code decides.
"""

import re

# Part of agent v6's version: the same agent with different hand-over code is a different agent.
# 1: Run 8's recording. 2: "escalat..." and "representative" narrowed after Run 8 removed two sentences
# that weren't about handing over ("escalation threats", "their authorized representative").
HAND_OVER_CODE_VERSION = "2"
# Part of agent v7's version: code decides whether to hand over (decide_hand_over). v6 keeps version 2.
HAND_OVER_DECISION_VERSION = "3"
HAND_OVER_MARKER = "HAND_OVER"
HAND_OVER_SENTENCE = "A human agent will take over from here."

_ESCALATE = r"escalat(e|ed|ing) (this|it|that|you|your)"      # an action, not "escalation threats"
_MARKER = re.compile(r"[*_`\[(]*\bHAND_OVER\b[*_`\])]*:?")
_ABOUT_A_PERSON = re.compile(
    rf"\b(human|colleague|specialist|(service|support|customer) representative|our team|support team|"
    rf"customer (service|support)|someone (from|on|in) our|connect (you|me)|transfer you|{_ESCALATE}|take over|"
    rf"hand you over)\b", re.I)
_OFFERS_A_PERSON = re.compile(rf"\b(connect (you|me)|transfer you|{_ESCALATE}|take over|hand you over|"
                              rf"(contact|speak (to|with)) (a|an|our) (human|agent|colleague|specialist))\b", re.I)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=\S)")
_LINE_START = re.compile(r"^(\s*(?:[-*•]|\d+[.)])?\s*)(.*)$")
_MARKDOWN_ONLY = re.compile(r"^[\s*_`#>•-]*$")


def _without_person_sentences(answer_text: str) -> tuple[str, bool, list]:
    """The answer without the marker and without sentences about what a person might do; whether the
    marker was there; the sentences removed."""
    text = answer_text or ""
    marker = bool(_MARKER.search(text))
    text = _MARKER.sub("", text)
    kept_lines, removed = [], []
    for line in text.split("\n"):
        prefix, body = _LINE_START.match(line).groups()
        sentences = _SENTENCE_END.split(body) if body.strip() else []
        kept = [sentence for sentence in sentences if not _ABOUT_A_PERSON.search(sentence)]
        removed += [sentence.strip() for sentence in sentences if _ABOUT_A_PERSON.search(sentence)]
        if kept or not sentences:
            kept_lines.append(prefix + " ".join(kept))
    text = "\n".join(line for line in kept_lines if not (line.strip() and _MARKDOWN_ONLY.match(line)))
    return re.sub(r"\n{3,}", "\n\n", text).strip(), marker, removed


def finish_hand_over(answer_text: str) -> tuple[str, dict]:
    """The answer with the hand-over written by code, and what changed ({} when nothing did)."""
    text, marker, removed = _without_person_sentences(answer_text)
    hands_over = marker or any(_OFFERS_A_PERSON.search(sentence) for sentence in removed)
    if hands_over:
        text = f"{text}\n\n{HAND_OVER_SENTENCE}" if text else HAND_OVER_SENTENCE
    if not marker and not removed:
        return answer_text, {}
    return text, {"marker": marker, "removed": removed}


# --- Agent v7: code decides whether to hand over ---------------------------------------------------

OUT_OF_SCOPE_TOPIC = "out_of_scope"
# A request for a person, in the passenger's words: a verb of asking with a person after it. Saying a
# person exists ("am I talking to a real person?", "my manager booked this") is not a request.
_A_PERSON = r"(?:a |an |the |your |some )?(?:real |live |actual )?(?:human|person|agent|representative|someone|supervisor)"
PASSENGER_ASKS_FOR_A_PERSON = re.compile(
    rf"\b(?:(?:speak|talk|chat)\s+(?:to|with)\s+{_A_PERSON}\b"
    rf"|(?:connect|transfer|put)\s+me\s+(?:to|with|through)\b"
    rf"|(?:want|need|get me)\s+{_A_PERSON}\b)", re.I)
# Rule 3: a ruling whose outcome a person decides. No policy in policies.md 1.3 has one (P8 inside 48
# hours is "best-effort and not guaranteed", not a person acting), so this stays empty.
RULINGS_THAT_NEED_A_PERSON: tuple = ()


def decide_hand_over(answer_text: str, topics_named: list, passenger_text: str) -> tuple[str, dict]:
    """The answer as code decides it, and the decision: hand over only for an out-of-scope question
    (out_of_scope the only topic named), a passenger who asks for a person, or a ruling that needs one."""
    text, marker, removed = _without_person_sentences(answer_text)
    topics = list(topics_named or [])
    if topics == [OUT_OF_SCOPE_TOPIC]:
        reason = "out_of_scope"
    elif PASSENGER_ASKS_FOR_A_PERSON.search(passenger_text or ""):
        reason = "passenger_asked"
    elif any(topic in RULINGS_THAT_NEED_A_PERSON for topic in topics):
        reason = "ruling_needs_person"
    else:
        reason = "none"
    handed_over = reason != "none"
    if handed_over:
        text = f"{text}\n\n{HAND_OVER_SENTENCE}" if text else HAND_OVER_SENTENCE
    return text, {"model_marked_hand_over": marker, "code_handed_over": handed_over, "hand_over_reason": reason,
                  "topics_named": topics, "mixed_message": OUT_OF_SCOPE_TOPIC in topics and len(topics) > 1,
                  "removed": removed}
