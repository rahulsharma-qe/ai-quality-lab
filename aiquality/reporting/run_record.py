"""RunRecord: the one result format every command writes and every report reads.

Saved as JSON Lines (one run per line) so runs can be compared over time, and so other
tools (a dashboard, the AI-for-QA track) can read the same shape. schema_version changes
whenever a field changes meaning.
"""

import json
import subprocess
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from aiquality.evaluation import Evaluation
from aiquality.reporting.redaction import redact_personal_data

SCHEMA_VERSION = "1"
RUN_RECORDS_FILE = "run_records.jsonl"


@dataclass
class RunRecord:
    command: str
    team: str
    client: Optional[str]
    run_mode: str                    # "live" (the agent really answered) or "recorded" (replayed answers)
    agent_name: str
    agent_version: str
    golden_set_name: str
    golden_set_version: str
    golden_set_source: str
    case_count: int
    summaries: list[dict]
    outcomes: list[dict]
    attacks: Optional[dict] = None         # attack resistance, overall and per family
    gate_decision: Optional[dict] = None   # filled by the release gate
    judge: Optional[dict] = None           # filled when a judge takes part
    golden_set_warnings: list = field(default_factory=list)   # from the golden-set lint
    description: str = ""                  # the team's own one-line description, shown in reports
    expected_result: Optional[str] = None  # set for a gate self-test: the result the gate must give
    schema_version: str = SCHEMA_VERSION
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    git_commit: Optional[str] = field(default_factory=lambda: _current_git_commit())

    @classmethod
    def from_evaluation(cls, evaluation: Evaluation, *, command: str, team: str, client: Optional[str],
                        run_mode: str, agent_name: str, agent_version: str, golden_set) -> "RunRecord":
        outcomes = []
        for o in evaluation.outcomes:
            outcomes.append({
                "case_id": o.case_id, "category": o.category, "priority": o.priority, "client": o.client,
                "attack_family": o.attack_family,
                "question": redact_personal_data(o.question),
                "answer_text": redact_personal_data(o.answer_text),
                "error": o.error,
                "results": [{**r.to_dict(), "evidence": redact_personal_data(r.evidence)} for r in o.results],
            })
        return cls(command=command, team=team, client=client, run_mode=run_mode, agent_name=agent_name,
                   agent_version=agent_version, golden_set_name=golden_set.name,
                   golden_set_version=golden_set.version, golden_set_source=golden_set.source,
                   case_count=len(evaluation.outcomes),
                   summaries=[s.to_dict() for s in evaluation.summaries.values()], outcomes=outcomes,
                   attacks=evaluation.attacks.to_dict() if evaluation.attacks else None)

    def to_dict(self) -> dict:
        return asdict(self)

    def save(self, output_dir: Path) -> Path:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / RUN_RECORDS_FILE
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(self.to_dict(), ensure_ascii=False) + "\n")
        return path


def load_run_records(path: Path) -> list[RunRecord]:
    records = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(RunRecord(**json.loads(line)))
    return records


def _current_git_commit() -> Optional[str]:
    try:
        result = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None
