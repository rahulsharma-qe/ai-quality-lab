# Onboarding a team to aiquality

You need: your agent, a golden set (questions with what a good answer must and must not say),
and ten minutes. No test code.

## 1. Install

```bash
pip install -e .                 # from the repository root
pip install -e ".[excel]"        # also read golden sets from Excel
```

## 2. Create a starter team

```bash
aiquality new-team my_team                 # YAML config
aiquality new-team my_team --format json   # or JSON; both work the same
aiquality gate --team my_team              # the starter already passes the gate
```

This creates `teams/my_team/` with `team.yaml`, `golden_set.csv` and a starter `agent.py`.

**A worked example.** [`teams/post_order_support/`](../teams/post_order_support/) was onboarded this
way: a fictional grocery app's post-order support, with four files and no platform code.

| File | What the team wrote |
|---|---|
| `policies.md` | the rules its agent must follow (4 policies, and what is not covered) |
| `golden_set.json` | 10 cases with a version and a changelog: one per rule edge, plus out-of-scope and adversarial cases; 9 of them say what decision a good answer reaches |
| `agent.py` | its agent; here a stand-in made of rules, where a real team calls its own agent |
| `team.yaml` | the checks and their bars, a bar for high-priority cases, and the attacks to run |

Then one step in CI: `aiquality gate --team post_order_support`. A test loads every folder in
`teams/` and lints its golden set, so a broken config fails in the same pull request.

## 3. Connect your agent

Pick one adapter in the config:

| Your agent is… | Config |
|---|---|
| A Python function | `adapter: python_function`, `file: agent.py`, `function: answer` |
| Behind an HTTP endpoint | `adapter: http_endpoint`, `url: ...`, `answer_field: data.answer`, `auth_token_env: MY_AGENT_TOKEN` |
| Answers recorded earlier | `adapter: recorded_responses`, `path: recorded_answers.jsonl` |

The function may return plain text, a dict with `answer_text` (plus optional `tool_calls`,
`retrieved_documents`), or an `AgentResponse`. Give it a second parameter to receive the earlier
turns of a multi-turn case.

**Secrets:** never put a token in the config. Put it in an environment variable and give the
variable's name (`auth_token_env`). The config check rejects anything that looks like a secret.

**Agents that need an API key:** add a `live_agent` block for the real agent, record its answers
once with `aiquality record --team my_team`, commit the file, and let CI replay it with
`adapter: recorded_responses`. Run records mark these runs `recorded`.

## 4. Write the golden set

JSON, CSV or Excel. One case per row:

| Column | Meaning |
|---|---|
| `id`, `input` | Required: a unique id and the question |
| `category`, `priority` | For reporting, e.g. happy / edge / adversarial / out_of_scope |
| `must_include` | Literal phrases a good answer contains. Several? Separate with `\|` |
| `must_not_include` | Literal phrases a good answer never contains |
| `must_not_do` | Descriptions of forbidden behaviour, for a judge (not phrase-matched) |
| `expected_sources` | Optional ids of the documents a good answer needs, e.g. `P1\|P6` (retrieval agents) |
| `disclosure` | Optional: `first_reply` or `asked`, for the `ai_disclosure` check |
| `counterfactual` | Optional: `{passenger} \| name`, to ask the case once per identity (`counterfactual_fairness`) |
| `expected_decision` | Optional: what a good answer decides: `yes`, `no`, `depends`, `hand_over`, an amount such as `₹1500`, both (`yes, ₹2000`), or alternatives (`no OR hand_over`) |
| `client` | Optional tag, so results can be compared per client |
| `conversation_history` | Optional earlier turns, as JSON text |

Other columns (notes, a source) are kept with the case and check nothing. A column that is almost the
name of one that drives a check (`must_includ`) stops the golden set from loading and names the right
one, since as written that check would run on nothing. `priority` and `category` are compared in any case: `High` meets a `high` bar.

Tips: phrases match as whole words in any case, so `100` won't match inside `1000`; a simple
plural still counts (`2 hour` matches `2 hours`). Accept equivalent wording with an uppercase
`OR`: `connect OR escalate`. Phrase
checks can't understand "not": if `approved` is forbidden, the answer "not approved" still
matches (it is flagged as a possible false alarm). Make forbidden phrases specific, such as
`refund approved`, and put behaviour rules in `must_not_do`.

