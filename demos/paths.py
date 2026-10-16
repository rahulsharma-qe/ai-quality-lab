"""Where the studies in demos/ find AeroAssist's files, wherever they are run from.

AeroAssist's agent and data live with its team in teams/aeroassist/. Importing this module also
puts that folder (for the agent's code) and the repository root (for the aiquality package, if it
isn't installed) on the import path, so `python demos/<script>.py` works from any folder.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
AEROASSIST = REPO_ROOT / "teams" / "aeroassist"

POLICIES = AEROASSIST / "policies.md"
GOLDEN_SET = AEROASSIST / "golden_dataset.json"
JUDGE_LABELS = AEROASSIST / "judge_labels.json"
JUDGE_RESULTS = AEROASSIST / "judge_validation_results.jsonl"
JUDGE_RUBRIC = AEROASSIST / "judge_rubric.md"

for folder in (AEROASSIST, REPO_ROOT):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
