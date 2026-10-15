# aiquality architecture

`aiquality` turns this repository's evaluation work into a self-serve platform. A team
connects its agent and brings one config file and a golden set, with no test code. It gets
evaluation, attack tests, a release gate, a human review queue, monitoring and reports.

**Status key:** solid boxes are in the `aiquality` package today. Dashed boxes are either
standalone scripts in this repository that are moving into the package, or planned.

## 1. Components

```mermaid
flowchart LR
  subgraph TEAM["What a team brings - no test code"]
    CFG["team.yaml or team.json"]
    GS["Golden set<br/>JSON · CSV · Excel"]
    POL["policies.md"]
    AG["Their agent"]
  end
  subgraph CORE["aiquality package"]
    TC["TeamConfig<br/>+ CompanyMinimums"]
    TD["Test data<br/>load_golden_set · GoldenCaseBuilder"]
    AD["Adapters<br/>PythonFunction · HttpEndpoint · RecordedResponses"]
    ATK["Attacks registry<br/>register_attack"]
    RUN["Runner"]
    CHK["Checks registry<br/>register_check"]
    JDG["Judges<br/>AnswerJudge · JudgeValidator"]
    MDL["ChatModel<br/>provider-neutral"]
    GATE["ReleaseGate<br/>PASS or FAIL<br/>+ advisory findings"]
    RR["RunRecord - JSONL<br/>personal data redacted"]
    MON["Monitoring<br/>tracing · drift"]
  end
  subgraph OUT["Outputs"]
    EXIT["Exit code<br/>CI blocks or passes"]
    REP["Reports - register_reporter<br/>console · HTML · JUnit XML · GitHub summary"]
    CMP["Compare two runs<br/>fixed · newly failing · still failing"]
    HRQ["Human review queue<br/>advisory findings"]
    GV["Gate view<br/>static HTML"]
    OTEL["OpenTelemetry to Phoenix or Langfuse<br/>optional, off by default"]
  end
  CFG --> TC
  GS --> TD
  AG --> AD
  POL --> JDG
  TC --> RUN
  TD --> RUN
  ATK --> RUN
  AD --> RUN
  RUN --> CHK
  CHK --> JDG
  JDG --> MDL
  CHK --> GATE
  TC --> GATE
  JDG -.->|"judge status per version"| GATE
  GATE --> EXIT
  GATE --> RR
  RR --> REP
  RR --> CMP
  RR --> HRQ
  RR --> GV
  RUN -.->|"traces"| MON
  RR -->|"history"| MON
  MON --> OTEL
  classDef later stroke-dasharray: 5 5
  class JDG,MDL,MON,HRQ,GV,OTEL later
```

| Part | Status |
|---|---|
| Contracts, adapters, team config, company minimums, test data, runner, checks registry, attacks registry, release gate (per team and client, accepted findings), RunRecord, console / HTML / JUnit XML / GitHub summary reports, run comparison, command line | In the package |
| Judges, judge validation, model layer, monitoring | Standalone scripts in this repo (`answer_judge.py`, `judge_validation.py`, `llm.py`, `observability/`), moving into the package |
| Human review queue, reusable CI workflow, gate view, tracing export | Planned |

## 2. One gate run, step by step

```mermaid
sequenceDiagram
  autonumber
  participant CI as CI or developer
  participant CLI as aiquality gate
  participant Cfg as TeamConfig
  participant Agent as AgentUnderTest
  participant Checks as Checks and judge
  participant Gate as ReleaseGate
  participant Rec as RunRecord and reports
  CI->>CLI: aiquality gate --team claims_assist
  CLI->>Cfg: load team.json, validate, apply company floor
  alt config invalid or agent unreachable
    CLI-->>CI: exit 2, setup error, not a quality result
  end
  CLI->>Agent: ask every golden case and attack case
  Agent-->>CLI: AgentResponse with answer, tools, documents, time
  CLI->>Checks: score each response
  Checks-->>CLI: CheckResult per case, judge version and mode
  Note over Checks: errored calls are reported separately, never counted as a pass
  CLI->>Gate: compare blocking checks with team bars, per client
  Gate-->>CLI: PASS or FAIL with reasons, plus advisory findings
  CLI->>Rec: write RunRecord, build reports, queue advisory findings
  CLI-->>CI: exit 0 for pass, 1 for fail
```

`aiquality gate` runs all of these steps; the human review queue for advisory (judge) findings is
planned. `aiquality evaluate` runs the same steps without the decision and never blocks.
Exit codes: 0 done or pass · 1 quality below the bar (release gate) · 2 setup error.

## 3. How a team uses it in CI (target design: the reusable workflow and review queue are planned)

```mermaid
flowchart LR
  A["Pull request<br/>prompt, model, policy or config change"] --> B["Team workflow calls<br/>reusable-quality-gate.yml"]
  B --> C["aiquality gate --team name"]
  C --> D{"Gate decision"}
  D -->|"PASS"| E["Merge allowed<br/>reports attached"]
  D -->|"FAIL"| F["Merge blocked<br/>reasons in the job summary"]
  D -.->|"advisory findings"| Q["Human review queue"]
  G["Nightly or on demand"] --> H["Live judge run"]
  H --> Q
```

In this repository the per-change checks run without an API key: demo agents, recorded
answers and rule-based checks. A team testing its live agent gives the workflow that agent's
access through CI secrets. Blocking a merge also needs branch protection in that repository.

## 4. Key design decisions

- **One contract.** Every agent is reached through `answer(question, conversation) -> AgentResponse`.
  Evidence the adapter can't see (tool calls, retrieved documents) stays `None`, and checks that
  need it report `NOT_APPLICABLE`, never a pass.
- **Every check is a pass rate.** Each check decides PASS or FAIL per case; the score is
  PASS / (PASS + FAIL), compared with a threshold. Not-applicable cases and errors are counted
  and shown, never folded into the score.
- **Configuration, not code.** Team settings are validated against a schema, every problem is
  listed at once, and the company floor applies: a team can be stricter, never looser.
- **Secrets stay out of files.** Configs name environment variables; anything that looks like a
  secret in a config is rejected.
- **Recorded answers keep CI key-free.** A live agent's answers are recorded once and replayed;
  every run record says whether it was `live` or `recorded`.
- **Phrase checks are cheap signals.** Whole-word matching avoids substring mistakes, but meaning
  (for example "not approved") needs a judge; a match right after a negation word is flagged.
- **One result format.** Every command writes a RunRecord with a `schema_version`; every report
  reads it.
- **The gate reads strictly.** Errors count as failures, a mandatory check with no applicable case
  fails for lack of evidence, and each client tag must meet the bar on its own.
- **Exceptions are owned and expire.** An accepted finding names one case and one check, a reason,
  an approver and an expiry within 90 days, and is listed in every report.
- **Attacks are data plus plugins.** Teams write goals; families turn them into cases built the same
  way every run, so recorded answers can be replayed.
