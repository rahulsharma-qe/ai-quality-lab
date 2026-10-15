"""Find a phrase in an answer as whole words, case-insensitively.

Whole-word matching stops substring mistakes: "100" does not match inside "1000",
"free" does not match inside "freedom". A simple plural still counts: "2 hour" matches
"2 hours", so phrases can be written in the singular. A hyphen counts as a space: "24 hour"
matches "24-hour", and "no-show" matches "no show".

Alternatives: "connect OR escalate" passes if either phrase appears (the OR is uppercase,
so a phrase can still contain an ordinary "or").

Phrases cannot understand meaning: "allowed" still matches inside "not allowed". Meaning
belongs to a judge; here we only flag a match that comes right after a negation word,
so a person can spot a likely false alarm fast.
"""

import re
from dataclasses import dataclass
from typing import Optional

NEGATION_WORDS = {"not", "no", "never", "cannot", "can't", "won't", "isn't", "aren't",
                  "don't", "doesn't", "didn't", "wouldn't", "shouldn't", "without"}
WORDS_CHECKED_BEFORE_MATCH = 3


@dataclass
class PhraseMatch:
    phrase: str
    sentence: str
    follows_negation: bool


def split_alternatives(item: str) -> list[str]:
    """'connect OR escalate' -> ['connect', 'escalate']. A plain phrase -> [phrase]."""
    return [part.strip() for part in re.split(r"\s+OR\s+", item) if part.strip()]


def find_any(text: str, item: str) -> Optional[PhraseMatch]:
    """The first alternative of `item` found in `text`, or None."""
    for alternative in split_alternatives(item):
        match = find_phrase(text, alternative)
        if match is not None:
            return match
    return None


def find_phrase(text: str, phrase: str) -> Optional[PhraseMatch]:
    phrase = " ".join(phrase.split())
    words = [re.escape(word) for word in re.split(r"[\s-]+", phrase) if word]
    if not words:
        return None
    # Words may be separated by spaces or hyphens ("24 hour" matches "24-hour"); optional plural at the end.
    pattern = r"(?<![\w])" + r"[\s-]+".join(words) + r"(?:e?s)?(?![\w])"
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if match is None:
        return None
    return PhraseMatch(phrase=phrase, sentence=_sentence_around(text, match.start(), match.end()),
                       follows_negation=_follows_negation(text[:match.start()]))


def _follows_negation(text_before: str) -> bool:
    # Hyphenated words stay whole, so "no-show" is not mistaken for the negation "no".
    previous_words = re.findall(r"[\w'’-]+", text_before.lower())[-WORDS_CHECKED_BEFORE_MATCH:]
    return any(word.replace("’", "'") in NEGATION_WORDS or word.endswith(("n't", "n’t"))
               for word in previous_words)


def _sentence_around(text: str, start: int, end: int) -> str:
    left = max(text.rfind(".", 0, start), text.rfind("\n", 0, start), text.rfind("!", 0, start),
               text.rfind("?", 0, start))
    right_candidates = [i for i in (text.find(".", end), text.find("\n", end), text.find("!", end),
                                    text.find("?", end)) if i != -1]
    right = min(right_candidates) + 1 if right_candidates else len(text)
    return " ".join(text[left + 1:right].split())
