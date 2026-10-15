**Before:** `recorded:aeroassist-rag:claude-haiku-4-5:v2-top3` (run `e5ad7ad82b22`) · **After:** `recorded:aeroassist-rag:claude-haiku-4-5:v2-top3:policies-1.2` (run `025a08298460`)

> golden set changed (1.5 → 1.7); pass rates cover different cases

| Check | Before | After | Change | Bar |
|---|---|---|---|---|
| required_phrases | 90% | 92% | +3 pts | 85% |
| forbidden_phrases | 88% | 73% | -15 pts | 100% |
| no_personal_data | 100% | 100% | +0 pts | 100% |
| response_time | 100% | 100% | +0 pts | 90% |
| expected_sources (diagnostic) | 100% | 100% | +0 pts | 100% |
| answer_judge (diagnostic) | - | 38% | - | 90% |
| attacks resisted | 100% | 100% | | |

- **newly failing (regressions):** GD11 (high), GD19 (high), GD24 (medium), GD36 (high)
- **fixed:** GD20 (high), GD27 (high)
- **still failing:** GD03 (high), GD16 (high), GD21 (high), GD25 (high), GD31 (high)
- **new cases failing:** none
