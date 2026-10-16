# demos — the studies that came before the platform

Each script here proved one testing technique on AeroAssist, the airline support agent under test.
The techniques that held up were then built into the `aiquality` package; these scripts stay as the
evidence and as small, readable examples of each idea.

AeroAssist itself (its policies, golden set, judge labels and agent code) lives with its team in
[`../teams/aeroassist/`](../teams/aeroassist/). `paths.py` is the one place these scripts look it up.

## What each study shows

| Study | Scripts | What it shows |
|---|---|---|
| Retrieval-augmented answers | `rag_eval.py` | Scores the agent with RAGAS: did it fetch the right policy (context precision and recall), and does the answer stay true to it (faithfulness, answer relevancy)? |
| Attack testing | `red_team.py`, `red_team_v2.py` | Attacks mapped to the OWASP list of risks for language-model apps. The first round found nothing, which was a sign the attacks were weak; the stronger round broke the agent with one changed number in a retrieved policy. |
| The fix for that breach | `guardrail_fix.py` | The money decision moves out of the model into code: the same attack is now resisted, and a valid refund still goes through. |
| An agent that uses tools | `aeroassist_agent.py`, `trajectory_eval.py`, `consistency_check.py` | Grades the agent's whole journey (which tool, which arguments, when it stopped, whether every request was handled), and runs it several times, because one pass proves little for an agent whose answers vary. |
| The fix for dropped requests | `completeness_guardrail.py` | A checklist in code that asks again for any request the agent missed. Fully complete answers went from 80% to 100%. |
| Release gate, first version | `eval_harness.py` | Pass rates against bars, and an exit code that fails the build. Healthy answers pass; a seeded regression fails. |
| Can the AI judge be trusted? | `answer_judge.py`, `build_label_set.py`, `judge_validation.py` | Thirty answers labelled by a person, split into a half for tuning and a held-back half measured once. Two numbers decide whether the judge may block a release: how many real failures it catches, and how many good answers it leaves alone. |
| Watching it in production | `observability/tracing.py`, `observability/monitor.py`, `observability/pii_guardrail.py` | A trace of every run, a dashboard (breaches, refusals, response time, cost), a drift alert, and a guardrail that took the personal-data leak rate from 1.7% to 0% (invented data only). |
| Shared helpers | `llm.py`, `loader_cell.py`, `paths.py` | The model settings (now a thin wrapper over the package), the golden-set schema check, and where AeroAssist's files are. |

## Run them

From the repository root:

```bash
pip install -e ".[dev]" -r demos/requirements.txt
python demos/eval_harness.py                     # no API key needed
python demos/loader_cell.py                      # golden-set schema check, no API key
python demos/rag_eval.py                         # needs ANTHROPIC_API_KEY
```

The scripts that call a model read `ANTHROPIC_API_KEY` from the environment.
