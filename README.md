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

## What's inside

| Area | File | The quality question it answers |
|---|---|---|
| **Golden dataset** | `golden_dataset.json` | *What is the human-verified source of truth?* 36 labelled cases (happy / edge / adversarial / out-of-scope), with a schema validator (`loader_cell.py`). |
| **RAG evaluation** | `rag_eval.py` | *Is the agent accurate and grounded?* Scores a policy-RAG with **RAGAS** — context precision/recall (retrieval) and faithfulness/answer-relevancy (generation), judged by Claude, embedded locally (no OpenAI). |
| **Red-teaming** | `red_team.py`, `red_team_v2.py` | *Can I break it?* OWASP-LLM-mapped attacks — prompt injection (direct & indirect), jailbreak, data-leak, excessive agency — plus strengthened vectors (obfuscation, multi-turn, poisoned knowledge base). |
| **The fix** | `guardrail_fix.py` | *How do I close a breach?* A deterministic **policy-of-record at the execution gate** — money decisions live in code, not in the model. |
| **Agentic testing** | `aeroassist_agent.py`, `trajectory_eval.py`, `consistency_check.py` | *Is the agent's whole journey right, not just its answer?* A tool-using agent that emits a **trajectory**, graded on tool choice, arguments, termination and **multi-intent completeness** — run N times to measure a reliability rate (a probabilistic agent isn't certified by a single pass). |
| **Completeness fix** | `completeness_guardrail.py` | *How do I stop a silently dropped intent?* A code-owned **intent checklist** that re-asks for any missed request. Before/after: fully-complete rate `80% → 100%`. |

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
```

Each file is self-contained and also runs cell-by-cell in a notebook. The API key is read
from the environment (`ANTHROPIC_API_KEY`) — it is never hard-coded, and `.env` is gitignored.
Data is privacy-safe synthetic only (no real PII).

---

## Roadmap (QA-of-AI stack, growing)

- [ ] **Eval harness** — run the full golden set in CI with score thresholds that *fail the build* (an eval you run by hand is a report; wired into CI it's a gate), with judge-call retries + pinned, containerized deps.
- [ ] **Runtime guardrails gateway** — the four guardrail layers enforced live on every request/response, not just at test time.
- [ ] **Observability loop** — trace every run; track hallucination-rate, guardrail-breach-rate, cost, latency; detect drift.

---

*Part of a two-repo body of work on AI quality: this repo (**QA of AI**) and
[`aeroassist-qa-agent`](https://github.com/rahulsharma-qe/aeroassist-qa-agent) (**AI for QA**).*
