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
"""

import re

HAND_OVER_MARKER = "HAND_OVER"
HAND_OVER_SENTENCE = "A human agent will take over from here."

_MARKER = re.compile(r"[*_`\[(]*\bHAND_OVER\b[*_`\])]*:?")
_ABOUT_A_PERSON = re.compile(
    r"\b(human|colleague|specialist|representative|our team|support team|customer (service|support)|"
    r"someone (from|on|in) our|connect (you|me)|transfer you|escalat\w*|take over|hand you over)\b", re.I)
_OFFERS_A_PERSON = re.compile(r"\b(connect (you|me)|transfer you|escalat\w*|take over|hand you over|"
                              r"(contact|speak (to|with)) (a|an|our) (human|agent|colleague|specialist))\b", re.I)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=\S)")
_LINE_START = re.compile(r"^(\s*(?:[-*•]|\d+[.)])?\s*)(.*)$")
_MARKDOWN_ONLY = re.compile(r"^[\s*_`#>•-]*$")


def finish_hand_over(answer_text: str) -> tuple[str, dict]:
    """The answer with the hand-over written by code, and what changed ({} when nothing did)."""
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
    hands_over = marker or any(_OFFERS_A_PERSON.search(sentence) for sentence in removed)
    text = "\n".join(line for line in kept_lines if not (line.strip() and _MARKDOWN_ONLY.match(line)))
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if hands_over:
        text = f"{text}\n\n{HAND_OVER_SENTENCE}" if text else HAND_OVER_SENTENCE
    if not marker and not removed:
        return answer_text, {}
    return text, {"marker": marker, "removed": removed}
