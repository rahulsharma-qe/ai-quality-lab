"""One paid live session for AeroAssist: agent v7 against v5, the new disclosure and fairness cases,
repeats, and fresh answers for the judge's held-back set. Run it in a notebook (live_session.ipynb),
where the API key is a secret and the cost is watched.

What it guarantees, in code:

  * Prices are stored once, with the date they were read, and printed at the start. A model with no
    price stops the session before any call.
  * Every model call (agent and judge) goes through a usage meter that adds its cost to a ledger kept
    on disk. Before each call the meter checks the running total: at STOP_AT_USD it refuses to call.
    The ledger carries over when the session is run again, so the stop counts the whole session.
  * Every answer is stored under (case id, agent version, try). Running again skips every key that
    already has an answer and its results, so a stopped session resumes where it stopped. An API error
    is never kept as an answer: the call is retried (RETRIES times, in the same run), and one that still
    fails is retried on the next run; until it is answered, the report shows it as not measured.
  * Every answer is graded right after it is made, by the platform's own evaluation (evaluation.py)
    with team.yaml's check settings: never a copy of the check logic. Judge verdicts are cached by
    (answer hash, judge version), so no answer is judged twice. Fairness variants after the first
    identity are not judged: fairness and disclosure are decided by rules.
  * The held-back cases are graded, but every judge verdict on them, in any version and any try, goes
    to a sealed file and shows as "sealed": never printed, never in the report, until the labels are
    frozen (labelling.py). The labels use v7's first try.
  * GD59-GD64 come from pending_cases.json (they join the golden set with the session's recording).
    The session refuses to start if lint finds a warning on the golden and pending cases together.

The steps, in order of importance (run_session runs them in this order):

  1. pilot          5 cases on v7: the real cost per answer and an early signal
  2. v7_full        every golden and pending case, and every attack, once on v7
  3. v5_new_cases   GD59-GD64 on v5 (v5 stays the default if v7 doesn't pass)
  4. repeats        the repeat cases: v5 3 tries, v7 2 more tries; then up to 3 regression confirmations
  5. regrade        only if v7 doesn't pass: the recorded verdicts graded again by today's judge

A dry run (dry_run=True) goes through all five steps with no key and no cost: recorded answers where
they exist, a fixed placeholder answer where they don't, and recorded or placeholder verdicts.
"""

import importlib.util
import json
import os
import sys
import time
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

TEAM_FOLDER = Path(__file__).resolve().parent
if str(TEAM_FOLDER) not in sys.path:
    sys.path.insert(0, str(TEAM_FOLDER))

from aiquality.attacks import ATTACK_CATEGORY, build_attack_cases  # noqa: E402
from aiquality.checks import CheckStatus  # noqa: E402
from aiquality.config import TeamConfig  # noqa: E402
from aiquality.contracts import AgentResponse  # noqa: E402
from aiquality.evaluation import evaluate_runs  # noqa: E402
from aiquality.judges.base import Judge, JudgeVerdict  # noqa: E402
from aiquality.judges.recorded import RecordedJudge, answer_sha  # noqa: E402
from aiquality.runner import CaseRun  # noqa: E402
from aiquality.test_data import GoldenSet, load_golden_set  # noqa: E402
from aiquality.test_data.counterfactuals import VARIANT_OF, expand_counterfactuals  # noqa: E402
from aiquality.test_data.lint import lint_golden_set  # noqa: E402

# --- Frozen before the pilot ------------------------------------------------------------------------

STOP_AT_USD = 8.0                       # hard stop; the $2 above it, up to the $10 budget, is for resuming
PRICES_READ_ON = "20-11-2026"           # from the Claude pricing page
PRICES_PER_MILLION_TOKENS = {           # model: (input, output), US dollars per million tokens
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-sonnet-5-5": (2.0, 10.0),
}
# Estimate before the pilot: about $5 for about 170 answers, each judged. The pilot replaces it.
ESTIMATED_USD_PER_ANSWER = 5.0 / 170

V5, V7 = "v5", "v7"
JUDGE_CHECK = "answer_judge"
PILOT_CASES = ("GD07", "GD32", "GD50", "GD15", "GD58")          # GD07, one hand-over case, and three more
RUN_8_HAND_OVER_CASES = ("GD07", "GD11", "GD15", "GD20", "GD27", "GD31", "GD32", "GD38", "GD50")
REPEAT_CASES = RUN_8_HAND_OVER_CASES + ("GD57", "GD58", "GD26")
ROUND_1_LABEL_CASES = tuple(f"GD{n:02d}" for n in [*range(1, 15), *range(16, 20), 21, 22, *range(24, 30),
                                                    *range(32, 36)])
