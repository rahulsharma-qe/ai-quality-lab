# AeroAssist run history

Saved runs, so any change to the agent can be compared with what came before.

| Folder | What it holds |
|---|---|
| `v1/` | The original agent (first instructions, top 2 policies, earlier turns ignored): its recorded answers and the gate's run record |
| `v2/` | The fixed agent (general rules, top 3 policies, earlier turns used): the gate's run record. Its answers are `../recorded_answers.jsonl`, the file CI replays |
| `comparison.md` | v1 against v2, case by case |
| `v2-policies-1.2/` | v2 answering from policies 1.2 (the reworded 4-hour cut-off), with the judge's verdicts: the gate's run record, the comparison with v2, and the review queue. Its answers and verdicts are `../recorded_answers.jsonl` and `../judge_verdicts.jsonl` |

Both versions were recorded in one session with the same settings (temperature 0, golden set 1.5,
39 golden + 16 attack cases each), so the differences come from the change, not from chance.

Compare again, or against a later run:

```bash
aiquality compare teams/aeroassist/history/v1 teams/aeroassist/history/v2
aiquality compare teams/aeroassist/history/v2-policies-1.2 aiquality-runs --fail-on-new-failures
```
