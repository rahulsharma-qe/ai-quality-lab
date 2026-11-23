"""Round 3's held-back questions: committed without the weak spots, pinned to the full file by its hash."""

import json

from held_back_questions import (COMMITMENT_FILE, FULL_FILE, QUESTIONS_FILE, active_questions, check_full_file,
                                 committed_sha256, questions_only, write_questions_file)

FULL = {"name": "held-back", "cases": [
    {"id": "HB01", "question": "Q one?", "policy": "P1", "weak_spot": "secret one"},
    {"id": "HB02", "question": "Q two?", "policy": "P2", "weak_spot": "secret two", "withdrawn": "exposed"},
    {"id": "HB03", "question": "Q three?", "policy": "P3", "weak_spot": "secret three"}]}


def write(path, data):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def test_the_questions_file_keeps_order_and_drops_the_weak_spots():
    questions = questions_only(FULL)
    assert [c["id"] for c in questions["cases"]] == ["HB01", "HB02", "HB03"]
    assert "secret" not in json.dumps(questions)


def test_a_withdrawn_question_is_never_asked_or_exported():
    assert [c["id"] for c in active_questions(questions_only(FULL))] == ["HB01", "HB03"]


def test_the_full_file_matches_its_commitment_and_rebuilds_the_questions(tmp_path):
    import hashlib
    full = write(tmp_path / "full.json", FULL)
    questions = tmp_path / "questions.json"
    write_questions_file(full, questions)
    commitment = tmp_path / "commitment.txt"
    commitment.write_text(f"date: 23-11-2026\nsha256: {hashlib.sha256(full.read_bytes()).hexdigest()}\n")
    assert check_full_file(full, questions, commitment) == []


def test_a_changed_full_file_is_caught(tmp_path):
    import hashlib
    full = write(tmp_path / "full.json", FULL)
    questions = tmp_path / "questions.json"
    write_questions_file(full, questions)
    commitment = tmp_path / "commitment.txt"
    commitment.write_text(f"sha256: {hashlib.sha256(full.read_bytes()).hexdigest()}\n")
    changed = {**FULL, "cases": [{**FULL["cases"][0], "question": "Q one, reworded?"}] + FULL["cases"][1:]}
    write(full, changed)
    assert len(check_full_file(full, questions, commitment)) == 2


def test_the_committed_files_hold_together():
    """Before round 3's freeze the full file isn't in the repository: the questions file must still hold no
    weak spot and the commitment must name a hash. Once the full file is committed, it must match both."""
    questions = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))
    assert len(committed_sha256(COMMITMENT_FILE)) == 64
    assert all(set(case) <= {"id", "question", "policy", "withdrawn"} for case in questions["cases"])
    assert len(active_questions(questions)) == 18
    if FULL_FILE.exists():
        assert check_full_file() == []
