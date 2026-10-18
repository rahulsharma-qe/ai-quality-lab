# AeroAssist run history

Saved runs, so any change to the agent can be compared with what came before. Each folder holds
its own answers, so a run can be replayed and compared after the default agent has moved on.
`../recorded_answers.jsonl` and `../judge_verdicts.jsonl`, the files CI replays, are a copy of the
current default agent's latest recording: `v5-policies-1.3/`.

| Folder | Agent and policies | Golden set | What it holds |
|---|---|---|---|
| `v1/` | v1 (first instructions, top 2 policies, earlier turns ignored), policies 1.1 | 1.5 | Answers and the gate's run record |
| `v2/` | v2 (general rules, top 3 policies, earlier turns used), policies 1.1 | 1.5 | Answers and the gate's run record |
| `comparison.md` | v1 against v2, case by case | | |
| `v2-policies-1.2/` | v2, policies 1.2 (the reworded 4-hour cut-off) | 1.7 | Answers, the judge's verdicts, the run record, the comparison with v2 and the review queue (Run 4) |
| `v2-policies-1.3/` | v2, policies 1.3 (P8: exactly 48 hours qualifies) | 1.9 | Answers, verdicts, run record, comparison with Run 4 (Run 5: the policy change on its own) |
| `v3-policies-1.3/` | v3 (rules for the kinds of error Run 4 found), policies 1.3 | 1.9 | Answers, verdicts, run record, comparison with v2 on the same policies, and `flip_check.jsonl` (Run 5) |
| `v3-policies-1.3-run6/` | v3 again, recorded in Run 6's session as its baseline | 1.11 | Answers, verdicts, run record, and the comparison with Run 5's v3: the same agent twice, so every difference is noise (Run 6) |
| `v4-policies-1.3/` | v4 (limits decided by the `check_policy_limits` tool), policies 1.3 | 1.11 | Answers with the tool calls the model made, verdicts, run record, comparison with v3 in the same session, and `repeat_check.jsonl` (Run 6) |
| `v3-policies-1.3-run7/` | v3 again, Run 7's baseline | 1.12 | Answers, verdicts, run record, and the comparison with Run 6's v3 (noise) |
| `v5-policies-1.3/` | v5 (the limits tool called on every message; limits rule on ranges), limits 2, policies 1.3 | 1.12 | Answers with tool calls, verdicts, run record, comparison with v3 in the same session, and `repeat_check.jsonl` (Run 7) |

Runs that are compared were recorded in one session with the same settings (temperature 0), so a
difference between them comes from the change or from the model's own variation, not from a
different setup.

`flip_check.jsonl` measures that variation. Every case whose result changed between v2 and v3,
and every held-out case, was asked 3 more times: 24 cases, 72 rows, each with a new answer, the
judge's verdict on it and whether it passed its phrase checks (golden set 1.9). Because each
repeat has a new answer and a new verdict, it measures the agent and the judge together. The
judge's verdict changed at least once for 13 of the 24 cases. What that means for the results is
in `docs/quality-log.md`, Run 5.

`repeat_check.jsonl` (Run 6) is the same check for v4, with the tool calls of each answer: GD13, GD18,
GD40 and GD41 always, every case whose result changed between v3 and v4, and the held-out cases
GD46 to GD51. 23 cases, 69 rows. Run 7's `repeat_check.jsonl` for v5 counts a case as changed when any
check changes, not only the judge, and marks answers that ask the passenger for a figure: 25 cases,
75 rows.

Compare again, or against a later run:

```bash
aiquality compare teams/aeroassist/history/v1 teams/aeroassist/history/v2
aiquality compare teams/aeroassist/history/v2-policies-1.3 teams/aeroassist/history/v3-policies-1.3
aiquality compare teams/aeroassist/history/v3-policies-1.3-run6 teams/aeroassist/history/v4-policies-1.3
aiquality compare teams/aeroassist/history/v3-policies-1.3-run7 teams/aeroassist/history/v5-policies-1.3
aiquality compare teams/aeroassist/history/v5-policies-1.3 aiquality-runs --fail-on-new-failures
```
