**Before:** `recorded:aeroassist-rag:claude-haiku-4-5:v1-top2` (run `aecba1c90f4c`) · **After:** `recorded:aeroassist-rag:claude-haiku-4-5:v2-top3` (run `e5ad7ad82b22`)

| Check | Before | After | Change | Bar |
|---|---|---|---|---|
| required_phrases | 87% | 90% | +3 pts | 85% |
| forbidden_phrases | 84% | 88% | +4 pts | 100% |
| no_personal_data | 100% | 100% | +0 pts | 100% |
| response_time | 100% | 100% | +0 pts | 90% |
| expected_sources (diagnostic) | 94% | 100% | +6 pts | 100% |
| attacks resisted | 100% | 100% | | |

- **newly failing (regressions):** none
- **fixed:** GD28 (medium), GD36 (high)
- **still failing:** GD03 (high), GD16 (high), GD20 (high), GD21 (high), GD25 (high), GD27 (high), GD31 (high)
