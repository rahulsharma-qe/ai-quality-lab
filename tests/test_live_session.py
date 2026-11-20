"""teams/aeroassist/live_session.py: the paid session's guarantees, checked with no key and no cost."""

import json
from types import SimpleNamespace

import pytest

import live_session as ls
from aiquality.commands import gate_team
from aiquality.config import TeamConfig


def quiet(*_):
    pass


@pytest.fixture(scope="module")
def dry(tmp_path_factory):
    folder = tmp_path_factory.mktemp("dry")
    return ls.run_session(folder, dry_run=True, log=quiet)


def test_the_frozen_lists_are_the_designs():
    assert ls.REPEAT_CASES == ("GD07", "GD11", "GD15", "GD20", "GD27", "GD31", "GD32", "GD38", "GD50",
                               "GD57", "GD58", "GD26")
    assert ls.HELD_BACK == ("GD23", "GD30", "GD36", "GD37", "GD39", "GD40", "GD41", "GD42", "GD43", "GD44", "GD45",
                            "GD46", "GD47", "GD48", "GD49", "GD51", "GD52", "GD53", "GD54", "GD55", "GD56", "GD59",
                            "GD60", "GD61", "GD62", "GD63", "GD64")
    assert not set(ls.HELD_BACK) & (set(ls.ROUND_1_LABEL_CASES) | set(ls.REPEAT_CASES))
    assert set(ls.MUST_NOT_HAND_OVER) | set(ls.MUST_HAND_OVER) | set(ls.EITHER_OUTCOME) == set(ls.REPEAT_CASES)


def test_a_dry_run_reaches_all_five_steps_and_pays_nothing(dry):
    assert dry.steps_reached == ["pilot", "v7_full", "v5_new_cases", "repeats", "confirmations", "regrade"]
    assert dry.ledger.total == 0 and not (dry.store.folder / "usage.jsonl").exists()
    versions = {r["version"] for r in dry.store.records.values()}
    assert versions == {"v5", "v7"}
    v7_first = [r for r in dry.store.records.values() if r["version"] == "v7" and r["try"] == 1]
    assert len(v7_first) == 58 + 2 + 4 * 4 + 16                 # golden, GD59-60, 4 x 4 identities, attacks


def test_the_lint_on_golden_and_pending_together_is_clean():
    from aiquality.test_data.lint import lint_golden_set
    assert lint_golden_set(ls.merged_golden_set(TeamConfig.load(ls.TEAM_FOLDER))) == []


def test_a_lint_warning_stops_the_session_before_any_call(tmp_path, monkeypatch):
    monkeypatch.setattr(ls, "lint_golden_set", lambda golden_set: ["GD61: no {passenger} slot"])
    with pytest.raises(RuntimeError, match="lint warnings"):
        ls.Session(tmp_path, dry_run=True, log=quiet).start()


def test_v7s_code_steps_run_in_the_dry_run(dry):
    gd07 = dry.store.records[("GD07", dry.agent("v7").agent_version, 1)]
    assert [c["name"] for c in gd07["tool_calls"]][-1] == "hand_over_decision"
    assert gd07["model_answer_text"] and gd07["tag"] == "cabin_class"


def test_held_back_verdicts_are_sealed_and_never_reported(dry):
    v7 = dry.agent("v7").agent_version
    held = [r for r in dry.store.records.values() if r["version"] == "v7" and r["try"] == 1
            and ls._base_id(r["case_id"]) in ls.HELD_BACK]
    judged = [r for r in held for x in r["results"] if x["check"] == "answer_judge"]
    assert judged and all(x["status"] == "sealed" and x["reason"] == "sealed"
                          for r in judged for x in r["results"] if x["check"] == "answer_judge")
    sealed_rows = (dry.store.folder / "sealed_verdicts.jsonl").read_text(encoding="utf-8")
    assert sealed_rows.strip()
    report = ls.report(dry)
    for row in sealed_rows.splitlines():
        assert json.loads(row)["reason"] not in report or json.loads(row)["reason"] == ""
    assert ("GD23", v7, 1) in dry.store.records                          # graded, stored, just not shown


def test_fairness_variants_after_the_first_identity_are_not_judged(dry):
    v7 = dry.agent("v7").agent_version
    first = dry.store.records[("GD62~name=Satyam Dixit", v7, 1)]
    later = dry.store.records[("GD62~name=Kushal Kumar", v7, 1)]
    assert any(x["check"] == "answer_judge" for x in first["results"])
    assert not any(x["check"] == "answer_judge" for x in later["results"])
    assert any(x["check"] == "counterfactual_fairness" for x in later["results"])


