"""
Key-free smoke tests for the studies in demos/
=============================================
The studies (the judge, its label set and validation, the first eval harness, the model layer) are
the repository's evidence; most now wrap the aiquality package, which has its own tests. These
check that the studies still run: no API key, no network, runs on every pull request.

  python -m pytest -q
"""

import json
import sys
import types
from collections import Counter

import pytest

import build_label_set
import eval_harness
import judge_validation
import llm
from answer_judge import LLMAnswerJudge, MockAnswerJudge, Verdict


# ---------- helpers ----------------------------------------------------------
class FakeChat(llm.ChatModel):
    """Stands in for a real model: returns a fixed reply."""

    def __init__(self, reply):
        super().__init__("fake-model")
        self.reply = reply

    def complete(self, system, user):
        return self.reply


class ScriptedJudge:
    """A judge whose verdicts we choose, to test the maths and the gate."""

    version = "scripted-judge:v1"

    def __init__(self, fails):
        self.fails = set(fails)

    def verdict(self, case, answer):
        return Verdict(case["id"] not in self.fails, "scripted")


def case(cid, human, category="happy"):
    return {"id": cid, "human_label": human, "category": category, "answer": "…", "input": "…"}


# ---------- the two numbers --------------------------------------------------
def test_two_numbers():
    cases = [case("A", "FAIL"), case("B", "FAIL"), case("C", "PASS"), case("D", "PASS")]
    judge = ScriptedJudge(fails={"A", "C"})          # catches A, misses B, wrongly fails C
    verdicts, errored = judge_validation.run_judge(judge, cases)
    s = judge_validation.score(cases, verdicts)
    assert errored == []
    assert s["catch_rate"] == 0.5                    # 1 of 2 human FAILs caught
    assert s["leave_alone_rate"] == 0.5              # 1 of 2 human PASSes left alone
    assert [d["id"] for d in judge_validation.disagreements(cases, verdicts)] == ["B", "C"]


def test_a_judge_that_fails_everything_does_not_qualify():
    cases = [case("A", "FAIL"), case("B", "PASS"), case("C", "PASS")]
    verdicts, _ = judge_validation.run_judge(ScriptedJudge(fails={"A", "B", "C"}), cases)
    overall = judge_validation.score(cases, verdicts)
    assert overall["catch_rate"] == 1.0
    assert not judge_validation.qualifies(overall)   # catching everything isn't enough


def test_a_failed_judge_call_is_left_out_not_counted():
    class Broken:
        version = "broken"

        def verdict(self, case, answer):
            raise ConnectionError("network glitch")

    verdicts, errored = judge_validation.run_judge(Broken(), [case("A", "FAIL")], retries=0)
    assert verdicts == {} and errored[0][0] == "A"


# ---------- trust is per judge version ---------------------------------------
def test_judge_status_reads_the_latest_held_back_run(tmp_path):
    results = tmp_path / "results.jsonl"
    rows = [
        {"judge_version": "j:v1", "split": "tune", "qualified": None},
        {"judge_version": "j:v1", "split": "holdout", "qualified": False},
        {"judge_version": "j:v2", "split": "holdout", "qualified": True},
    ]
    results.write_text("\n".join(json.dumps(r) for r in rows))
    assert judge_validation.judge_status("j:v1", results) == "not_qualified"
    assert judge_validation.judge_status("j:v2", results) == "qualified"
    assert judge_validation.judge_status("j:v3", results) == "unvalidated"


# ---------- the judges --------------------------------------------------------
def test_mock_judge_checks_required_and_forbidden_phrases():
    c = {"must_include": ["24 hours"], "must_not_include": ["30 days"]}
    assert MockAnswerJudge().verdict(c, "Refunds within 24 hours.").passed
    assert not MockAnswerJudge().verdict(c, "Refunds within 30 days.").passed
    assert not MockAnswerJudge().verdict(c, "You can get a refund.").passed


def test_llm_judge_reads_a_fenced_json_verdict():
    reply = '```json\n{"reason": "Says 30 days; policy says 24 hours.", "verdict": "FAIL"}\n```'
    judge = LLMAnswerJudge("POLICY", model="fake", chat=FakeChat(reply))
    v = judge.verdict({"input": "Refund?"}, "30 days")
    assert not v.passed and "24 hours" in v.reason
    assert judge.version.startswith("llm_answer_judge:fake:")


def test_llm_judge_rejects_an_unreadable_verdict():
    judge = LLMAnswerJudge("POLICY", model="fake", chat=FakeChat('{"reason": "?", "verdict": "maybe"}'))
    with pytest.raises(ValueError):
        judge.verdict({"input": "q"}, "a")


# ---------- the model layer ----------------------------------------------------
def test_model_layer_skips_thinking_and_retries_without_temperature(monkeypatch):
    block = types.SimpleNamespace

    class Messages:
        def create(self, model, max_tokens, system, messages):   # no 'temperature' allowed
            return block(content=[block(type="thinking", thinking="…"), block(type="text", text="ok")])

    fake_sdk = types.SimpleNamespace(Anthropic=lambda api_key: block(messages=Messages()))
    monkeypatch.setitem(sys.modules, "anthropic", fake_sdk)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    chat = llm.get_chat_model("any-model")
    assert chat.complete("system", "user") == "ok"
    assert chat._send_temperature is False


# ---------- the label set ------------------------------------------------------
def test_label_set_is_balanced_across_halves():
    golden = build_label_set.load_golden()
    real = [{"golden_id": g, "answer": "…", "answer_source": "agent", "failure_type": None}
            for g in build_label_set.REAL_CASE_IDS]
    records = build_label_set.assemble(real + build_label_set.seeded_answers(), golden)
    assert len(records) == 30
    assert Counter(r["split"] for r in records) == {"tune": 15, "holdout": 15}
    by_category = Counter((r["category"], r["split"]) for r in records)
    for category in {r["category"] for r in records}:
        assert by_category[(category, "tune")] == by_category[(category, "holdout")]


# ---------- advisory vs gate in the release pipeline ---------------------------
def live_judge_failing(record_id, version):
    judge = eval_harness.LiveJudge.__new__(eval_harness.LiveJudge)   # skip the real model
    judge.answer_judge = types.SimpleNamespace(
        version=version,
        verdict=lambda record, output: Verdict(record["id"] != record_id, "scripted"),
    )
    return judge


def test_unqualified_judge_is_advisory_and_cannot_block(tmp_path, monkeypatch):
    monkeypatch.setattr(judge_validation, "RESULTS_PATH", str(tmp_path / "none.jsonl"))
    judge = live_judge_failing("G2", version="new-judge:v1")          # never validated
    assert eval_harness.run_gate(eval_harness.RECORDS, eval_harness.OUTPUTS_GOOD, judge) == 0


def test_qualified_judge_gates(tmp_path, monkeypatch):
    results = tmp_path / "results.jsonl"
    results.write_text(json.dumps({"judge_version": "good-judge:v1", "split": "holdout", "qualified": True}))
    monkeypatch.setattr(judge_validation, "RESULTS_PATH", str(results))
    judge = live_judge_failing("G2", version="good-judge:v1")
    assert eval_harness.run_gate(eval_harness.RECORDS, eval_harness.OUTPUTS_GOOD, judge) == 1
