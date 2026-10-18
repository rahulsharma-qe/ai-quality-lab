"""What each command does, as plain functions. The command line and the examples both call these."""

from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Optional

from aiquality.adapters import RecordedResponsesAgent, RecordingSummary, build_agent, record_responses
from aiquality.attacks import build_attack_cases
from aiquality.config import CompanyMinimums, TeamConfig
from aiquality.contracts import AgentUnderTest
from aiquality.errors import ConfigError, SetupError
from aiquality.evaluation import evaluate_runs
from aiquality.gate import GateDecision, ReleaseGate
from aiquality.judges.recorded import VerdictRecordingSummary, record_verdicts
from aiquality.judging import build_judge, judge_for_run, judge_summary
from aiquality.reporting import RunRecord, create_reporter
from aiquality.reporting.redaction import redact_personal_data
from aiquality.reporting.repeats import RepeatRow, RepeatSummary, save_repeat_rows, summarise_repeats
from aiquality.runner import Runner
from aiquality.test_data import load_golden_set
from aiquality.test_data.lint import lint_golden_set

DEFAULT_OUTPUT_DIR = "aiquality-runs"
REPEAT_FILE = "repeat_check.jsonl"
JUDGE_CHECK = "answer_judge"


def evaluate_team(config: TeamConfig, live: bool = False, output_dir=DEFAULT_OUTPUT_DIR,
                  agent: Optional[AgentUnderTest] = None, print_reports: bool = True,
                  include_golden: bool = True, include_attacks: bool = True,
                  command: str = "evaluate") -> RunRecord:
    """Ask the team's agent its golden and attack cases, score them, save a RunRecord, write reports.

    live=True uses the team's live_agent instead of its default agent.
    agent=... overrides both (handy in examples and tests).
    """
    record, _, _ = _run_and_score(config, live, agent, include_golden, include_attacks, command)
    _save_and_report(record, config, output_dir, print_reports)
    return record


def gate_team(config: TeamConfig, live: bool = False, output_dir=DEFAULT_OUTPUT_DIR,
              agent: Optional[AgentUnderTest] = None, print_reports: bool = True,
              today: Optional[date] = None) -> tuple[RunRecord, GateDecision]:
    """Evaluate golden and attack cases, then decide PASS or FAIL against the team's bars."""
    record, evaluation, check_settings = _run_and_score(config, live, agent, True, True, "gate")
    mandatory = CompanyMinimums.load().mandatory_checks
    decision = ReleaseGate(config, mandatory, today, check_settings).decide(evaluation)
    decision.warnings += [f"golden set: {warning}" for warning in record.golden_set_warnings]
    if record.judge and not record.judge["blocking"]:
        decision.warnings.append(f"answer_judge is advisory: judge {record.judge['version']} is "
                                 f"{record.judge['status'].replace('_', ' ')}, so it reports but can't block")
    record.gate_decision = decision.to_dict()
    _save_and_report(record, config, output_dir, print_reports)
    return record, decision


def _run_and_score(config, live, agent, include_golden, include_attacks, command):
    agent_settings = _pick_agent_settings(config, live)
    agent = agent or build_agent(agent_settings, config.folder, team_name=config.team)
    golden_set, cases = team_cases(config, include_golden, include_attacks)
    case_runs = Runner(agent, max_error_rate=config.max_error_rate).run(cases)
    check_settings, judge_info = _check_settings_with_judge(config, live)
    evaluation = evaluate_runs(case_runs, check_settings, default_client=config.client)
    run_mode = "recorded" if isinstance(agent, RecordedResponsesAgent) else "live"
    record = RunRecord.from_evaluation(evaluation, command=command, team=config.team, client=config.client,
                                       run_mode=run_mode, agent_name=agent.name, agent_version=agent.version,
                                       golden_set=golden_set)
    record.judge = judge_info
    record.golden_set_warnings = lint_golden_set(golden_set)
    record.description, record.expected_result = config.description, config.expected_result
    return record, evaluation, check_settings


def _check_settings_with_judge(config: TeamConfig, live: bool, judge=None):
    """The team's check settings, with its judge handed to the answer_judge check. That check may
    block only if the config says so AND this judge version has qualified against people's labels.
    judge=... replaces the configured judge (examples and tests)."""
    settings = config.checks.get(JUDGE_CHECK)
    if settings is None:
        return config.checks, None
    judge, mode = (judge, "given") if judge is not None else judge_for_run(config, live)
    info = judge_summary(config, judge, mode, settings.blocking)
    with_judge = dict(config.checks)
    with_judge[JUDGE_CHECK] = replace(settings, blocking=info["blocking"],
                                      options={**settings.options, "judge": judge})
    return with_judge, info


def _save_and_report(record: RunRecord, config: TeamConfig, output_dir, print_reports: bool) -> None:
    record.save(output_dir)
    if print_reports:
        write_reports(record, config.reports, output_dir)


def attack_team(config: TeamConfig, **options) -> RunRecord:
    """Run only the team's attack cases."""
    if not config.attacks:
        raise ConfigError(config.source, ["no 'attacks' block in the team config"])
    return evaluate_team(config, include_golden=False, include_attacks=True, command="attack", **options)


