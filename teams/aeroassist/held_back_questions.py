"""Judge round 3's held-back questions, committed before the session without what each one aims at.

The full file, judge_holdout_cases.json, gives each question its policy pointer and the weak spot it aims
at. The labeller mustn't read the weak spots before round 3's freeze, so the full file stays out of the
repository until then. What is committed now:

    judge_holdout_questions.json     id, question and policy pointer (and "withdrawn" where a question
                                     was taken out), built from the full file by questions_only(), in the
                                     same order. This is what the session and the labelling export read.
    judge_holdout_commitment.txt     the date and the sha256 of the full file, so it can't change unseen.

After the freeze the full file is committed unchanged, and check_full_file() confirms that its hash
matches the commitment and that it rebuilds the questions file exactly. A mismatch means round 3 was not
pre-registered, and the log says so.
"""

import hashlib
import json
from pathlib import Path

TEAM_FOLDER = Path(__file__).resolve().parent
FULL_FILE = TEAM_FOLDER / "judge_holdout_cases.json"
QUESTIONS_FILE = TEAM_FOLDER / "judge_holdout_questions.json"
COMMITMENT_FILE = TEAM_FOLDER / "judge_holdout_commitment.txt"
KEPT_FIELDS = ("id", "question", "policy", "withdrawn")


def questions_only(full: dict) -> dict:
    """The full file without the weak-spot lines: only the kept fields, in the same order."""
    return {"name": full["name"],
            "cases": [{k: case[k] for k in KEPT_FIELDS if k in case} for case in full["cases"]]}


def active_questions(questions: dict) -> list:
    """The questions to ask and export: a withdrawn question is never asked or exported."""
    return [case for case in questions["cases"] if not case.get("withdrawn")]


def sha256_of(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_questions_file(full_path: Path = FULL_FILE, out_path: Path = QUESTIONS_FILE) -> None:
    full = json.loads(Path(full_path).read_text(encoding="utf-8"))
    Path(out_path).write_text(json.dumps(questions_only(full), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def committed_sha256(commitment_path: Path = COMMITMENT_FILE) -> str:
    for line in Path(commitment_path).read_text(encoding="utf-8").splitlines():
        if line.startswith("sha256:"):
            return line.split(":", 1)[1].strip()
    raise ValueError(f"{commitment_path} has no 'sha256:' line")


def check_full_file(full_path: Path = FULL_FILE, questions_path: Path = QUESTIONS_FILE,
                    commitment_path: Path = COMMITMENT_FILE) -> list:
    """Problems with the full file against the commitment and the committed questions; [] when it matches."""
    problems = []
    if sha256_of(full_path) != committed_sha256(commitment_path):
        problems.append("the full file's sha256 doesn't match the commitment: round 3 was not pre-registered")
    full = json.loads(Path(full_path).read_text(encoding="utf-8"))
    if questions_only(full) != json.loads(Path(questions_path).read_text(encoding="utf-8")):
        problems.append("the full file doesn't rebuild the committed questions file")
    return problems
