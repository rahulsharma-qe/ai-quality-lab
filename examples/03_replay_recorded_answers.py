"""Example 03: record a live agent's answers once, then replay them with no model calls.

This is how a team that needs an API key still gets a key-free, repeatable check in CI:
record in a safe place (for example Colab, with the key as a secret), commit the file,
and let CI replay it. Run records mark these runs as run_mode "recorded".

The command-line equivalent for a team is:  aiquality record --team <team>
Run:  python examples/03_replay_recorded_answers.py
"""

import tempfile
from pathlib import Path

from aiquality import PythonFunctionAgent, RecordedResponsesAgent, load_golden_set
from aiquality.adapters import record_responses
from sample_store_agent import answer as sample_store_answer

DATA = Path(__file__).parent / "data"
golden_set = load_golden_set(DATA / "sample_golden_set.json")

live_agent = PythonFunctionAgent(sample_store_answer, name="sample-store", version="sample-store-1")
recording = Path(tempfile.mkdtemp()) / "recorded_answers.jsonl"

summary = record_responses(live_agent, golden_set.cases, recording)
print(f"recorded {summary.written} answers, {len(summary.failed)} failed -> {recording.name}")

replay_agent = RecordedResponsesAgent(recording)
print("replay agent version:", replay_agent.version)
for case in golden_set:
    print(f"  {case.id}: {replay_agent.answer(case.input).answer_text}")
