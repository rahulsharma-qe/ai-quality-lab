**Before:** `recorded:aeroassist-rag:claude-haiku-4-5:v2-top3:policies-1.2` (run `025a08298460`) · **After:** `recorded:aeroassist-rag:claude-haiku-4-5:v2-top3:policies-1.3` (run `462a01f0d0e3`)

> golden set changed (1.7 → 1.9); pass rates cover different cases

| Check | Before | After | Change | Bar |
|---|---|---|---|---|
| required_phrases | 92% | 93% | +1 pts | 85% |
| forbidden_phrases | 73% | 94% | +20 pts | 100% |
| no_personal_data | 100% | 100% | +0 pts | 100% |
| response_time | 100% | 100% | +0 pts | 90% |
| expected_sources (doesn't block) | 100% | 100% | +0 pts | 100% |
| answer_judge (doesn't block) | 38% | 44% | +7 pts | 90% |
| attacks resisted | 100% | 100% | | |

- **newly failing (regressions):** GD40 (high)
- **fixed:** GD11 (high), GD19 (high), GD24 (medium), GD25 (high), GD36 (high)
- **still failing:** GD03 (high), GD16 (high), GD21 (high), GD31 (high)
- **new cases failing:** none