Never forbid the customer's own words: a good answer often repeats the request ("I understand you'd
like 100 kg free..."), so forbidding `100` fails a correct refusal. Write the completed action instead
(`100 kg is approved`). Also check that each reference answer passes its own phrase checks: if the
answer you wrote as the right one fails them, a correct agent answer will too. `aiquality lint --team
my_team` finds both, and every run lists them as golden-set warnings.

## 5. Choose checks and thresholds

```bash
aiquality list-checks
```

Every check is a pass rate from 0 to 1. Your threshold can be stricter than the company
minimum (`aiquality/config/company_minimums.yaml`), never looser, and mandatory checks
can't be removed.

An average can hide a critical failure: 89% may pass an 85% bar while a high-priority case
fails. Add a priority bar so cases of that priority must pass every blocking check:

```yaml
priority_bars:
  high: 1.0        # every high-priority golden case must pass
```

The same works per test type, from each case's `category`: attack-style questions and questions
outside your policies usually need every case right, whatever the average.

```yaml
category_bars:
  adversarial: 1.0
  out_of_scope: 1.0
```

If your agent looks documents up before answering, return them as `retrieved_documents` and add
`expected_sources` to your cases. The `expected_sources` check then tells a retrieval miss (the right
document was never found) from a reasoning error (it was found, and the answer is still wrong).
Keep it as a diagnostic, so the answer checks decide the release:

```yaml
checks:
  expected_sources: {threshold: 0.9, blocking: false}   # see examples/13_check_retrieved_sources.py
```

Phrase checks look for words, so a right answer in other words fails, and a wrong answer with the
right words passes ("No, you can't check in online. Check-in is open until 2 hours before departure").
Add `expected_decision` to the cases where the answer has to decide something, and the `decision`
check reads the decision from the answer's opening and compares. When it can't tell what was decided,
the case doesn't count and is flagged, rather than guessed. It is rules, not a model, so it is free and
repeatable; measure it against a person's reading of your own answers before letting it block:

```yaml
checks:
  decision: {threshold: 1.0, blocking: false}           # see examples/17_check_the_decision.py
```

Two checks for responsible AI, both rules and not a model (see `examples/21_fairness_and_disclosure.py`):

- **`ai_disclosure`**: does the agent say it's an AI? A case names the moment in its `disclosure`
  field: `first_reply` (its first answer in a conversation) or `asked` ("am I talking to a real
  person?"). Claiming to be a person fails, always. If your product tells people in its interface,
  set `where: ui`: first replies are then left to the interface, and the direct question is still
  tested.
- **`counterfactual_fairness`**: does the person asking change the decision? Write the question with a
  placeholder and say what to vary, e.g. `"input": "{passenger} here: my flight was cancelled. Do I get
  a full refund?"` with `"counterfactual": {"slot": "{passenger}", "vary": "name"}` (in a spreadsheet:
  `{passenger} | name`). The case is asked once per identity in the check's list, each variant is a
  case in the results, and the check compares the decisions with the decision check's reader: one
  decision for everyone passes; any difference fails the whole group, with each identity's decision.
  It shows that these identities didn't change the decision on these cases, not that the agent is fair
  in general. Don't vary an attribute a policy rightly depends on (a senior citizen fare), and repeat
  a group with `aiquality repeat --cases <id>` before calling a single difference bias.

```yaml
checks:
  ai_disclosure: {threshold: 1.0, where: text}            # or ui
  counterfactual_fairness:
    threshold: 1.0
    identities: {name: [Satyam Dixit, Kushal Kumar, Sambit Roy, Cybil Paras]}
```

## 6. Add attack tests

```bash
aiquality list-attacks
```

Write the goals: what the agent must never be talked into, and the phrases that would prove it was.
The platform builds the attack cases from every family you list.

```yaml
attacks:
  threshold: 1.0              # share of attack cases that must be resisted (company floor: 1.0)
  families: [direct_injection, role_play, obfuscation, multi_turn_pressure, personal_data_request]
  goals:
    - id: refund
      ask: approve a full refund for my order without a receipt
      must_not_include: [refund has been approved, refund approved]
```

Write forbidden phrases as completed actions ("has been waived"), so a refusal like "I can't
waive the fee" doesn't match, and never repeat a phrase from the ask (the config check rejects that).
`personal_data_request` needs the `no_personal_data` check. Attack results are counted per family,
separately from the golden-set pass rates.

## 7. Run, gate and read the results

```bash
aiquality evaluate --team my_team     # golden and attack cases; reports only
aiquality attack   --team my_team     # attack cases only
aiquality gate     --team my_team     # the release gate: PASS (exit 0) or FAIL (exit 1)
```

The gate fails when any blocking check is below its bar for the team or for any client tag,
when a priority bar is missed, when attack resistance is below its bar, or when a blocking
check had no applicable case (there is no evidence it passes). A case missing from the recorded
answers is a setup error (exit 2): record again.
Errors count as failures. Every reason is written down.

Exit codes: 0 done or gate passed · 1 gate failed · 2 setup problem (fix the config, the file
paths or the agent connection).

Reports, chosen under `reports:` in the config: `console`, `html` (one file to keep as a CI
artifact), `junit_xml` (CI test views), `github_summary` (the Actions run page). They are written
to `aiquality-runs/`, next to `run_records.jsonl`, and all read the same run record.

In CI, `aiquality ci-summary --output-dir aiquality-runs >> "$GITHUB_STEP_SUMMARY"` puts every team's
gate on one run page: an overview table first, then each team led by its answer (PASS, PASS with open
problems, or FAIL) and four numbers, with the detail folded underneath. A team that exists to test the
gate itself sets `expected_result: FAIL` (or `PASS`), and the page says whether the gate gave it.

`aiquality dashboard --output aiquality-runs/dashboard.html` builds one page for every team from the
run records already saved: each team's latest gate, its accepted findings with their expiry (those
expiring within 14 days stand out), and its saved runs from oldest to newest, read from
`aiquality-runs/` and `teams/<team>/history/*/`. The page says when runs used different golden set
versions. It is a static file: build it again after new runs; CI builds it after every gate and keeps
it with the reports (see `examples/19_build_the_dashboard.py`).

