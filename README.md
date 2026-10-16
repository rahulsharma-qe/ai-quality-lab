# ai-quality-lab — Quality Engineering *of* AI systems

A hands-on toolkit for testing the things that make an LLM agent trustworthy:
**is it accurate, is it grounded, and is it safe under attack?**

This is the **"QA *of* AI"** side of my work — evaluating and hardening AI systems.
Its sibling repo, [`aeroassist-qa-agent`](https://github.com/rahulsharma-qe/aeroassist-qa-agent),
is the **"AI *for* QA"** side — using AI to generate tests, data and scripts. Together they
cover both halves of modern quality engineering.

> **System under test:** *AeroAssist*, a mock support agent for the fictional **Meridian
> Airways**, answering from an 8-policy knowledge base ([`teams/aeroassist/policies.md`](teams/aeroassist/policies.md)). Everything here is
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
aiquality validate-judge --team aeroassist --split holdout   # trust the AI judge only after it qualifies
aiquality review   --team aeroassist                 # what a person should look at, and why
aiquality list-checks && aiquality list-attacks && aiquality list-judges
```

- **One contract** for every agent: a Python function, an HTTP endpoint, or answers recorded
  from a live agent, so CI needs no API key. Every run record says `live` or `recorded`.
- **Checks are plugins** (`@register_check`), each scored as a pass rate against a threshold;
  a company-wide floor that teams can tighten, never loosen.
- **Honest results:** cases a check can't judge are `NOT_APPLICABLE`, failed calls are `ERROR`,
  and neither is ever counted as a pass. A broken setup exits with code 2, never as a quality failure.
- **Secrets stay out of configs:** they're read from environment variables named in the config.
- **A judge for meaning, trusted per version:** an AI judge grades answers against the team's policy,
  but it may block a release only after this exact version qualifies against people's labels;
  until then it is advisory and feeds a **human review queue** of disagreements and doubts.
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
    JDG["Judges - register_judge<br/>policy_answer · phrase · validation"]
    MDL["ChatModel<br/>provider-neutral"]
    GATE["ReleaseGate<br/>PASS or FAIL<br/>+ advisory findings"]
    RR["RunRecord - JSONL<br/>personal data redacted"]
    MON["Monitoring<br/>tracing · drift"]
  end
  subgraph OUT["Outputs"]
    EXIT["Exit code<br/>CI blocks or passes"]
    REP["Reports - register_reporter<br/>console · HTML · JUnit XML · GitHub summary"]
    HRQ["Human review queue<br/>aiquality review"]
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
  class MON,GV,OTEL later
```

Solid boxes are in the package today; dashed boxes are scripts in [`demos/`](demos/) moving into it,
or planned. Details: [`docs/architecture.md`](docs/architecture.md) ·
onboarding: [`docs/onboarding.md`](docs/onboarding.md) · runnable examples: [`examples/`](examples/).

### Testing AeroAssist with it: results so far

Four runs on a policy-answering airline support agent, each one changing what we test next. The full
story (what we ran, found, changed and learned, with the evidence) is in
**[`docs/quality-log.md`](docs/quality-log.md)**, which also lists every open problem.

- **An average hid a critical failure.** 89% against an 85% bar would have passed while three
  high-priority cases failed; a priority bar now fails the gate for the right reason.
- **One quality loop, proven on unseen cases.** Diagnosing by layer showed two errors were retrieval
  misses and one was a gap in the policy. General fixes, then held-out cases written after the fix:
  no case newly failing, all held-out cases passed.
- **A sentence, not the model, was wrong.** "Allowed up to 4 hours before departure" was read two ways
  by the agent and by a person; rewording the policy fixed the case the prompt rules hadn't.
- **The phrase checks pass, and they are not enough.** An advisory AI judge found real errors the
  phrase checks passed: a passenger flying tomorrow told web check-in is closed, and changes refused
  at exactly 4 and 48 hours. So the AeroAssist gate stays non-blocking in CI until they're fixed.

---

## What's inside

| Area | File | The quality question it answers |
|---|---|---|
| **Platform** | `aiquality/`, `teams/`, `examples/`, `tests/`, `docs/` | *Can another team use this without writing test code?* Agent adapters, team configs, golden sets from JSON/CSV/Excel, pluggable checks, a company floor, run records and a command line. See the section above. |
| **Quality log** | `docs/quality-log.md` | *What did testing find, what changed, and what is still open?* Every run in order, the open problems, and the lessons that carry over to other agents. |
| **Golden dataset** | `teams/aeroassist/golden_dataset.json` | *What is the human-verified source of truth?* 40 labelled cases (happy / edge / adversarial / out-of-scope, 4 of them held-out), versioned with a changelog, plus a schema validator (`demos/loader_cell.py`). |
| **RAG evaluation** | `demos/rag_eval.py` | *Is the agent accurate and grounded?* Scores a policy-RAG with **RAGAS** — context precision/recall (retrieval) and faithfulness/answer-relevancy (generation), judged by Claude, embedded locally (no OpenAI). |
| **Red-teaming** | `demos/red_team.py`, `demos/red_team_v2.py` | *Can I break it?* OWASP-LLM-mapped attacks — prompt injection (direct & indirect), jailbreak, data-leak, excessive agency — plus strengthened vectors (obfuscation, multi-turn, poisoned knowledge base). |
| **The fix** | `demos/guardrail_fix.py` | *How do I close a breach?* A deterministic **policy-of-record at the execution gate** — money decisions live in code, not in the model. |
| **Agentic testing** | `demos/aeroassist_agent.py`, `demos/trajectory_eval.py`, `demos/consistency_check.py` | *Is the agent's whole journey right, not just its answer?* A tool-using agent that emits a **trajectory**, graded on tool choice, arguments, termination and **multi-intent completeness** — run N times to measure a reliability rate (a probabilistic agent isn't certified by a single pass). |
| **Completeness fix** | `demos/completeness_guardrail.py` | *How do I stop a silently dropped intent?* A code-owned **intent checklist** that re-asks for any missed request. Before/after: fully-complete rate `80% → 100%`. |
| **Eval harness / CI gate** | `demos/eval_harness.py`, `.github/workflows/eval-gate.yml` | *How do I stop a regression shipping?* A metric **registry** with per-metric thresholds + direction and a build-failing **exit code** — evals become a **gate**, not a report. Key-free **mock judge** runs on every PR (deterministic, no API key); the **live judge** runs on demand, and may only block a release once it has qualified against human labels (otherwise it's advisory). Demo: healthy outputs PASS (exit 0), a seeded regression FAILS (exit 1). |
| **Model layer** | `aiquality/models`, `demos/llm.py` | *Can I switch models without touching every file?* One place for model clients: provider and model are settings (`LLM_PROVIDER`, `AGENT_MODEL`, `JUDGE_MODEL`); the judge uses a different, stronger model than the agent, so nothing grades its own work. |
| **Judge validation** | `demos/answer_judge.py`, `demos/build_label_set.py`, `demos/judge_validation.py`; labels and results in `teams/aeroassist/` | *Can I trust the AI judge that gates my releases?* Thirty answers labelled blind by a person, split into a tuning half and a held-back half; two numbers against the human labels — **catches real failures** and **leaves good answers alone**; per-category breakdown; results saved per judge version. A judge that hasn't qualified runs in **advisory mode**. |
| **Tests for the test tools** | `tests/` | *Do the evaluation tools themselves work?* Key-free tests (fake judges, local servers, no network) run on every PR. |
| **Observability** | `demos/observability/tracing.py`, `demos/observability/monitor.py`, `demos/observability/pii_guardrail.py` | *Is it still safe in production?* A structured per-run **trace** (evidence log), a **dashboard** (breach/refusal rate, latency, cost), a baseline-vs-recent **drift alert**, and a **triage→fix** loop. Before/after: PII breach-rate `1.7% → 0%` (fake PII only). |

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
pip install -e ".[dev]" -r demos/requirements.txt
cp .env.example .env          # add your ANTHROPIC_API_KEY (never commit .env)

python demos/rag_eval.py            # evaluate the RAG with RAGAS
python demos/red_team.py            # baseline red-team (OWASP-mapped)
python demos/red_team_v2.py         # strengthened attacks (finds the real breach)
python demos/guardrail_fix.py       # the fix: breach closed, legit refunds still work

python demos/trajectory_eval.py     # grade the agent's trajectory (tool/args/termination/completeness)
python demos/consistency_check.py   # N-run completeness rate (catches silent multi-intent drops)
python demos/completeness_guardrail.py  # the completeness fix: before/after rate

python demos/eval_harness.py            # CI GATE: healthy outputs -> PASS (exit 0)
python demos/eval_harness.py regressed  # CI GATE: seeded regression -> FAIL (exit 1)

python demos/build_label_set.py                                  # 15 agent + 15 seeded answers to label
python demos/judge_validation.py --judge llm --split tune        # improve the judge on the tuning half
python demos/judge_validation.py --judge llm --split holdout     # measure once; exit 0 = qualified to gate
python -m pytest -q                                              # key-free tests for the tools themselves

aiquality record   --team aeroassist     # record the live agent's golden and attack answers (needs the key + the aeroassist extra)
aiquality evaluate --team aeroassist     # replay them: key-free and repeatable
aiquality gate     --team aeroassist     # the release gate on the recorded answers
```

In Colab, run `build_label_set.main()` and `judge_validation.main()` inside the notebook (not
with `!python`) so the Colab secret is available.

Run the scripts from the repository root; [`demos/README.md`](demos/README.md) says what each one
shows. The API key is read from the environment (`ANTHROPIC_API_KEY`) — it is never hard-coded,
and `.env` is gitignored. Data is privacy-safe synthetic only (no real PII).

---

## Roadmap (QA-of-AI stack, growing)

- [x] **Eval harness (done)** — run the full golden set in CI with score thresholds that *fail the build* (an eval you run by hand is a report; wired into CI it's a gate), with judge-call retries + pinned, containerized deps.
- [ ] **Runtime guardrails gateway** — the four guardrail layers enforced live on every request/response, not just at test time.
- [x] **Observability loop (done)** — trace every run; track hallucination-rate, guardrail-breach-rate, cost, latency; detect drift.
- [x] **Judge validation (done, round 1)** — human labels, tuning and held-back halves, two numbers, advisory mode until qualified.
- [ ] **Judge validation, round 2** — a labelling guide with quiet-failure examples, a second labeller, narrower single-purpose judges, and a fresh held-back set with the bars set beforehand.
- [ ] **One model layer for every judge** — move the RAGAS, red-team and completeness judges onto the package's model layer (`aiquality/models`).
- [ ] **Clearer policy boundaries** — P5's cut-off is reworded (done); the agent still refuses at exactly 4 and exactly 48 hours (GD18, GD30), so state every boundary as inclusive and test each one.
- [x] **Platform core (done)** — `aiquality` package: one agent contract, three adapters, team configs in YAML or JSON, golden sets from JSON/CSV/Excel, pluggable checks, a company floor, run records, a command line.
- [x] **Release gate per team and client (done)** — attack tests as plugins, accepted findings with expiry, exit codes 0/1/2, HTML / JUnit XML / GitHub summary reports.
- [x] **Judges in the platform (done)** — judges registry, validation and status per version, an advisory-until-qualified judge check, recorded verdicts, a human review queue.
- [ ] **A second team and monitoring in the platform** — a second (fictional) team onboarded with configuration only, a reusable CI workflow, monitoring moved into the package.
- [ ] **Gate view and tracing export** — a static gate dashboard and OpenTelemetry export to an open-source tracing tool.
- [x] **Quality loop on AeroAssist (done)** — retrieval checked on its own, run comparison case by case, agent v2 with general rules, held-out cases, no regressions.
- [ ] **Parallel runs** — worker limit, rate-limit retries and a per-run budget cap.

---

*Part of a two-repo body of work on AI quality: this repo (**QA of AI**) and
[`aeroassist-qa-agent`](https://github.com/rahulsharma-qe/aeroassist-qa-agent) (**AI for QA**).*
