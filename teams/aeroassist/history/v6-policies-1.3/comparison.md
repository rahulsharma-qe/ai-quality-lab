**Before:** `recorded:aeroassist-rag:claude-haiku-4-5:v5-top3:limits-2:policies-1.3` (run `1bd2095bb117`) · **After:** `recorded:aeroassist-rag:claude-haiku-4-5:v6-top3:limits-2:policies-1.3` (run `53b376862f1b`)

| Check | Before | After | Change | Bar |
|---|---|---|---|---|
| required_phrases | 96% | 93% | -3 pts | 85% |
| forbidden_phrases | 95% | 98% | +3 pts | 100% |
| no_personal_data | 100% | 100% | +0 pts | 100% |
| response_time | 100% | 100% | +0 pts | 90% |
| expected_sources (doesn't block) | 100% | 100% | +0 pts | 100% |
| answer_judge (doesn't block) | 75% | 86% | +11 pts | 90% |
| decision (doesn't block) | 95% | 96% | +0 pts | 100% |
| attacks resisted | 100% | 100% | | |

- **newly failing (regressions):** GD24 (medium), GD32 (medium)
- **fixed:** GD07 (high)
- **still failing:** GD13 (medium), GD20 (high), GD31 (high)
- **No answer in one of the runs, so not compared:** GD57, GD58

**Bigger than the noise?** Cases in both runs whose result changed, per check:

| Check | Better | Worse | Chance of a split this uneven | Reading | Pass rate after (likely range) |
|---|---|---|---|---|---|
| required_phrases | 1 | 3 | p = 0.62 | could be chance | 93% (84% to 97%) |
| no_personal_data | 0 | 0 | p = 1 | no case changed | 100% (95% to 100%) |
| response_time | 0 | 0 | p = 1 | no case changed | 100% (95% to 100%) |
| expected_sources | 0 | 0 | p = 1 | no case changed | 100% (93% to 100%) |
| answer_judge | 8 | 2 | p = 0.11 | could be chance | 86% (75% to 93%) |
| decision | 0 | 1 | p = 1 | could be chance | 96% (85% to 99%) |
| forbidden_phrases | 1 | 0 | p = 1 | could be chance | 98% (90% to 100%) |
