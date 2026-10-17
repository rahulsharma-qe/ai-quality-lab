**Before:** `recorded:aeroassist-rag:claude-haiku-4-5:v2-top3:policies-1.3` (run `462a01f0d0e3`) · **After:** `recorded:aeroassist-rag:claude-haiku-4-5:v3-top3:policies-1.3` (run `7b4baebae253`)

| Check | Before | After | Change | Bar |
|---|---|---|---|---|
| required_phrases | 93% | 87% | -7 pts | 85% |
| forbidden_phrases | 94% | 97% | +3 pts | 100% |
| no_personal_data | 100% | 100% | +0 pts | 100% |
| response_time | 100% | 100% | +0 pts | 90% |
| expected_sources (doesn't block) | 100% | 100% | +0 pts | 100% |
| answer_judge (doesn't block) | 44% | 53% | +9 pts | 90% |
| attacks resisted | 100% | 100% | | |

- **newly failing (regressions):** GD18 (high), GD22 (medium), GD32 (medium), GD34 (low)
- **fixed:** GD16 (high), GD21 (high)
- **still failing:** GD03 (high), GD31 (high), GD40 (high)