def test_grading_matches_aiquality_gate_case_by_case(tmp_path):
    """On v5's recorded answers, the session's grading (the platform's evaluation with team.yaml's settings)
    gives every golden case the same result per check as `aiquality gate`."""
    config = TeamConfig.load(ls.TEAM_FOLDER)
    session = ls.Session(tmp_path / "s", dry_run=True, config=config, log=quiet)
    golden_ids = [case.id for case in session.cases if case.id.startswith("GD") and int(case.id[2:4]) <= 58]
    records = session.ask_and_grade(golden_ids, "v5", 1, "check")
    record, _ = gate_team(config, output_dir=tmp_path / "runs", print_reports=False)
    gate = {o["case_id"]: {r["check"]: r["status"] for r in o["results"]} for o in record.to_dict()["outcomes"]
            if o["case_id"] in golden_ids}
    mine = {r["case_id"]: {x["check"]: x["status"] for x in r["results"]} for r in records}
    for case_id in ls.HELD_BACK:                       # the judge's verdict on a held-back case stays sealed
        if case_id in mine:
            assert mine[case_id].pop("answer_judge") == "sealed"
            gate[case_id].pop("answer_judge")
    assert mine == gate


# --- The $8 stop and resume, with simulated usage --------------------------------------------------

class FakeClient:
    """Each call 'costs' 1M input tokens on haiku: $1."""

    def __init__(self):
        self.messages = self
        self.calls = 0

    def create(self, **params):
        self.calls += 1
        return SimpleNamespace(usage=SimpleNamespace(input_tokens=1_000_000, output_tokens=0), model=params["model"])


def fake_agent(ledger, version):
    client = FakeClient()
    meter = ls.UsageMeter(client, ledger, purpose=f"agent {version}")

    def answer(question, conversation=None):
        meter.messages.create(model="claude-haiku-4-5", messages=[])
        return {"answer_text": "No.", "tool_calls": []}
    return ls.AgentUnderSession(version, f"fake-{version}", answer, meter, 0), client


def test_the_stop_fires_and_a_rerun_skips_stored_answers_and_carries_the_total(tmp_path):
    session = ls.Session(tmp_path, dry_run=True, stop_at=3.0, log=quiet)
    session._agents["v7"], first_client = fake_agent(session.ledger, "v7")
    with pytest.raises(ls.BudgetStop):
        session.ask_and_grade(ls.PILOT_CASES, "v7", 1, "pilot")
    assert first_client.calls == 3 and session.ledger.total == 3.0               # no call past the stop
    stored = [k for k in session.store.records]
    assert len(stored) == 3

    again = ls.Session(tmp_path, dry_run=True, stop_at=5.0, log=quiet)
    assert again.ledger.total == 3.0                                           # carried over from usage.jsonl
    again._agents["v7"], second_client = fake_agent(again.ledger, "v7")
    again.ask_and_grade(ls.PILOT_CASES, "v7", 1, "pilot")
    assert second_client.calls == 2 and again.ledger.total == 5.0             # the 3 stored ones were skipped
    assert len(again.store.records) == 5
    with pytest.raises(ls.BudgetStop):                                        # at the stop: no further call
        again.ask_and_grade(["GD01"], "v7", 1, "v7_full")
    assert second_client.calls == 2


def test_every_record_keeps_the_fields_the_design_asks_for(tmp_path):
    session = ls.Session(tmp_path, dry_run=True, log=quiet)
    session._agents["v7"], _ = fake_agent(session.ledger, "v7")
    [record] = session.ask_and_grade(["GD07"], "v7", 1, "pilot")
    for field in ("input_tokens", "output_tokens", "cost_usd", "models_returned", "latency_ms", "model_answer_text",
                  "tool_calls", "temperature", "agent_version", "judge_version", "try", "results"):
        assert field in record
    assert record["input_tokens"] == 1_000_000 and record["cost_usd"] == 1.0


def test_a_model_with_no_price_stops_before_any_call():
    with pytest.raises(ls.BudgetStop, match="no price"):
        ls.price_of("claude-unknown-1")
    assert ls.price_of("claude-haiku-4-5-20251001") == (1.0, 5.0)              # a dated id finds its price


def test_repeats_need_a_reason_once_v7s_first_try_already_misses(dry, tmp_path, monkeypatch):
    messages = []
    session = ls.Session(dry.store.folder, dry_run=True, log=messages.append)
    monkeypatch.setattr(ls, "already_missed", lambda s: ["criterion 2: GD04 not handed over"])
    ls.step_repeats(session)
    assert "repeats skipped" in messages[-1]


# --- An API error is retried, never kept as an answer; a held-back verdict is sealed in every record ---

def failing_then_answering_agent(failures):
    calls = {"n": 0}

    def answer(question, conversation=None):
        calls["n"] += 1
        if calls["n"] <= failures:
            raise RuntimeError("overloaded_error 529")
        return {"answer_text": "A human agent will take over from here.",
                "tool_calls": [{"name": "hand_over_decision", "arguments": {"code_handed_over": True}}]}
    return ls.AgentUnderSession("v7", "fake-v7", answer, None, 0), calls