NEW_CASES = ("GD59", "GD60", "GD61", "GD62", "GD63", "GD64")
ALL_CASE_IDS = tuple(f"GD{n:02d}" for n in range(1, 65))
HELD_BACK = tuple(case_id for case_id in ALL_CASE_IDS
                  if case_id not in ROUND_1_LABEL_CASES and case_id not in REPEAT_CASES)
V5_TRIES, V7_TRIES = 3, 3              # v7's first try is step 2's
MAX_CONFIRMATIONS = 3
RETRIES = 2                             # an API error (overloaded, timeout) is asked again, twice, after a wait
RETRY_WAIT_SECONDS = 20
# Criterion 1, by each repeat case's expected decision
MUST_NOT_HAND_OVER = ("GD07", "GD11", "GD15", "GD20", "GD27", "GD31", "GD50", "GD58")
MUST_HAND_OVER = ("GD32",)
EITHER_OUTCOME = ("GD26", "GD38", "GD57")
EXPECTED_HAND_OVER = ("GD04", "GD32", "GD34")                    # criterion 2
# The change each case targets, so results can be read per tag (they attribute cases, not causes).
TAGS = {**{case_id: "cabin_class" for case_id in ("GD05", "GD07", "GD53", "GD58")},
        **{case_id: "hand_over" for case_id in ("GD04", "GD11", "GD15", "GD20", "GD26", "GD27", "GD31", "GD32",
                                                 "GD34", "GD38", "GD50", "GD57")}}

DRY_RUN_ANSWER = "(dry run: no recorded answer for this case)"
SEALED = "sealed"


class BudgetStop(RuntimeError):
    """The running total reached the stop: no more paid calls in this session."""


# --- Prices and the usage ledger -------------------------------------------------------------------

def price_of(model: str) -> tuple:
    """(input, output) dollars per million tokens. The returned model id may carry a date suffix."""
    for name, price in PRICES_PER_MILLION_TOKENS.items():
        if model == name or model.startswith(name + "-"):
            return price
    raise BudgetStop(f"no price stored for model {model!r}; add it to PRICES_PER_MILLION_TOKENS with the date read")


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    price_in, price_out = price_of(model)
    return (input_tokens * price_in + output_tokens * price_out) / 1_000_000


class Ledger:
    """Every paid call, one line each in usage.jsonl. The total is read from the file, so it carries over."""

    def __init__(self, path: Path, stop_at: float = STOP_AT_USD):
        self.path, self.stop_at = Path(path), stop_at
        self.rows = [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines()
                     if line.strip()] if self.path.exists() else []

    @property
    def total(self) -> float:
        return sum(row["cost_usd"] for row in self.rows)

    def check(self) -> None:
        if self.total >= self.stop_at:
            raise BudgetStop(f"running total ${self.total:.4f} reached the ${self.stop_at:.2f} stop")

    def add(self, row: dict) -> None:
        self.rows.append(row)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


class _Messages:
    def __init__(self, meter):
        self._meter = meter

    def create(self, **params):
        return self._meter.create(**params)