def team_cases(config: TeamConfig, include_golden: bool = True, include_attacks: bool = True):
    """The golden set, and the list of cases to ask: golden cases, then attack cases."""
    golden_set = load_golden_set(config.golden_set)
    cases = list(golden_set.cases) if include_golden else []
    if include_attacks and config.attacks:
        cases += build_attack_cases(config.attacks.families, config.attacks.goals)
    return golden_set, cases


def write_reports(record: RunRecord, report_names: list[str], output_dir) -> list[Path]:
    written = []
    for report_name in report_names:
        path = create_reporter(report_name).write(record, Path(output_dir))
        if path is not None:
            written.append(path)
    return written


def record_team(config: TeamConfig, output_path: Optional[Path] = None) -> tuple[Path, RecordingSummary]:
    """Ask the team's LIVE agent every golden and attack case once and save the answers for replay.

    By default the answers go to the file the team's recorded_responses agent reads.
    """
    if not config.live_agent:
        raise ConfigError(config.source, ["recording needs a 'live_agent' block in the team config"])
    if output_path is None:
        if config.agent.get("adapter") != "recorded_responses":
            raise ConfigError(config.source, ["give an output path, or set agent.adapter to recorded_responses"])
        output_path = config.folder / config.agent["path"]
    live_agent = build_agent(config.live_agent, config.folder, team_name=config.team)
    _, cases = team_cases(config)
    return Path(output_path), record_responses(live_agent, cases, Path(output_path))


def repeat_team(config: TeamConfig, case_ids: list[str], times: int = 3, output_path=None,
                agent: Optional[AgentUnderTest] = None, judge=None) -> tuple[Path, RepeatSummary]:
    """Ask the agent the chosen cases `times` times each and score every answer with every check,
    to see which results hold and which vary. One row per case per repeat is saved as JSONL.

    Recorded answers are the same every time, so this asks the team's live_agent (or its default agent
    when that isn't a recording), and grades with the live judge. agent=... and judge=... replace both
    (examples and tests). The file is started afresh, and each repeat is saved as soon as it is done,
    so an interrupted run keeps the answers it paid for.
    """
    if times < 1:
        raise SetupError("--times must be 1 or more")
    agent = agent or _repeat_agent(config)
    cases = _pick_cases(config, case_ids)
    check_settings, _ = _check_settings_with_judge(config, live=True, judge=judge)
    path = Path(output_path or Path(DEFAULT_OUTPUT_DIR) / REPEAT_FILE)
    all_rows = []
    for repeat in range(1, times + 1):
        case_runs = Runner(agent, max_error_rate=config.max_error_rate).run(cases)
        evaluation = evaluate_runs(case_runs, check_settings, default_client=config.client)
        rows = [_repeat_row(outcome, run, repeat, agent.version)
                for outcome, run in zip(evaluation.outcomes, case_runs)]
        save_repeat_rows(rows, path, append=repeat > 1)
        all_rows += rows
    return path, summarise_repeats(all_rows)


def _repeat_agent(config: TeamConfig) -> AgentUnderTest:
    settings = config.live_agent or config.agent
    if settings.get("adapter") == "recorded_responses":
        raise ConfigError(config.source, ["repeating needs an agent that really answers: recorded answers are the "
                                          "same every time. Add a 'live_agent' block to the team config"])
    return build_agent(settings, config.folder, team_name=config.team)


def _pick_cases(config: TeamConfig, case_ids: list[str]) -> list:
    _, cases = team_cases(config)
    by_id = {case.id: case for case in cases}
    wanted = list(dict.fromkeys(case_ids))
    unknown = [case_id for case_id in wanted if case_id not in by_id]
    if unknown:
        raise SetupError(f"no case with id {', '.join(unknown)} in team {config.team}'s golden set or attacks")
    if not wanted:
        raise SetupError("no cases to repeat: name them with --cases or --changed-between")
    return [by_id[case_id] for case_id in wanted]


def _repeat_row(outcome, case_run, repeat: int, agent_version: str) -> RepeatRow:
    response = case_run.response
    tool_calls = None if response is None or response.tool_calls is None else [t.to_dict() for t in response.tool_calls]
    results = [{"check": r.check_name, "status": r.status.value, "reason": redact_personal_data(r.reason),
                "flags": list(r.flags)} for r in outcome.results]
    return RepeatRow(case_id=outcome.case_id, repeat=repeat, agent_version=agent_version,
                     answer_text=redact_personal_data(outcome.answer_text), error=outcome.error,
                     tool_calls=tool_calls, results=results)


def record_judge_verdicts(config: TeamConfig, chat=None) -> tuple[Path, VerdictRecordingSummary]:
    """Grade the team's current answers (its default agent, usually the recording) once with the LIVE
    judge, and save the verdicts so CI can replay them without a key. Golden cases only."""
    if config.judge is None or config.judge.recorded is None:
        raise ConfigError(config.source, ["recording verdicts needs 'judge.recorded: <file>' in the team config"])
    agent = build_agent(config.agent, config.folder, team_name=config.team)
    _, cases = team_cases(config, include_attacks=False)
    answered = [(run.case, run.response.answer_text) for run in Runner(agent, config.max_error_rate).run(cases)
                if run.succeeded]
    return config.judge.recorded, record_verdicts(build_judge(config, chat=chat), answered, config.judge.recorded)


def _pick_agent_settings(config: TeamConfig, live: bool) -> dict:
    if not live:
        return config.agent
    if not config.live_agent:
        raise ConfigError(config.source, ["--live needs a 'live_agent' block in the team config"])
    return config.live_agent
