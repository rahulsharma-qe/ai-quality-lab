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
aiquality evaluate --team my_team          # the starter already runs
```

This creates `teams/my_team/` with `team.yaml`, `golden_set.csv` and a starter `agent.py`.

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
| `client` | Optional tag, so results can be compared per client |
| `conversation_history` | Optional earlier turns, as JSON text |

Tips: phrases match as whole words in any case, so `100` won't match inside `1000`; a simple
plural still counts (`2 hour` matches `2 hours`). Accept equivalent wording with an uppercase
`OR`: `connect OR escalate`. Phrase
checks can't understand "not": if `approved` is forbidden, the answer "not approved" still
matches (it is flagged as a possible false alarm). Make forbidden phrases specific, such as
`refund approved`, and put behaviour rules in `must_not_do`.

## 5. Choose checks and thresholds

```bash
aiquality list-checks
```

Every check is a pass rate from 0 to 1. Your threshold can be stricter than the company
minimum (`aiquality/config/company_minimums.yaml`), never looser, and mandatory checks
can't be removed.

## 6. Run and read the results

```bash
aiquality evaluate --team my_team
```

The console shows each check's pass rate against its threshold and every finding, with the
sentence that triggered it. Each run is appended to `aiquality-runs/run_records.jsonl`.

Exit codes: 0 done · 2 setup problem (fix the config, the file paths or the agent connection).

## 7. Extend without forking

Add a check: one class with `@register_check("name")` in a file in your team folder, list that
file under `plugins:` in the config, and use the check's name under `checks:`
(a small example: `test_a_team_plugin_adds_its_own_check` in `tests/test_team_config.py`).
Add a report format: one class with `@register_reporter("name")`.
