"""A language-model judge: is this answer correct and grounded in the team's policy?

The judge reads the team's whole policy file, the question and the answer, and returns PASS or
FAIL with a one-sentence reason. Choices that keep it honest:
  - PASS / FAIL, not a 1-5 score: clearer, and easy to compare with people's labels
  - reason first, verdict second: the judge explains before it decides
  - temperature 0 where the client accepts it: the same answer gets the same verdict
  - a different, stronger model than the agent (JUDGE_MODEL): nothing grades its own work
  - the rubric says style and length are not grounds to fail

The version is name : model : rubric version : a hash of the rubric text, so editing the rubric
makes a new version, and a new version must be validated again before it can gate.
Known limit: the judge sees the latest question only, not earlier turns of a conversation.
"""

import hashlib
from pathlib import Path
from typing import Optional

from aiquality.judges.base import Judge, JudgeVerdict
from aiquality.judges.registry import register_judge
from aiquality.models import JUDGE_MODEL, ChatModel, extract_json, get_chat_model

DEFAULT_RUBRIC_FILE = Path(__file__).with_name("default_rubric.md")


@register_judge("policy_answer")
class PolicyAnswerJudge(Judge):
    name = "llm_answer_judge"

    def __init__(self, policy_text: str, rubric: Optional[str] = None, rubric_version: str = "default-v1",
                 model: str = JUDGE_MODEL, chat: Optional[ChatModel] = None):
        self.policy_text = policy_text
        self.rubric = (rubric if rubric is not None else DEFAULT_RUBRIC_FILE.read_text(encoding="utf-8")).strip()
        self.rubric_version = rubric_version
        self.model = model
        self.chat = chat or get_chat_model(model, temperature=0.0, max_tokens=2000)   # room to think and answer

    @property
    def version(self) -> str:
        # The policies are what the judge grades against: changing them makes it a different judge.
        return f"{self.name}:{self.model}:{self.rubric_version}:{_short_hash(self.rubric)}:{_short_hash(self.policy_text)}"

    def verdict(self, case, answer_text):
        user = (f"POLICY:\n{self.policy_text}\n\n"
                f"CUSTOMER QUESTION:\n{case.input}\n\n"
                f"ASSISTANT ANSWER:\n{answer_text}")
        reply = extract_json(self.chat.complete(self.rubric, user))
        verdict = str(reply.get("verdict", "")).strip().upper()
        if verdict not in ("PASS", "FAIL"):
            raise ValueError(f"judge returned an unreadable verdict: {reply!r}")
        return JudgeVerdict(passed=(verdict == "PASS"), reason=str(reply.get("reason", "")).strip())


def _short_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:8]