def test_an_api_error_is_retried_in_the_same_run(tmp_path):
    session = ls.Session(tmp_path, dry_run=True, log=quiet, retry_wait_seconds=0)
    session._agents["v7"], calls = failing_then_answering_agent(failures=2)
    [record] = session.ask_and_grade(["GD32"], "v7", 1, "pilot")
    assert calls["n"] == 3 and record["error"] is None and ls.handed_over(record) is True


def test_an_answer_that_still_errors_is_retried_on_resume_and_reported_not_measured(tmp_path):
    session = ls.Session(tmp_path, dry_run=True, log=quiet, retry_wait_seconds=0)
    session._agents["v7"], calls = failing_then_answering_agent(failures=3)
    [record] = session.ask_and_grade(["GD32"], "v7", 1, "pilot")
    assert calls["n"] == 3 and record["error"].startswith("RuntimeError")
    assert not session.store.has("GD32", "fake-v7", 1)
    assert "GD32 (v7, try 1)" in ls.criteria_9a(session)["not_measured"]
    assert ls.criteria_9a(session)["passes"] is False
    again = ls.Session(tmp_path, dry_run=True, log=quiet, retry_wait_seconds=0)
    again._agents["v7"], calls_again = failing_then_answering_agent(failures=0)
    [retried] = again.ask_and_grade(["GD32"], "v7", 1, "pilot")
    assert calls_again["n"] == 1 and retried["error"] is None
    assert Store_record(again, "GD32", "fake-v7", 1)["error"] is None
    assert "GD32 (v7, try 1)" not in ls.criteria_9a(again)["not_measured"]


def Store_record(session, case_id, agent_version, try_number):
    return session.store.records[ls.Store.key(case_id, agent_version, try_number)]


def test_a_held_back_verdict_is_sealed_in_every_version_and_try(tmp_path):
    session = ls.Session(tmp_path, dry_run=True, log=quiet)

    def same_answer(version):
        return ls.AgentUnderSession(version, f"fake-{version}", lambda q, c=None: {"answer_text": "Hello!",
                                                                                   "tool_calls": []}, None, 0)
    session._agents["v7"], session._agents["v5"] = same_answer("v7"), same_answer("v5")
    for version, try_number in (("v7", 1), ("v5", 1), ("v7", 2)):
        [record] = session.ask_and_grade(["GD23"], version, try_number, "probe")
        judge = [x for x in record["results"] if x["check"] == "answer_judge"]
        assert judge and judge[0]["status"] == "sealed" and judge[0]["reason"] == "sealed"
    assert not (tmp_path / "verdict_cache.jsonl").exists() or "GD23" not in (tmp_path / "verdict_cache.jsonl").read_text()


def test_the_pilot_cost_is_kept_so_a_resumed_session_still_applies_the_repeats_rule(tmp_path):
    session = ls.Session(tmp_path, dry_run=True, log=quiet)
    session._agents["v7"], _ = fake_agent(session.ledger, "v7")
    assert ls.step_pilot(session) == 5.0
    again = ls.Session(tmp_path, dry_run=True, log=quiet)
    again._agents["v7"], client = fake_agent(again.ledger, "v7")
    assert ls.step_pilot(again) == 5.0 and again.pilot_cost == 5.0 and client.calls == 0


def test_the_advisory_judge_doesnt_decide_pass_or_regression(tmp_path):
    """A judge FAIL alone doesn't fail a case: until the judge qualifies, the measure is the decision check
    and the blocking rule checks (as the gate counts them)."""
    session = ls.Session(tmp_path, dry_run=True, log=quiet)
    record = {"case_id": "GD01", "error": None,
              "results": [{"check": "answer_judge", "status": "FAIL"}, {"check": "decision", "status": "PASS"},
                          {"check": "required_phrases", "status": "PASS"}]}
    assert ls.passes_answer_checks(session, record) is True
    record["results"][2]["status"] = "FAIL"
    assert ls.passes_answer_checks(session, record) is False


def test_the_regrade_keeps_held_back_verdicts_sealed(tmp_path, monkeypatch):
    """The regrade judges v5's recorded answers, held-back questions among them: those verdicts go to their
    own sealed file, like every other verdict on a held-back case."""
    session = ls.Session(tmp_path, dry_run=True, log=quiet)
    monkeypatch.setattr(ls, "criteria_9a", lambda s: {"passes": False})
    ls.step_regrade(session)
    shown = (tmp_path / "regraded_verdicts.jsonl").read_text(encoding="utf-8")
    sealed = (tmp_path / "regraded_verdicts_sealed.jsonl").read_text(encoding="utf-8")
    assert '"GD23"' not in shown and '"GD23"' in sealed and '"GD01"' in shown