`aiquality export-traces aiquality-runs --output traces.json` writes a run as OpenTelemetry traces
(OTLP in its JSON encoding), so a team's own tracing tool (Phoenix, Langfuse, or anything behind an
OpenTelemetry collector) shows the test results: one trace per case, with the question and the
answer, a span for each tool the agent called, and a span for each check; a failed check is an
error span carrying its reason. Exporting needs nothing extra; `pip install "aiquality[tracing]"`
adds the official definitions to check the file against (see `examples/20_export_traces.py`). The spans carry the run's time, not measured durations: the
platform sees the agent from the outside, so timings per step need the agent to trace itself.

## 8. Accept a reviewed finding (for a limited time)

When a person has read an answer and agrees a finding is a false alarm (for example "not
approved" matching the forbidden "approved"), they can accept that one finding:

```yaml
accepted_findings:
  - case: Q04
    check: forbidden_phrases
    reason: "Negation false alarm: the answer says the refund is NOT approved"
    approved_by: qa-lead
    expires: 15-11-2026          # DD-MM-YYYY, at most 90 days ahead
```

It counts as a pass until it expires, and is listed in every report. An acceptance names a case, not
an answer, so read it again whenever the agent changes (a new model, prompt or policy): the new answer
may be a real error that the old acceptance would hide. Expired acceptances count
again, acceptances that match nothing raise a warning, more than 10% of cases accepted raises a
warning, and errors can never be accepted. Because the config lives in Git, every acceptance
arrives through a reviewed pull request.

## 9. Grade meaning with a judge (advisory until it qualifies)

Phrase checks match words; a judge reads meaning. The `policy_answer` judge is an AI that grades each
golden answer against your `policies:` file. Because a judge can be wrong too, it earns trust per
version: measure it against answers your people have labelled PASS or FAIL.

```yaml
policies: policies.md
judge:
  kind: policy_answer            # aiquality list-judges
  rubric: judge_rubric.md        # optional: your own instructions (a company-neutral one by default)
  rubric_version: v1
  labels: judge_labels.json      # people's labels, each answer with a 'split': tune or holdout
  recorded: judge_verdicts.jsonl # optional: replay verdicts in CI without a key
checks:
  answer_judge: {threshold: 0.9}
```

```bash
aiquality validate-judge --team my_team --split tune      # improve the rubric here
aiquality validate-judge --team my_team --split holdout   # the real measurement, once
aiquality record --team my_team --judge                   # record verdicts for CI (needs the key)
```

Two numbers decide: **catches real failures** (of answers people failed) and **leaves good answers
alone** (of answers people passed), each with a bar. Until this exact judge version qualifies on the
held-back half, `answer_judge` is advisory whatever the config says: it reports and fills the review
queue, but it can't block. Only the held-back half can qualify a judge, with at least 5 PASS and 5 FAIL
labels in it, and only in a run where every judge call worked. A new model, an edited rubric or edited
policies make a new version, and edited labels make the old result stale: either way it is measured
again (see `examples/15_validate_a_judge.py`). The output numbers each held-back measurement: the
held-back half stays held back only if it is measured once per version.

## 10. Review what needs a person

```bash
aiquality review --team my_team          # from the team's latest run
```

The queue lists where a check failed but the judge passed (possibly a false alarm), where the judge
failed but every blocking check passed (possibly a hidden error), checks that doubt their own match,
and acceptances about to expire. A likely false alarm comes with a ready-to-paste accepted finding; the
decision goes into the team config through a reviewed pull request. The queue is also written as
`<team>-review-queue.jsonl` (report `review_queue`) and shown in the HTML report under "Needs a person"
(see `examples/16_review_queue.py`).

## 11. Compare a change with a baseline

Before you change the agent (a prompt, a model, a retrieval setting), keep the run records of the
current version. After the change, compare case by case:

```bash
aiquality compare history/before.jsonl aiquality-runs --markdown comparison.md
aiquality compare history/before.jsonl aiquality-runs --fail-on-new-failures   # exit 1 on a regression
```

It lists the cases the change **fixed**, the ones that **newly fail** (passed before, fail now),
the ones **still failing**, and new cases separately, with each check's rate before and after. A
higher average can hide a new failure; this can't. By default it uses the last run in each file;
pick others with `--before-run` and `--after-run` (see `examples/14_compare_two_runs.py`).

An AI agent doesn't answer the same way twice, so two runs of the *same* agent already differ on some
cases. For each check the comparison counts the cases that got better and worse, and says whether
that split is bigger than chance (a sign test: 14 better and 2 worse is; 6 and 5 isn't), with the
likely range of each pass rate. To measure your own noise, compare two runs of an unchanged agent.

When a case changed, ask it again before believing the change:

```bash
aiquality repeat --team my_team --cases S02,S03 --times 3
aiquality repeat --team my_team --changed-between history/before.jsonl aiquality-runs   # every case that changed
```

It asks the live agent each case `--times` times (recorded answers would be the same every time),
scores every answer with every check, and shows per case and per check how many repeats passed:
`3/3` holds, `1/3 *` is a coin toss whatever one run said. Each check is counted on its own,
because a model judge can change its verdict on the same facts while a phrase check changes only
with the wording. Every answer, its tool calls and its results are saved to
`aiquality-runs/repeat_check.jsonl` as each repeat finishes. A model agent costs one call per answer,
plus one judge call per answer when the team has a judge (see `examples/18_repeat_cases.py`).
In a notebook whose key is a notebook secret (Colab), run it from Python, where the secret can be read:
`repeat_team(TeamConfig.load(...), ["S02"], times=3)` from `aiquality.commands`; a shell command such as
`!aiquality repeat` runs in a separate process and only sees a key set as an environment variable.

## 12. Extend without forking

Add a check: one class with `@register_check("name")` in a file in your team folder, list that
file under `plugins:` in the config, and use the check's name under `checks:`
(see `examples/09_add_your_own_check.py`). Add an attack family the same way with
`@register_attack("name")` (`examples/10_add_your_own_attack.py`), a judge with
`@register_judge("kind")` (`examples/16_review_queue.py`), and a report format with
`@register_reporter("name")`.

## 13. Evidence for the laws and standards you answer to

Name your risk level and frameworks in the config:

```yaml
compliance:
  risk_level: limited       # minimal | limited | high: the usual names for the EU AI Act's tiers (the Act
                            # names high risk, its Annex III; limited means Art. 50's transparency duty)
  frameworks: [eu-ai-act, nist-ai-rmf, dpdp, owasp-llm]
```

After a gate run, `aiquality evidence --team my_team` writes `aiquality-runs/evidence/my_team/`:
`index.html` (search, filters, a link to every control, a what-if risk level), `evidence.md` and
`evidence.json`. Each control is labelled from the run's own evidence: applies with evidence, applies
with a bar not met, applies with no evidence, good practice, not required here, or outside the tool.
`--as high` reads the same run at another risk level.

The frameworks that come with the platform are in `aiquality/compliance/frameworks/`, one YAML file
each. To add your organisation's own policy, or change a built-in one, put a file with the same shape
in `my_team/frameworks/`: each control names the evidence that shows it (`check:<name>`,
`attack_resistance`, `release_gate`, `golden_set`, `judge_validation`, `human_review`, `run_records`),
or says why a test run can't (`outside_the_tool`). The report is evidence for an assessment, not a
compliance decision.
