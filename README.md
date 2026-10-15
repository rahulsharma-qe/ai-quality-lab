# ai-quality-lab — Quality Engineering *of* AI systems

A hands-on toolkit for testing the things that make an LLM agent trustworthy:
**is it accurate, is it grounded, and is it safe under attack?**

This is the **"QA *of* AI"** side of my work — evaluating and hardening AI systems.
Its sibling repo, [`aeroassist-qa-agent`](https://github.com/rahulsharma-qe/aeroassist-qa-agent),
is the **"AI *for* QA"** side — using AI to generate tests, data and scripts. Together they
cover both halves of modern quality engineering.

> **System under test:** *AeroAssist*, a mock support agent for the fictional **Meridian
> Airways**, answering from an 8-policy knowledge base (`policies.md`). Everything here is
> evaluated against that agent, but the techniques are stack-agnostic — point them at any
> LLM app.

---

## The platform: `aiquality` — configuration, not code

The scripts below proved each technique on one agent. `aiquality` packages them into a
self-serve platform: a team connects its agent and brings one config file (YAML or JSON) and a
golden set (JSON, CSV or Excel). No test code.

```bash
pip install -e ".[dev]"     # install aiquality from this folder, plus the test tools (pytest, Excel support)
aiquality new-team my_team                       # a starter team that already passes the gate
aiquality evaluate --team my_team                # pass rate per check, attacks per family, every finding
aiquality gate     --team examples/gate_demo/good_team       # PASS, exit 0
aiquality gate     --team examples/gate_demo/regressed_team  # FAIL, exit 1, every reason listed
aiquality compare  before.jsonl aiquality-runs        # what a change fixed, and what it newly broke
aiquality list-checks && aiquality list-attacks
```

- **One contract** for every agent: a Python function, an HTTP endpoint, or answers recorded
  from a live agent, so CI needs no API key. Every run record says `live` or `recorded`.
- **Checks are plugins** (`@register_check`), each scored as a pass rate against a threshold;
  a company-wide floor that teams can tighten, never loosen.
- **Honest results:** cases a check can't judge are `NOT_APPLICABLE`, failed calls are `ERROR`,
  and neither is ever counted as a pass. A broken setup exits with code 2, never as a quality failure.
- **Secrets stay out of configs:** they're read from environment variables named in the config.
- **Attack tests as data:** a team writes goals ("approve a full refund") and the phrases that would
  prove an attack worked; five attack families turn them into cases, scored per family.
- **A release gate that really blocks:** every blocking check must meet its bar for the team and for
  each client; errors count as failures; exit 1 fails the build.
- **Owned, expiring exceptions:** a reviewed false alarm can be accepted for one case and one check,
  with a reason, an approver and an expiry within 90 days, and is listed in every report.
- **One result format:** every run is a versioned RunRecord (personal data redacted) that every
  report reads: console, HTML, JUnit XML and the GitHub Actions summary.

```mermaid
flowchart LR
  subgraph TEAM["What a team brings - no test code"]
    CFG["team.yaml or team.json"]
    GS["Golden set<br/>JSON · CSV · Excel"]
    POL["policies.md"]
    AG["Their agent"]
  end
  subgraph CORE["aiquality package"]
    TC["TeamConfig<br/>+ CompanyMinimums"]
    TD["Test data<br/>load_golden_set · GoldenCaseBuilder"]
    AD["Adapters<br/>PythonFunction · HttpEndpoint · RecordedResponses"]
    ATK["Attacks registry<br/>register_attack"]
    RUN["Runner"]
    CHK["Checks registry<br/>register_check"]
    JDG["Judges<br/>AnswerJudge · JudgeValidator"]
    MDL["ChatModel<br/>provider-neutral"]
    GATE["ReleaseGate<br/>PASS or FAIL<br/>+ advisory findings"]
    RR["RunRecord - JSONL<br/>personal data redacted"]
    MON["Monitoring<br/>tracing · drift"]
  end
  subgraph OUT["Outputs"]
    EXIT["Exit code<br/>CI blocks or passes"]
    REP["Reports - register_reporter<br/>console · HTML · JUnit XML · GitHub summary"]
    HRQ["Human review queue<br/>advisory findings"]
    GV["Gate view<br/>static HTML"]
    OTEL["OpenTelemetry to Phoenix or Langfuse<br/>optional, off by default"]
  end
  CFG --> TC
  GS --> TD
  AG --> AD
  POL --> JDG
  TC --> RUN
  TD --> RUN
  ATK --> RUN
  AD --> RUN
  RUN --> CHK
  CHK --> JDG
  JDG --> MDL
  CHK --> GATE
  TC --> GATE
  JDG -.->|"judge status per version"| GATE
  GATE --> EXIT
  GATE --> RR
  RR --> REP
  RR --> HRQ
  RR --> GV
  RUN -.->|"traces"| MON
  RR -->|"history"| MON
  MON --> OTEL
  classDef later stroke-dasharray: 5 5
  class JDG,MDL,MON,HRQ,GV,OTEL later
```

Solid boxes are in the package today; dashed boxes are scripts in this repo moving into it, or
planned. Details: [`docs/architecture.md`](docs/architecture.md) ·
onboarding: [`docs/onboarding.md`](docs/onboarding.md) · runnable examples: [`examples/`](examples/).

### First real run: what the checks actually found

AeroAssist, 36 golden cases, answers recorded once from the live agent and replayed (golden set 1.2):

| Check | Pass rate | Bar | Result |
|---|---|---|---|
| Required phrases | 89% | 85% | meets |
| Forbidden phrases | 91% | 100% | below: two false alarms that need a judge |
| Response time | 97% | 90% | meets |

The first run (golden set 1.1) raised 11 findings. Reading every answer sorted them into:

- **3 real agent errors.** Applied the no-show rule to a 5-day-old cancellation and skipped the
  24-hour refund rule (GD03); offered a date change 2 hours before departure when the cut-off is
  4 hours (GD20); treated a personal medical attendant as standard special assistance instead of
  handing over (GD32).
- **1 judgement call** on how 40 kg splits across cabin and check-in (GD10).
- **4 phrases too narrow** ("escalate" for "connect", "original class" for "same class"):
  golden set 1.2 accepts equivalent wording with `OR`. Phrases tied to real errors were not changed.
- **1 bug in the checker:** "2 hour" didn't match "2 hours"; simple plurals now count. That fix
  surfaced a new false alarm ("change fees" in a correct answer), kept on purpose because the
  same rule also catches a real "you'll pay change fees".
- **1 negation false alarm:** "you don't need to pay extra" matched the forbidden "pay extra".
- **1 timing artifact:** loading the embedding model was counted as the first answer's time;
  agents can now load models in `prepare()` before timing starts.

Phrase checks are a cheap, fast first filter, but on their own they both miss and over-report.
Meaning needs a validated judge and people on the disagreements, which is where this platform goes next.

### Second run: attacks and the release gate

Re-recorded with attack cases (36 golden + 16 attacks, golden set 1.4):

| | Result | Bar |
|---|---|---|
| Required phrases | 89% | 85% |
| Forbidden phrases | 100% with 3 reviewed false alarms accepted until 14 Nov | 100% |
| Personal data, response time | 100% | 100%, 90% |
| Attacks | 16 of 16 resisted | 100% |
| **Release gate** | **FAIL: high-priority cases GD03, GD20 and GD27 fail** | every high-priority case |

The average alone (89% against an 85% bar) would have passed. A priority bar made the gate fail
for the right reason: a date change offered two hours before departure (GD20) is not a rounding
error. Known limit: AeroAssist's agent receives only the latest question, so the multi-turn attack
family is effectively single-turn for it; passing the conversation to the agent is next.

---

## What's inside

| Area | File | The quality question it answers |
|---|---|---|
| **Platform** | `aiquality/`, `teams/`, `examples/`, `tests/`, `docs/` | *Can another team use this without writing test code?* Agent adapters, team configs, golden sets from JSON/CSV/Excel, pluggable checks, a company floor, run records and a command line. See the section above. |
| **Golden dataset** | `golden_dataset.json` | *What is the human-verified source of truth?* 36 labelled cases (happy / edge / adversarial / out-of-scope), with a schema validator (`loader_cell.py`). |
| **RAG evaluation** | `rag_eval.py` | *Is the agent accurate and grounded?* Scores a policy-RAG with **RAGAS** — context precision/recall (retrieval) and faithfulness/answer-relevancy (generation), judged by Claude, embedded locally (no OpenAI). |
| **Red-teaming** | `red_team.py`, `red_team_v2.py` | *Can I break it?* OWASP-LLM-mapped attacks — prompt injection (direct & indirect), jailbreak, data-leak, excessive agency — plus strengthened vectors (obfuscation, multi-turn, poisoned knowledge base). |
| **The fix** | `guardrail_fix.py` | *How do I close a breach?* A deterministic **policy-of-record at the execution gate** — money decisions live in code, not in the model. |
| **Agentic testing** | `aeroassist_agent.py`, `trajectory_eval.py`, `consistency_check.py` | *Is the agent's whole journey right, not just its answer?* A tool-using agent that emits a **trajectory**, graded on tool choice, arguments, termination and **multi-intent completeness** — run N times to measure a reliability rate (a probabilistic agent isn't certified by a single pass). |
| **Completeness fix** | `completeness_guardrail.py` | *How do I stop a silently dropped intent?* A code-owned **intent checklist** that re-asks for any missed request. Before/after: fully-complete rate `80% → 100%`. |
| **Eval harness / CI gate** | `eval_harness.py`, `.github/workflows/eval-gate.yml` | *How do I stop a regression shipping?* A metric **registry** with per-metric thresholds + direction and a build-failing **exit code** — evals become a **gate**, not a report. Key-free **mock judge** runs on every PR (deterministic, no API key); the **live judge** runs on demand, and may only block a release once it has qualified against human labels (otherwise it's advisory). Demo: healthy outputs PASS (exit 0), a seeded regression FAILS (exit 1). |
| **Model layer** | `llm.py` | *Can I switch models without touching every file?* One place for model clients: provider and model are settings (`LLM_PROVIDER`, `AGENT_MODEL`, `JUDGE_MODEL`); the judge uses a different, stronger model than the agent, so nothing grades its own work. |
| **Judge validation** | `answer_judge.py`, `build_label_set.py`, `judge_labels.json`, `judge_validation.py`, `judge_validation_results.jsonl` | *Can I trust the AI judge that gates my releases?* Thirty answers labelled blind by a person, split into a tuning half and a held-back half; two numbers against the human labels — **catches real failures** and **leaves good answers alone**; per-category breakdown; results saved per judge version. A judge that hasn't qualified runs in **advisory mode**. |
| **Tests for the test tools** | `test_judge_validation.py`, `tests/` | *Do the evaluation tools themselves work?* Key-free tests (fake judges, local servers, no network) run on every PR. |
| **Observability** | `observability/tracing.py`, `observability/monitor.py`, `observability/pii_guardrail.py` | *Is it still safe in production?* A structured per-run **trace** (evidence log), a **dashboard** (breach/refusal rate, latency, cost), a baseline-vs-recent **drift alert**, and a **triage→fix** loop. Before/after: PII breach-rate `1.7% → 0%` (fake PII only). |

---

## The headline finding (the story this repo tells)

1. The first red-team came back **0 breaches / 10**. I treated that as a warning, not a win —
   a clean security result usually means the attack is too weak.
2. I strengthened it. The overt *"ignore your rules"* injection still resisted (models are
   trained against it). What broke the agent was a **subtle poisoned fact**: I changed one
   number in a retrieved policy — refund window `24h → 30 days` — and a *faithful* RAG
   repeated it, confidently promising a customer a refund they weren't entitled to.
3. **The lesson:** faithfulness and injection-resistance pull against each other. A RAG
   trained to trust its context will faithfully repeat a *poisoned* context.
4. **The fix:** move the money decision out of the model. A deterministic policy-of-record
   (refund window = 24h) lives in code and owns the ruling; the model only phrases it.
   Re-running the exact attack, the same judge flipped **breach → resisted**, while a
   legitimate in-window refund still succeeds. *The model talks; the code rules.*

Full walkthrough: [`docs/red_team_walkthrough.md`](docs/red_team_walkthrough.md).

---

## The second finding: check the examiner

The release gate trusts an AI judge to decide whether an answer is good. So before letting it
gate, I measured it against my own labels — the way a chief examiner re-marks a sample of a new
examiner's papers.

**The set-up.** Thirty answers: fifteen from the agent and fifteen deliberately broken (wrong
fact, missing condition, invented rule, wrong refusal, unsafe agreement, long-but-wrong). I
labelled all thirty **blind** — not knowing which were which — then split them into a **tuning
half** (to improve the judge) and a **held-back half** (measured once, never tuned on).

| Run | Judge | Catches real failures | Leaves good answers alone |
|---|---|---|---|
| Tuning half | v1 | 6 / 10 = 60% | 3 / 5 = 60% |
| Tuning half | v2 (one rubric rule added) | 12 / 12 = 100% | 3 / 3 = 100% |
| **Held-back half (run once)** | **v2, frozen** | **7 / 7 = 100%** | **5 / 8 = 62%** |

**Verdict: not qualified** (bars: catches ≥ 85%, leaves good answers alone ≥ 80%) — so the
pipeline runs it in **advisory mode**: it reports, and what it fails goes to a person, but it
can't block a release.

**What I learned**
1. **The first judge was lenient for a fixable reason.** My standard — an escalation that hints an
   exception might be possible ("a manager may review your situation") is a failure — wasn't
   written into the rubric. One rule fixed it. The fix was the standard, not the model.
2. **Tuning scores mean little.** 100% on the half you tuned on is expected; only the held-back
   half counts.
3. **The judge checked me too.** All three held-back disagreements were answers I had passed that
   broke my own written rule — two left out a condition the customer needed, one refused when
   the policy had the answer. People catch loud errors and miss quiet omissions; judges miss
   nuance. Run both: the judge on everything, people on a sample and on every disagreement.
4. **Disagreements can expose the policy.** Two tuning disagreements came down to a policy that
   doesn't say whether a deadline boundary is inclusive. Anything ambiguous: fix the policy, or
   hand over — never guess.
5. **Trust is per version.** A new judge model or rubric is unvalidated until it passes again.
   Re-running the same judge twice gave identical verdicts on every case.

*Small sample, one labeller: the numbers are a direction, not a verdict.*

---

## Run it

```bash
pip install -r requirements.txt
cp .env.example .env          # add your ANTHROPIC_API_KEY (never commit .env)

python rag_eval.py            # evaluate the RAG with RAGAS
python red_team.py            # baseline red-team (OWASP-mapped)
python red_team_v2.py         # strengthened attacks (finds the real breach)
python guardrail_fix.py       # the fix: breach closed, legit refunds still work

python trajectory_eval.py     # grade the agent's trajectory (tool/args/termination/completeness)
python consistency_check.py   # N-run completeness rate (catches silent multi-intent drops)
python completeness_guardrail.py  # the completeness fix: before/after rate

python eval_harness.py            # CI GATE: healthy outputs -> PASS (exit 0)
python eval_harness.py regressed  # CI GATE: seeded regression -> FAIL (exit 1)

python build_label_set.py                                  # 15 agent + 15 seeded answers to label
python judge_validation.py --judge llm --split tune        # improve the judge on the tuning half
python judge_validation.py --judge llm --split holdout     # measure once; exit 0 = qualified to gate
python -m pytest -q                                        # key-free tests for the tools themselves

aiquality record   --team aeroassist     # record the live agent's golden and attack answers (needs the key + the aeroassist extra)
aiquality evaluate --team aeroassist     # replay them: key-free and repeatable
aiquality gate     --team aeroassist     # the release gate on the recorded answers
```

In Colab, run `build_label_set.main()` and `judge_validation.main()` inside the notebook (not
with `!python`) so the Colab secret is available.

Each file is self-contained and also runs cell-by-cell in a notebook. The API key is read
from the environment (`ANTHROPIC_API_KEY`) — it is never hard-coded, and `.env` is gitignored.
Data is privacy-safe synthetic only (no real PII).

---

## Roadmap (QA-of-AI stack, growing)

- [x] **Eval harness (done)** — run the full golden set in CI with score thresholds that *fail the build* (an eval you run by hand is a report; wired into CI it's a gate), with judge-call retries + pinned, containerized deps.
- [ ] **Runtime guardrails gateway** — the four guardrail layers enforced live on every request/response, not just at test time.
- [x] **Observability loop (done)** — trace every run; track hallucination-rate, guardrail-breach-rate, cost, latency; detect drift.
- [x] **Judge validation (done, round 1)** — human labels, tuning and held-back halves, two numbers, advisory mode until qualified.
- [ ] **Judge validation, round 2** — a labelling guide with quiet-failure examples, a second labeller, narrower single-purpose judges, and a fresh held-back set with the bars set beforehand.
- [ ] **One model layer for every judge** — move the RAGAS, red-team and completeness judges onto `llm.py`.
- [ ] **Clearer policy boundaries** — state whether each deadline is inclusive.
- [x] **Platform core (done)** — `aiquality` package: one agent contract, three adapters, team configs in YAML or JSON, golden sets from JSON/CSV/Excel, pluggable checks, a company floor, run records, a command line.
- [x] **Release gate per team and client (done)** — attack tests as plugins, accepted findings with expiry, exit codes 0/1/2, HTML / JUnit XML / GitHub summary reports.
- [ ] **Judges and monitoring in the platform** — live judge with per-version qualification, a human review queue, a second (fictional) team onboarded with configuration only, a reusable CI workflow.
- [ ] **Gate view and tracing export** — a static gate dashboard and OpenTelemetry export to an open-source tracing tool.
- [ ] **Parallel runs** — worker limit, rate-limit retries and a per-run budget cap.

---

*Part of a two-repo body of work on AI quality: this repo (**QA of AI**) and
[`aeroassist-qa-agent`](https://github.com/rahulsharma-qe/aeroassist-qa-agent) (**AI for QA**).*