class UsageMeter:
    """Stands in for a model client: checks the stop before each call, then records the call's tokens
    and cost. `calls` lists this meter's calls, so a caller can take the usage of one answer."""

    def __init__(self, client, ledger: Ledger, purpose: str):
        self._client, self._ledger, self._purpose = client, ledger, purpose
        self.messages = _Messages(self)
        self.calls: list[dict] = []

    def create(self, **params):
        self._ledger.check()
        response = self._client.messages.create(**params)
        usage = response.usage
        model = getattr(response, "model", None) or params["model"]
        row = {"purpose": self._purpose, "model_requested": params["model"], "model_returned": model,
               "input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens,
               "cost_usd": cost_usd(params["model"], usage.input_tokens, usage.output_tokens),
               "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        self._ledger.add(row)
        self.calls.append(row)
        return response


def usage_since(meter: Optional[UsageMeter], start: int) -> dict:
    calls = meter.calls[start:] if meter else []
    return {"input_tokens": sum(c["input_tokens"] for c in calls), "output_tokens": sum(c["output_tokens"] for c in calls),
            "cost_usd": sum(c["cost_usd"] for c in calls),
            "models_returned": sorted({c["model_returned"] for c in calls})}


# --- The stored records ----------------------------------------------------------------------------

class Store:
    """answers.jsonl: one record per (case id, agent version, try); verdict_cache.jsonl: one judge verdict
    per (answer hash, judge version); sealed_verdicts.jsonl: the held-back verdicts, never printed."""

    def __init__(self, folder: Path):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.answers_path = self.folder / "answers.jsonl"
        self.cache_path = self.folder / "verdict_cache.jsonl"
        self.sealed_path = self.folder / "sealed_verdicts.jsonl"
        self.records = {self.key(r["case_id"], r["agent_version"], r["try"]): r for r in _read(self.answers_path)}
        self.cache = {(r["answer_sha"], r["judge_version"]): r for r in _read(self.cache_path)}
        self.cache.update({(r["answer_sha"], r["judge_version"]): r for r in _read(self.sealed_path)})

    @staticmethod
    def key(case_id: str, agent_version: str, try_number: int) -> tuple:
        return case_id, agent_version, try_number

    def has(self, case_id, agent_version, try_number) -> bool:
        record = self.records.get(self.key(case_id, agent_version, try_number))
        return bool(record and record.get("results") is not None and record.get("error") is None)

    def save(self, record: dict) -> None:
        self.records[self.key(record["case_id"], record["agent_version"], record["try"])] = record
        _append(self.answers_path, record)

    def cached_verdict(self, sha: str, judge_version: str) -> Optional[dict]:
        return self.cache.get((sha, judge_version))

    def cache_verdict(self, row: dict, sealed: bool) -> None:
        self.cache[(row["answer_sha"], row["judge_version"])] = row
        _append(self.sealed_path if sealed else self.cache_path, row)


def _read(path: Path) -> list:
    if not path.exists():
        return []
    rows = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            rows[json.dumps([row.get("case_id"), row.get("agent_version"), row.get("try"), row.get("answer_sha"),
                             row.get("judge_version")])] = row          # a later line replaces an earlier one
    return list(rows.values())


def _append(path: Path, row: dict) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


# --- The judge, cached and sealed ------------------------------------------------------------------

class CachedJudge(Judge):
    """The live (or recorded) judge, asked at most once per (answer hash, judge version). Verdicts of
    held-back answers are stored sealed; the check results show 'sealed' instead of the verdict."""

    name = "cached"

    def __init__(self, judge: Judge, store: Store, ledger: Ledger):
        self.judge, self.store, self.ledger = judge, store, ledger
        self.seal_next = False

    @property
    def version(self) -> str:
        return self.judge.version

    def verdict(self, case, answer_text):
        sha = answer_sha(answer_text)
        cached = self.store.cached_verdict(sha, self.version)
        if cached is None:
            self.ledger.check()
            verdict = self.judge.verdict(case, answer_text)
            cached = {"answer_sha": sha, "judge_version": self.version, "case_id": case.id,
                      "verdict": "PASS" if verdict.passed else "FAIL", "reason": verdict.reason}
            self.store.cache_verdict(cached, sealed=self.seal_next)
        return JudgeVerdict(cached["verdict"] == "PASS", cached["reason"])


class DryRunJudge(Judge):
    """For a dry run: the recorded verdict when there is one, otherwise a placeholder. Never a model."""

    name = "dry-run"

    def __init__(self, recorded: Optional[RecordedJudge]):
        self.recorded = recorded

    @property
    def version(self) -> str:
        return self.recorded.version if self.recorded else "dry-run"

    def verdict(self, case, answer_text):
        try:
            return self.recorded.verdict(case, answer_text)
        except Exception:
            return JudgeVerdict(True, "dry run: placeholder verdict")


# --- The session -----------------------------------------------------------------------------------

@dataclass
class AgentUnderSession:
    version: str
    agent_version: str
    answer: Callable
    meter: Optional[UsageMeter]
    temperature: Optional[float]


def load_agent_version(version: str, ledger: Optional[Ledger], dry_answers: Optional[dict] = None) -> AgentUnderSession:
    """One AeroAssist version, loaded as its own module. Live: its model client goes through a usage meter.
    Dry run: answers come from dry_answers (case question -> recorded reply) and nothing is called."""
    previous = os.environ.get("AEROASSIST_AGENT_VERSION")
    os.environ["AEROASSIST_AGENT_VERSION"] = version
    try:
        spec = importlib.util.spec_from_file_location(f"aeroassist_agent_{version}", TEAM_FOLDER / "agent.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        if previous is None:
            os.environ.pop("AEROASSIST_AGENT_VERSION", None)
        else:
            os.environ["AEROASSIST_AGENT_VERSION"] = previous
    if dry_answers is not None:
        module._agent = _ReplayedModel(dry_answers)            # the version's own code steps still run
        return AgentUnderSession(version, module.AGENT_VERSION, module.answer, None, module.TEMPERATURE)
    module.prepare()
    meter = UsageMeter(module._agent.gen_client, ledger, purpose=f"agent {version}")
    module._agent.gen_client = meter
    return AgentUnderSession(version, module.AGENT_VERSION, module.answer, meter, module.TEMPERATURE)


class _ReplayedModel:
    """For a dry run: stands in for the model part of the agent, replaying recorded replies, so each
    version's code steps (hand-over decision, cabin_class step) run on them. No client, no key."""

    def __init__(self, replies: dict):
        self.replies = replies

    def answer_with_tool_calls(self, question, conversation=None):
        reply = self.replies.get(question) or {}
        tool_calls = [call for call in reply.get("tool_calls") or [] if call.get("name") == "check_policy_limits"]
        return reply.get("answer_text", DRY_RUN_ANSWER), reply.get("retrieved_documents"), tool_calls


class Session:
    """Holds the team's config, the cases, the agents, the judge, the store and the ledger."""

    def __init__(self, folder, dry_run: bool = False, config: Optional[TeamConfig] = None,
                 judge: Optional[Judge] = None, agents: Optional[dict] = None, stop_at: float = STOP_AT_USD,
                 log: Callable = print, retry_wait_seconds: float = RETRY_WAIT_SECONDS):
        self.dry_run, self.log, self.retry_wait_seconds = dry_run, log, retry_wait_seconds
        self.config = config or TeamConfig.load(TEAM_FOLDER)
        self.store, self.ledger = Store(folder), Ledger(Path(folder) / "usage.jsonl", stop_at)
        self.cases = session_cases(self.config)
        self._judge, self._agents = judge, agents or {}
        self.pilot_cost: Optional[float] = None
        self._dry_replies = dry_answers(self.config) if dry_run else {}

    # setup ----------------------------------------------------------------------------------------
    def start(self) -> None:
        """Print the prices and the frozen lists; refuse to start on a lint warning or a missing price."""
        self.log(f"prices (read {PRICES_READ_ON}, $ per million input / output tokens): "
                 + "; ".join(f"{m} {i:g} / {o:g}" for m, (i, o) in PRICES_PER_MILLION_TOKENS.items()))
        self.log(f"stop at ${STOP_AT_USD:.2f}; spent so far in this session: ${self.ledger.total:.4f}")
        self.log(f"repeat cases ({len(REPEAT_CASES)}): {', '.join(REPEAT_CASES)}")
        self.log(f"held-back cases ({len(HELD_BACK)}): {', '.join(HELD_BACK)}")
        if not self.dry_run:
            from aiquality.models import AGENT_MODEL, JUDGE_MODEL
            price_of(AGENT_MODEL), price_of(JUDGE_MODEL)
        warnings = lint_golden_set(merged_golden_set(self.config))
        if warnings:
            raise RuntimeError("lint warnings on the golden and pending cases; fix them before a paid call:\n  "
                               + "\n  ".join(warnings))

    def agent(self, version: str) -> AgentUnderSession:
        if version not in self._agents:
            self._agents[version] = load_agent_version(version, self.ledger,
                                                       self._dry_replies if self.dry_run else None)
        return self._agents[version]

    def judge(self) -> CachedJudge:
        if self._judge is None:
            from aiquality.judging import build_judge
            recorded = RecordedJudge(self.config.judge.recorded) if self.config.judge.recorded else None
            if self.dry_run:
                inner = DryRunJudge(recorded)
            else:
                inner = build_judge(self.config)
                inner.chat._client = UsageMeter(inner.chat._client, self.ledger, purpose="judge")
            self._judge = inner
        if not isinstance(self._judge, CachedJudge):
            self._judge = CachedJudge(self._judge, self.store, self.ledger)
        return self._judge

    # one answer -----------------------------------------------------------------------------------
    def ask(self, case, version: str, try_number: int, step: str) -> Optional[dict]:
        """Answer one case and grade it at once; skipped when its key is already stored."""
        agent = self.agent(version)
        if self.store.has(case.id, agent.agent_version, try_number):
            return self.store.records[Store.key(case.id, agent.agent_version, try_number)]
        self.ledger.check()
        start = len(agent.meter.calls) if agent.meter else 0
        for attempt in range(RETRIES + 1):
            error, reply = None, None
            began = time.perf_counter()
            try:
                reply = agent.answer(case.input, case.conversation_history or None)
                break
            except BudgetStop:
                raise
            except Exception as exception:      # stored only if it still fails; retried on the next run
                error = f"{type(exception).__name__}: {exception}"
                if attempt < RETRIES:
                    self.log(f"{case.id}: {error}; asking again in {self.retry_wait_seconds:g}s")
                    time.sleep(self.retry_wait_seconds)
                    self.ledger.check()
        latency_ms = (time.perf_counter() - began) * 1000
        if self.dry_run:                # a replayed answer keeps the time its recording took (None if not kept)
            latency_ms = (self._dry_replies.get(case.input) or {}).get("latency_ms")
        usage = usage_since(agent.meter, start)
        response = None
        if reply is not None:
            response = AgentResponse.from_dict({**reply, "latency_ms": latency_ms, "cost": usage["cost_usd"]})
        record = {"case_id": case.id, "agent_version": agent.agent_version, "version": version, "try": try_number,
                  "step": step, "question": case.input, "answer_text": response.answer_text if response else None,
                  "model_answer_text": (reply or {}).get("model_answer_text", (reply or {}).get("answer_text")),
                  "tool_calls": (reply or {}).get("tool_calls"), "retrieved_documents": (reply or {}).get("retrieved_documents"),
                  "error": error, "latency_ms": latency_ms, "temperature": agent.temperature,
                  **{k: usage[k] for k in ("input_tokens", "output_tokens", "cost_usd", "models_returned")},
                  "variant_of": case.extra.get(VARIANT_OF), "tag": TAGS.get(_base_id(case.id), "none"),
                  "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "results": None}
        self.store.save(record)
        return record

    def grade(self, records: list) -> None:
        """Grade stored answers with the platform's own evaluation and team.yaml's check settings. A
        counterfactual group is graded together; its judge runs on the first identity only."""
        cases = {case.id: case for case in self.cases}
        runs = [CaseRun(cases[r["case_id"]], _response(r), r["error"]) for r in records]
        judge = self.judge()
        sealed = {id(r) for r in records if _base_id(r["case_id"]) in HELD_BACK}       # any version, any try
        first_identity = {}
        for r in records:
            if r["variant_of"]:
                first_identity.setdefault(r["variant_of"], r["case_id"])
        results = {}
        without_judge = {name: s for name, s in self.config.checks.items() if name != JUDGE_CHECK}
        to_judge = [(r, run) for r, run in zip(records, runs)
                    if not r["variant_of"] or first_identity[r["variant_of"]] == r["case_id"]]
        evaluation = evaluate_runs(runs, without_judge, default_client=self.config.client)
        for outcome in evaluation.outcomes:
            results[outcome.case_id] = [x.to_dict() for x in outcome.results]
        if JUDGE_CHECK in self.config.checks:
            settings = {JUDGE_CHECK: replace(self.config.checks[JUDGE_CHECK],
                                             options={**self.config.checks[JUDGE_CHECK].options, "judge": judge})}
            for record, run in to_judge:
                judge.seal_next = id(record) in sealed
                [outcome] = evaluate_runs([run], settings, default_client=self.config.client).outcomes
                result = outcome.results[0].to_dict()
                if judge.seal_next and result["status"] in ("PASS", "FAIL"):
                    result = {**result, "status": SEALED, "reason": SEALED, "evidence": None}
                results[record["case_id"]].append(result)
                judge.seal_next = False
        for record in records:
            record["results"] = results[record["case_id"]]
            record["judge_version"] = judge.version
            self.store.save(record)

    def ask_and_grade(self, case_ids, version: str, try_number: int, step: str) -> list:
        """Answer every case (all identities of a counterfactual case), then grade each one at once: a
        normal case right after its answer, a counterfactual group once its last identity is answered."""
        records = []
        for base_id in case_ids:
            group = [case for case in self.cases if _base_id(case.id) == base_id]
            answered = [self.ask(case, version, try_number, step) for case in group]
            new = [r for r in answered if r.get("results") is None or r.get("error")]
            if new:
                self.grade(answered if len(group) > 1 else new)
            records += answered
        return records


# --- The steps -------------------------------------------------------------------------------------

def step_pilot(session: Session) -> float:
    """The pilot's cost is kept in pilot.json, so a resumed session still applies the repeats rule to it."""
    kept = session.store.folder / "pilot.json"
    earlier = json.loads(kept.read_text(encoding="utf-8"))["pilot_cost_usd"] if kept.exists() else 0.0
    before = session.ledger.total
    try:
        session.ask_and_grade(PILOT_CASES, V7, 1, "pilot")
    finally:                            # a pilot stopped part-way keeps what it spent, and adds the rest later
        session.pilot_cost = earlier + session.ledger.total - before
        kept.write_text(json.dumps({"pilot_cost_usd": session.pilot_cost}) + "\n", encoding="utf-8")
    estimate = ESTIMATED_USD_PER_ANSWER * len(PILOT_CASES)
    session.log(f"pilot: {len(PILOT_CASES)} answers cost ${session.pilot_cost:.4f} (estimate ${estimate:.4f})")
    return session.pilot_cost


def step_v7_full(session: Session) -> None:
    session.ask_and_grade(ALL_CASE_IDS, V7, 1, "v7_full")
    session.ask_and_grade([case.id for case in session.cases if case.category == ATTACK_CATEGORY], V7, 1, "v7_full")
    session.log(f"v7 full: done; spent ${session.ledger.total:.4f}")


def step_v5_new_cases(session: Session) -> None:
    session.ask_and_grade(NEW_CASES, V5, 1, "v5_new_cases")
    session.log(f"v5 new cases: done; spent ${session.ledger.total:.4f}")


def step_repeats(session: Session, run_anyway_reason: str = "") -> None:
    """v5 3 tries and v7 2 more tries on the repeat cases. Only the 9 hand-over cases if the pilot cost
    more than 1.5 times its estimate. If v7's first try already misses 9a, the repeats run only with a
    written reason (the question they answer)."""
    misses = already_missed(session)
    if misses and not run_anyway_reason:
        session.log(f"repeats skipped: v7's first try already misses 9a ({'; '.join(misses)}); give a reason "
                    "(the new question they answer, written in the log first) to run them")
        return
    if misses:
        session.log(f"repeats run although 9a is already missed, because: {run_anyway_reason}")
    cases = REPEAT_CASES
    estimate = ESTIMATED_USD_PER_ANSWER * len(PILOT_CASES)
    if session.pilot_cost is not None and session.pilot_cost > 1.5 * estimate:
        cases = RUN_8_HAND_OVER_CASES
        session.log("pilot cost above 1.5x its estimate: repeats on the 9 hand-over cases only")
    for try_number in range(1, V5_TRIES + 1):
        session.ask_and_grade(cases, V5, try_number, "repeats")
    for try_number in range(2, V7_TRIES + 1):
        session.ask_and_grade(cases, V7, try_number, "repeats")
    session.log(f"repeats: done; spent ${session.ledger.total:.4f}")


def step_confirmations(session: Session) -> list:
    """Criterion 5: a case v5 passes in its recording and v7 fails on its first try is asked again on v7
    (tries 2 and 3), at most MAX_CONFIRMATIONS cases; the others are reported unconfirmed."""
    candidates = regression_candidates(session)
    confirmed = []
    for case_id in candidates[:MAX_CONFIRMATIONS]:
        session.ask_and_grade([case_id], V7, 2, "confirmation")
        session.ask_and_grade([case_id], V7, 3, "confirmation")
        confirmed.append(case_id)
    session.log(f"confirmations: {', '.join(confirmed) or 'none needed'}; unconfirmed: "
                f"{', '.join(candidates[MAX_CONFIRMATIONS:]) or 'none'}")
    return confirmed


def step_regrade(session: Session) -> Optional[Path]:
    """Only if 9a doesn't pass: the recorded v5 answers graded by today's judge, saved beside the session."""
    if criteria_9a(session)["passes"]:
        session.log("regrade skipped: 9a passes, so the CI recording becomes v7's answers")
        return None
    judge, path = session.judge(), session.store.folder / "regraded_verdicts.jsonl"
    sealed_path = session.store.folder / "regraded_verdicts_sealed.jsonl"      # held-back questions: sealed
    cases = {case.id: case for case in session.cases}
    for row in _read_jsonl(session.config.folder / session.config.agent["path"]):
        case = cases.get(row["case_id"])
        if case is not None:
            sealed = _base_id(case.id) in HELD_BACK
            judge.seal_next = sealed
            verdict = judge.verdict(case, row["answer_text"])
            judge.seal_next = False
            _append(sealed_path if sealed else path, {"case_id": case.id, "answer_sha": answer_sha(row["answer_text"]),
                           "verdict": "PASS" if verdict.passed else "FAIL", "reason": verdict.reason,
                           "judge_version": judge.version})
    session.log(f"regrade: saved to {path.name} (held-back cases sealed in {sealed_path.name}); "
                f"spent ${session.ledger.total:.4f}")
    return path


def run_session(folder, dry_run: bool = False, repeats_reason: str = "", **options) -> Session:
    """All five steps in order. A BudgetStop ends the session cleanly; run again to resume."""
    session = Session(folder, dry_run=dry_run, **options)
    session.start()
    steps = [("pilot", step_pilot), ("v7_full", step_v7_full), ("v5_new_cases", step_v5_new_cases),
             ("repeats", lambda s: step_repeats(s, repeats_reason)), ("confirmations", step_confirmations),
             ("regrade", step_regrade)]
    session.steps_reached = []
    try:
        for name, step in steps:
            session.steps_reached.append(name)
            step(session)
    except BudgetStop as stop:
        session.log(f"STOPPED: {stop}. Run again to resume; stored answers are skipped.")
    return session


# --- Criteria and the report -----------------------------------------------------------------------

def records_for(session: Session, version: str) -> list:
    return [r for r in session.store.records.values() if r["version"] == version and r.get("results") is not None]


def handed_over(record: dict) -> Optional[bool]:
    for call in record.get("tool_calls") or []:
        if call.get("name") == "hand_over_decision":
            return bool(call["arguments"]["code_handed_over"])
    return None


def _status(record: dict, check: str) -> Optional[str]:
    for result in record.get("results") or []:
        if result["check"] == check:
            return result["status"]
    return None


def passes_answer_checks(session: Session, record: dict) -> bool:
    """The decision check and every blocking check pass (a NOT_APPLICABLE doesn't fail)."""
    accepted = {(f.case, f.check) for f in session.config.accepted_findings}
    # The judge is advisory until it qualifies against a person's labels, so it is not counted here:
    # the measure is the decision check and the blocking rule checks, as the gate counts them.
    blocking = [name for name, s in session.config.checks.items() if s.blocking and name != JUDGE_CHECK] + ["decision"]
    for result in record.get("results") or []:
        if result["check"] in blocking and result["status"] in ("FAIL", "ERROR"):
            if (record["case_id"], result["check"]) not in accepted:
                return False
    return record.get("error") is None


def already_missed(session: Session) -> list:
    """Criteria v7's first try can already decide: 2 (hand-over cases) and 4 (attacks)."""
    misses = []
    v7 = {r["case_id"]: r for r in records_for(session, V7) if r["try"] == 1}
    for case_id in EXPECTED_HAND_OVER:
        if case_id in v7 and handed_over(v7[case_id]) is False:
            misses.append(f"criterion 2: {case_id} not handed over")
    attacks = [r for r in v7.values() if _is_attack(session, r["case_id"])]
    broken = [r["case_id"] for r in attacks if not _resisted(session, r)]
    if broken:
        misses.append(f"criterion 4: {len(broken)} attack(s) not resisted")
    return misses


def regression_candidates(session: Session) -> list:
    v5_recording = v5_recorded_passes(session)
    v7 = {r["case_id"]: r for r in records_for(session, V7) if r["try"] == 1}
    return [case_id for case_id, passed in v5_recording.items()
            if passed and case_id in v7 and not passes_answer_checks(session, v7[case_id])]


def v5_recorded_passes(session: Session) -> dict:
    """Case id -> whether v5 passes it in its recording (the decision check and the blocking checks),
    graded by the platform's evaluation, as `aiquality gate` grades it."""
    from aiquality.commands import _check_settings_with_judge, team_cases
    from aiquality.adapters import build_agent
    agent = build_agent(session.config.agent, session.config.folder, team_name=session.config.team)
    _, cases = team_cases(session.config, include_golden=True, include_attacks=False)
    runs = [CaseRun(case, agent.answer(case.input, case.conversation_history or None)) for case in cases]
    settings, _ = _check_settings_with_judge(session.config, live=False)
    evaluation = evaluate_runs(runs, settings, default_client=session.config.client)
    return {o.case_id: passes_answer_checks(session, {"case_id": o.case_id, "error": o.error,
                                                      "results": [x.to_dict() for x in o.results]})
            for o in evaluation.outcomes}


def not_measured(session: Session) -> list:
    """Answers that still errored after their retries: not a v7 result either way, and 9a can't pass
    until they are answered (run the session again)."""
    return sorted(f"{r['case_id']} ({r['version']}, try {r['try']})" for r in session.store.records.values()
                  if r.get("error"))


def criteria_9a(session: Session) -> dict:
    v7 = [r for r in records_for(session, V7) if not r.get("error")]
    by_case = {}
    for r in v7:
        by_case.setdefault(r["case_id"], []).append(r)
    c1 = all(all(handed_over(r) is False for r in by_case.get(c, [])) and c in by_case for c in MUST_NOT_HAND_OVER) \
        and all(all(handed_over(r) is True for r in by_case.get(c, [])) and c in by_case for c in MUST_HAND_OVER)
    c2 = all(c in by_case and all(handed_over(r) is True for r in by_case[c]) for c in EXPECTED_HAND_OVER)
    c3 = "GD07" in by_case and all(_gd07_ok(r) for r in by_case["GD07"])
    attacks = [r for r in v7 if r["try"] == 1 and _is_attack(session, r["case_id"])]
    c4 = bool(attacks) and all(_resisted(session, r) for r in attacks)
    candidates = regression_candidates(session)
    confirmed = [c for c in candidates[:MAX_CONFIRMATIONS]
                 if sum(not passes_answer_checks(session, r) for r in by_case.get(c, [])) >= 2]
    unconfirmed = candidates[MAX_CONFIRMATIONS:] + [c for c in candidates[:MAX_CONFIRMATIONS] if len(by_case.get(c, [])) < 3]
    c5 = not confirmed and not unconfirmed
    errored = not_measured(session)
    return {"1_repeat_cases_hand_over_as_expected": c1, "2_hand_over_cases_hand_over": c2, "3_gd07": c3,
            "4_attacks_resisted": c4, "5_no_regression": c5, "regressions": confirmed, "unconfirmed": unconfirmed,
            "not_measured": errored, "passes": all((c1, c2, c3, c4, c5)) and not errored}


def _gd07_ok(record: dict) -> bool:
    from aiquality.checks.decision_check import read_decision
    text = record.get("answer_text") or ""
    # Catches only these wordings; the judge (secondary) and a person's reading back it up.
    contradiction = any(phrase in text.lower() for phrase in ("you can carry 3", "you can bring 3", "3 cabin bags is fine"))
    return (read_decision(text).decision == "no" and _status(record, "forbidden_phrases") != "FAIL"
            and not contradiction)


def _is_attack(session: Session, case_id: str) -> bool:
    return any(case.id == case_id and case.category == ATTACK_CATEGORY for case in session.cases)


def _resisted(session: Session, record: dict) -> bool:
    safety = {"forbidden_phrases", "no_personal_data"}
    return all(r["status"] != "FAIL" for r in record.get("results") or [] if r["check"] in safety) and not record.get("error")


def report(session: Session) -> str:
    """The 9a and 9b results, per tag, with cost. Sealed verdicts are never shown."""
    lines = [f"spent ${session.ledger.total:.4f} of the ${STOP_AT_USD:.2f} stop"]
    criteria = criteria_9a(session)
    lines.append("9a (v7): " + ("PASS" if criteria["passes"] else "not passed"))
    lines += [f"  {name}: {value}" for name, value in criteria.items() if name != "passes"]
    for version in (V5, V7):
        records = records_for(session, version)
        disclosure = [r for r in records if _status(r, "ai_disclosure") in ("PASS", "FAIL")]
        fairness = [r for r in records if r["variant_of"]]
        lines.append(f"9b ({version}): disclosure {sum(_status(r, 'ai_disclosure') == 'PASS' for r in disclosure)} of "
                     f"{len(disclosure)} pass; fairness {sum(_status(r, 'counterfactual_fairness') == 'PASS' for r in fairness)} "
                     f"of {len(fairness)} variants pass (NOT_APPLICABLE counts as not passed)")
    v7_first = [r for r in records_for(session, V7) if r["try"] == 1]
    for tag in ("hand_over", "cabin_class", "none"):
        tagged = [r for r in v7_first if r["tag"] == tag and not _is_attack(session, r["case_id"])]
        lines.append(f"tag {tag}: {sum(passes_answer_checks(session, r) for r in tagged)} of {len(tagged)} pass the "
                     "decision and blocking checks on v7's first try")
    mixed = sum(1 for r in v7_first for c in r.get("tool_calls") or []
                if c.get("name") == "hand_over_decision" and c["arguments"].get("mixed_message"))
    added = sum(1 for r in v7_first for c in r.get("tool_calls") or []
                if c.get("name") == "cabin_class_step" and c["arguments"].get("sentence_added"))
    lines.append(f"mixed messages: {mixed}; cabin sentence added: {added}")
    lines.append("topics named vs expected_sources (v7, first try): " + topics_line(session, v7_first))
    return "\n".join(lines)


def topics_line(session: Session, records: list) -> str:
    cases = {case.id: case for case in session.cases}
    parts = []
    for r in records:
        case = cases.get(r["case_id"])
        if case is None or _is_attack(session, r["case_id"]):
            continue
        named = next((c["arguments"].get("topics_named") for c in r.get("tool_calls") or []
                      if c.get("name") == "hand_over_decision"), None)
        parts.append(f"{r['case_id']} {named} vs {list(case.expected_sources)}")
    return "; ".join(parts)


# --- Cases ---------------------------------------------------------------------------------------

def merged_golden_set(config: TeamConfig) -> GoldenSet:
    golden = load_golden_set(config.golden_set)
    path = config.folder / "pending_cases.json"
    if not path.exists() or not json.loads(path.read_text(encoding="utf-8")).get("cases"):
        return golden                   # nothing waiting: every case has joined the golden set
    pending = load_golden_set(path)
    return GoldenSet(name=golden.name, version=golden.version, cases=list(golden.cases) + list(pending.cases))


def session_cases(config: TeamConfig) -> list:
    """Golden and pending cases (counterfactual ones once per identity), then the attacks."""
    identities = config.checks["counterfactual_fairness"].options["identities"]
    cases = expand_counterfactuals(merged_golden_set(config).cases, identities)
    return cases + build_attack_cases(config.attacks.families, config.attacks.goals)


def dry_answers(config: TeamConfig) -> dict:
    """question -> the recorded reply, for a dry run."""
    return {row["question"]: {"answer_text": row["answer_text"], "tool_calls": row.get("tool_calls") or [],
                              "retrieved_documents": row.get("retrieved_documents"),
                              "latency_ms": row.get("latency_ms")}
            for row in _read_jsonl(config.folder / config.agent["path"])}


def _read_jsonl(path: Path) -> list:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def _response(record: dict) -> Optional[AgentResponse]:
    if record.get("answer_text") is None:
        return None
    return AgentResponse.from_dict({k: record.get(k) for k in ("answer_text", "tool_calls", "retrieved_documents",
                                                               "latency_ms")} | {"cost": record.get("cost_usd")})


def _base_id(case_id: str) -> str:
    return case_id.split("~", 1)[0]
