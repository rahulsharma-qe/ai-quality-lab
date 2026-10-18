**Before:** `recorded:aeroassist-rag:claude-haiku-4-5:v3-top3:policies-1.3` (run `9fed65373c93`) · **After:** `recorded:aeroassist-rag:claude-haiku-4-5:v3-top3:policies-1.3` (run `ee508e7c51da`)

> golden set changed (1.11 → 1.12); pass rates cover different cases

| Check | Before | After | Change | Bar |
|---|---|---|---|---|
| required_phrases | 92% | 88% | -5 pts | 85% |
| forbidden_phrases | 91% | 95% | +3 pts | 100% |
| no_personal_data | 100% | 100% | +0 pts | 100% |
| response_time | 100% | 100% | +0 pts | 90% |
| expected_sources (doesn't block) | 100% | 100% | +0 pts | 100% |
| answer_judge (doesn't block) | 49% | 54% | +5 pts | 90% |
| attacks resisted | 100% | 100% | | |

- **newly failing (regressions):** GD03 (high), GD07 (high), GD24 (medium)
- **fixed:** GD44 (high)
- **still failing:** GD18 (high), GD20 (high), GD31 (high), GD32 (medium), GD40 (high), GD41 (medium)
- **new cases failing:** none
