# Changelog

Changes to the `aiquality` package, newest first. What each feature does, and why, is in the
[README](README.md); what testing found is in the [quality log](docs/quality-log.md).
`aiquality --version` prints the installed version.

## 0.1.0 — 2026-10-19

The first release.

- **Commands:** `evaluate`, `gate`, `attack`, `record`, `compare`, `repeat`, `validate-judge`,
  `review`, `lint`, `new-team`, `ci-summary`, `dashboard`, `export-traces`, `list-checks`,
  `list-attacks`, `list-judges`, and `--version`. Exit codes: 0 done or gate passed, 1 gate failed,
  2 setup problem.
- **Ways to reach an agent:** `python_function`, `http_endpoint`, `recorded_responses`.
- **Checks:** `required_phrases`, `forbidden_phrases`, `no_personal_data`, `response_time`,
  `expected_sources`, `decision`, `answer_judge`.
- **Attack families:** `direct_injection`, `multi_turn_pressure`, `obfuscation`,
  `personal_data_request`, `role_play`.
- **Judges:** `phrase` (no model, for key-free runs) and `policy_answer` (a model judge, advisory
  until it qualifies against people's labels).
- **Reports:** `console`, `html`, `junit_xml`, `github_summary`, `review_queue`; plus the dashboard
  page and OpenTelemetry traces (OTLP JSON).
- **Inputs:** team config in YAML or JSON; golden sets in JSON, CSV or Excel (Excel needs the `excel` extra;
  only JSON carries a version).
- **Run record:** schema version 1, one JSON line per run.
- **Python:** 3.11 and 3.12, tested in CI.
