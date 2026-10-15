"""Replay answers recorded from a live agent, so CI needs no API key and runs are repeatable.

Recording file: JSON Lines, one answer per line:
  {"case_id": "GD01", "question": "...", "conversation": [], "answer_text": "...", "tool_calls": null,
   "retrieved_documents": [...], "latency_ms": 2140.5, "agent_version": "...", "recorded_at": "..."}
Answers are matched by the question text plus the earlier turns of the conversation, so two
multi-turn cases that end with the same question ("Yes, please") don't get each other's answer.
Matching ignores case and extra spaces.
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from aiquality.contracts import AgentResponse, AgentUnderTest
from aiquality.errors import ConfigError, RecordingNotFoundError


class RecordedResponsesAgent(AgentUnderTest):
    """An agent that answers from a recording instead of calling a model."""

    def __init__(self, recording_path: Path, name: str = "recorded-agent"):
        self.recording_path = Path(recording_path)
        self.name = name
        self._answers_by_question, self.version = _load_recording(self.recording_path)

    def answer(self, question: str, conversation: Optional[list[dict]] = None) -> AgentResponse:
        row = self._answers_by_question.get(_answer_key(question, conversation))
        if row is None:
            raise RecordingNotFoundError(
                f"no recorded answer for this question in {self.recording_path.name}: {question[:80]!r}")
        return AgentResponse.from_dict(row)


@dataclass
class RecordingSummary:
    """What a recording run produced: answers written, and cases that failed (id -> reason)."""

    written: int = 0
    failed: dict = field(default_factory=dict)


def record_responses(agent: AgentUnderTest, cases: Iterable, output_path: Path) -> RecordingSummary:
    """Ask a live agent every case once and save the answers for later replay.

    A case whose call fails is skipped and listed in the summary; it is never
    written as a fake answer.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary = RecordingSummary()
    recorded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with output_path.open("w", encoding="utf-8") as handle:
        for case in cases:
            try:
                response = agent.answer(case.input, case.conversation_history or None)
            except Exception as error:  # one failed call must not stop the recording
                summary.failed[case.id] = f"{type(error).__name__}: {error}"
                continue
            row = {"case_id": case.id, "question": case.input,
                   "conversation": case.conversation_history or [], **response.to_dict(),
                   "agent_version": agent.version, "recorded_at": recorded_at}
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            summary.written += 1
    return summary


def _load_recording(path: Path) -> tuple[dict, str]:
    if not path.is_file():
        raise ConfigError(str(path), [
            f"recording not found: {path}. Record it once with: aiquality record --team <team>"])
    answers, versions = {}, set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            raise ConfigError(str(path), [f"line {line_number} is not valid JSON"])
        if "question" not in row or "answer_text" not in row:
            raise ConfigError(str(path), [f"line {line_number} needs 'question' and 'answer_text'"])
        answers[_answer_key(row["question"], row.get("conversation"))] = row
        versions.add(row.get("agent_version", "unversioned"))
    version = "recorded:" + ",".join(sorted(versions))
    return answers, version


def _answer_key(question: str, conversation: Optional[list[dict]]) -> str:
    key = " ".join(question.split()).lower()
    if conversation:
        turns = json.dumps([[t.get("role"), " ".join(str(t.get("content", "")).split()).lower()]
                            for t in conversation])
        key += "#" + hashlib.sha1(turns.encode("utf-8")).hexdigest()[:12]
    return key
