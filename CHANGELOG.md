# Changelog

Changes to the `aiquality` package, newest first. What each feature does, and why, is in the
[README](README.md); what testing found is in the [quality log](docs/quality-log.md).
`aiquality --version` prints the installed version.

## 0.2.0 — 2026-10-28

The gate and the judge are stricter: some things that passed in 0.1.0 now fail or stop with a setup
error. Read **Breaking** before upgrading.

### Breaking

- **A blocking check with no applicable case fails the gate**, not only a mandatory one: there is no
  evidence it passes. Make the check non-blocking, or give it a case.
- **A golden-set column that is almost the name of one that drives a check** (`must_includ`) stops the
  golden set from loading, naming the right one; before, it was kept as a note and the check ran on
  nothing. Other extra columns (`notes`, `sub_category`, `expected_behavior`) are still kept as notes.
- **Tables count an ERROR as a failure**, as the gate always did, so a pass rate in a report can be lower.
- **A case missing from the recorded answers is a setup error (exit 2)**: record again.
- **A judge qualifies only** on the held-back half, with at least 5 PASS and 5 FAIL labels, in a run
  where every judge call worked. `--split all` no longer qualifies.
- **The judge's version includes the policies it grades against**, so a live model judge is a new
  version and starts unvalidated; changed held-back labels make a measured judge unvalidated too.

### Added

- `aiquality evidence`: a run held against the laws and standards a team chose (EU AI Act, NIST AI
  RMF, ISO/IEC 42001, OWASP LLM Top 10, DPDP, GDPR, PCI DSS, HIPAA, HITRUST, RBI FREE-AI). Evidence,
  not a compliance decision, and it says so first.
- Checks: `ai_disclosure` (tells people it's an AI, never claims to be one) and
  `counterfactual_fairness` (the same question for a different person gets the same decision).
- `category_bars`: a bar per test type, beside the bar per priority.
- Judge validation numbers each held-back measurement of a version and flags a weak category. A run
  that doesn't count (a judge call failed) exits 2. Recorded verdicts from a judge other than the one the
  config describes don't carry its status.

### Fixed

- `compare` no longer counts a case with no answer in one run as fixed or broken, or in its noise test.
- The decision reader reads "absolutely / certainly / of course not" as no.
- Priority and category bars match in any case (`High` meets a `high` bar).
- A secret in the agent's URL is refused, and messages print the URL masked.
- Setup problems (a team folder that exists, no model client, no API key, a wrong folder) are one-line
  messages with exit 2, not tracebacks.
- Days are read as 30-11-2026 or 2026-11-30 and shown as 30-11-2026 in reports, the dashboard and the
  evidence report (run records keep 2026-11-30, so they sort).

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
