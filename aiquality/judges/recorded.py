"""Replay a judge's verdicts, so CI grades meaning without an API key.

Recording file: JSON Lines, one verdict per line:
  {"case_id": "GD01", "answer_sha": "3f2a...", "verdict": "PASS", "reason": "...",
   "judge_version": "...", "recorded_at": "..."}
A verdict belongs to one answer: it is looked up by case id plus a hash of the answer text, so
when the agent's answers are recorded again, old verdicts no longer match and the check says
"record the judge again" instead of reusing a verdict for a different answer.
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from aiquality.errors import ConfigError
from aiquality.judges.base import Judge, JudgeVerdict


class VerdictNotRecordedError(LookupError):
    """No recorded verdict for this exact answer."""


class RecordedJudge(Judge):
    """A judge that answers from a recording. Its version is the version of the judge that was
    recorded, so its validation status still applies."""

    def __init__(self, recording_path: Path):
        self.recording_path = Path(recording_path)
        self.name = "recorded"
        self._verdicts, self._version = _load(self.recording_path)

    @property
    def version(self) -> str:
        return self._version

    def verdict(self, case, answer_text):
        row = self._verdicts.get((case.id, answer_sha(answer_text)))
        if row is None:
            raise VerdictNotRecordedError(f"no recorded verdict for {case.id}'s current answer in "
                                          f"{self.recording_path.name}; record the judge again")
        return JudgeVerdict(row["verdict"] == "PASS", row.get("reason", ""))


@dataclass
class VerdictRecordingSummary:
    written: int = 0
    failed: dict = field(default_factory=dict)      # case id -> reason


def record_verdicts(judge: Judge, answers: Iterable, output_path: Path) -> VerdictRecordingSummary:
    """Grade every (case, answer_text) pair once with a live judge and save the verdicts.
    A call that fails is listed, never written as a made-up verdict."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary = VerdictRecordingSummary()
    recorded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with output_path.open("w", encoding="utf-8") as handle:
        for case, answer_text in answers:
            try:
                verdict = judge.verdict(case, answer_text)
            except Exception as error:  # noqa: BLE001  (one failed call must not stop the recording)
                summary.failed[case.id] = f"{type(error).__name__}: {error}"
                continue
            row = {"case_id": case.id, "answer_sha": answer_sha(answer_text), **verdict.to_dict(),
                   "judge_version": judge.version, "recorded_at": recorded_at}
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            summary.written += 1
    return summary


def answer_sha(answer_text: str) -> str:
    return hashlib.sha256(" ".join(answer_text.split()).encode()).hexdigest()[:16]


def _load(path: Path):
    if not path.is_file():
        raise ConfigError(str(path), [f"recorded judge verdicts not found: {path}. "
                                      "Record them once with: aiquality record --team <team> --judge"])
    verdicts, versions = {}, set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            verdicts[(row["case_id"], row["answer_sha"])] = row
            versions.add(row["judge_version"])
        except (json.JSONDecodeError, KeyError) as error:
            raise ConfigError(str(path), [f"line {line_number}: not a recorded verdict ({error})"])
    if len(versions) > 1:
        raise ConfigError(str(path), [f"verdicts from more than one judge version: {', '.join(sorted(versions))}"])
    return verdicts, (versions.pop() if versions else "empty-recording")
