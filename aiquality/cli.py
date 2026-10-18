"""Command line:  aiquality <command> ...

  aiquality evaluate --team aeroassist          score the team's agent on its golden and attack cases
  aiquality attack   --team aeroassist          run only the attack tests
  aiquality gate     --team aeroassist          evaluate, then PASS (exit 0) or FAIL (exit 1)
  aiquality evaluate --team aeroassist --live   use the live agent instead of recorded answers
  aiquality record   --team aeroassist          record the live agent's answers for replay
  aiquality record   --team aeroassist --judge  record the live judge's verdicts on those answers
  aiquality compare  history/before.jsonl aiquality-runs   what got fixed, what newly fails
  aiquality repeat   --team aeroassist --cases GD13,GD18 --times 3   which results hold, which vary
  aiquality repeat   --team aeroassist --changed-between before.jsonl aiquality-runs   ask again what changed
  aiquality validate-judge --team aeroassist --split holdout   measure the judge against people's labels
  aiquality review   --team aeroassist          what a person should look at from the latest run, and why
  aiquality new-team claims_assist --format json
  aiquality lint     --team aeroassist          golden-set mistakes that would cause false alarms
  aiquality dashboard --output dashboard.html   every team now, and run by run (from saved run records)
  aiquality export-traces aiquality-runs --output traces.json   a run as OpenTelemetry traces
  aiquality list-checks
  aiquality list-attacks

Exit codes: 0 done or gate passed · 1 gate failed (quality below the bar) ·
2 setup problem (bad config, missing file, agent unreachable), never reported as a quality failure.
"""

import argparse
import sys
from datetime import date
from pathlib import Path

from aiquality.attacks import describe_attacks
from aiquality.checks import describe_checks
from aiquality.commands import (DEFAULT_OUTPUT_DIR, REPEAT_FILE, attack_team, create_team_scaffold, evaluate_team,
                                gate_team, record_judge_verdicts, record_team, repeat_team)
from aiquality.config import TeamConfig
from aiquality.errors import SetupError
from aiquality.judges import available_judges
from aiquality.judges.validation import render_validation
from aiquality.reporting import (changed_cases, compare_runs, pick_run, render_comparison, render_comparison_markdown,
                                 render_repeats)

EXIT_OK = 0
EXIT_QUALITY_FAILURE = 1
EXIT_SETUP_ERROR = 2


def main(argv=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return EXIT_SETUP_ERROR
    try:
        return args.handler(args)
    except SetupError as error:
        print(f"SETUP ERROR (exit {EXIT_SETUP_ERROR}): {error}", file=sys.stderr)
        return EXIT_SETUP_ERROR


def _evaluate(args) -> int:
    config = TeamConfig.load(_team_path(args.team, args.teams_dir))
    evaluate_team(config, live=args.live, output_dir=args.output_dir)
    print(f"\nrun record saved in {Path(args.output_dir) / 'run_records.jsonl'}")
    return EXIT_OK


def _gate(args) -> int:
    config = TeamConfig.load(_team_path(args.team, args.teams_dir), today=args.today)
    _, decision = gate_team(config, live=args.live, output_dir=args.output_dir, today=args.today)
    return EXIT_OK if decision.passed else EXIT_QUALITY_FAILURE


def _attack(args) -> int:
    config = TeamConfig.load(_team_path(args.team, args.teams_dir))
    attack_team(config, live=args.live, output_dir=args.output_dir)
    return EXIT_OK


def _record(args) -> int:
    config = TeamConfig.load(_team_path(args.team, args.teams_dir))
    if args.judge:
        path, summary = record_judge_verdicts(config)
        print(f"recorded {summary.written} judge verdicts to {path}")
        for case_id, reason in summary.failed.items():
            print(f"  not recorded {case_id}: {reason}")
        return EXIT_OK if not summary.failed else EXIT_SETUP_ERROR
    path, summary = record_team(config, Path(args.output) if args.output else None)
    print(f"recorded {summary.written} answers to {path}")
    for case_id, reason in summary.failed.items():
        print(f"  not recorded {case_id}: {reason}")
    return EXIT_OK if not summary.failed else EXIT_SETUP_ERROR


def _compare(args) -> int:
    comparison = compare_runs(pick_run(args.before, args.before_run), pick_run(args.after, args.after_run))
    print(render_comparison(comparison))
    if args.markdown:
        Path(args.markdown).write_text(render_comparison_markdown(comparison) + "\n", encoding="utf-8")
        print(f"\nmarkdown written to {args.markdown}")
    if args.fail_on_new_failures and comparison.has_new_failures:
        return EXIT_QUALITY_FAILURE
    return EXIT_OK


def _repeat(args) -> int:
    config = TeamConfig.load(_team_path(args.team, args.teams_dir))
    case_ids = [case_id.strip() for case_id in (args.cases or "").split(",") if case_id.strip()]
    if args.changed_between:
        before, after = (pick_run(path) for path in args.changed_between)
        changed = changed_cases(before, after)
        print(f"{len(changed)} cases changed between the two runs: {', '.join(changed) or 'none'}")
        case_ids += changed
    case_ids = list(dict.fromkeys(case_ids))
    print(f"asking {len(case_ids)} cases {args.times} times: {len(case_ids) * args.times} answers, each scored by "
          f"every check (with a model judge, that is one judge call per answer too)\n")
    path, summary = repeat_team(config, case_ids, args.times, args.output or Path(args.output_dir) / REPEAT_FILE)
    print(render_repeats(summary))
    print(f"\nanswers and results saved in {path}")
    return EXIT_OK


def _dashboard(args) -> int:
    from aiquality.reporting.dashboard import write_dashboard
    path = write_dashboard(args.output, args.output_dir, args.teams_dir)
    print(f"dashboard written to {path}")
    return EXIT_OK


def _export_traces(args) -> int:
    from aiquality.reporting.trace_export import write_traces
    record = pick_run(args.runs, args.run)
    path = write_traces(record, args.output)
    print(f"{len(record.outcomes)} cases of run {record.run_id} ({record.team}) written as traces to {path}")
    return EXIT_OK


def _validate_judge(args) -> int:
    from aiquality.judging import validate_team_judge
    config = TeamConfig.load(_team_path(args.team, args.teams_dir))
    run = validate_team_judge(config, args.split, kind=args.kind)
    print(render_validation(run))
    return EXIT_QUALITY_FAILURE if run.qualified is False else EXIT_OK


def _review(args) -> int:
    from aiquality.review import build_review_queue, last_run_for_team, render_review_queue, write_review_queue
    config = TeamConfig.load(_team_path(args.team, args.teams_dir))
    record = last_run_for_team(args.output_dir, config.team)
    items = build_review_queue(record)
    print(f"from run {record.run_id} ({record.created_at})")
    print(render_review_queue(items, config.team))
    path = write_review_queue(items, Path(args.output_dir) / f"{config.team}-review-queue.jsonl")
    print(f"\nqueue written to {path}")
    return EXIT_OK


def _lint(args) -> int:
    from aiquality.test_data import load_golden_set
    from aiquality.test_data.lint import lint_golden_set
    config = TeamConfig.load(_team_path(args.team, args.teams_dir))
    warnings = lint_golden_set(load_golden_set(config.golden_set))
    print("\n".join(f"warning: {w}" for w in warnings) or "golden set: no warnings")
    return EXIT_OK


def _ci_summary(args) -> int:
    from aiquality.reporting.ci_summary import render_ci_summary
    print(render_ci_summary(args.output_dir))
    return EXIT_OK


def _list_judges(args) -> int:
    for kind in available_judges():
        print(kind)
    return EXIT_OK


def _new_team(args) -> int:
    folder = create_team_scaffold(args.name, Path(args.teams_dir), args.format)
    print(f"created {folder}\nnext: edit agent.py and golden_set.csv, then run:\n"
          f"  aiquality evaluate --team {args.name}")
    return EXIT_OK


def _list_checks(args) -> int:
    for name, description in describe_checks().items():
        print(f"{name:<20}{description}")
    return EXIT_OK


def _list_attacks(args) -> int:
    for name, description in describe_attacks().items():
        print(f"{name:<24}{description}")
    return EXIT_OK


def _team_path(team: str, teams_dir: str) -> Path:
    """--team accepts a name under --teams-dir, a team folder, or a config file."""
    direct = Path(team)
    return direct if direct.exists() else Path(teams_dir) / team


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aiquality", description="Quality checks for AI agents.")
    commands = parser.add_subparsers(dest="command")

    def add_team_arguments(command):
        command.add_argument("--team", required=True, help="team name, team folder or config file")
        command.add_argument("--teams-dir", default="teams", help="folder holding team folders (default: teams)")

    evaluate = commands.add_parser("evaluate", help="score the team's agent on its golden set")
    add_team_arguments(evaluate)
    evaluate.add_argument("--live", action="store_true", help="use the live agent (may need an API key)")
    evaluate.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="where run records go")
    evaluate.set_defaults(handler=_evaluate)

    gate = commands.add_parser("gate", help="evaluate, then PASS (exit 0) or FAIL (exit 1) against the bars")
    add_team_arguments(gate)
    gate.add_argument("--live", action="store_true", help="use the live agent (may need an API key)")
    gate.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="where run records and reports go")
    gate.add_argument("--today", type=date.fromisoformat, metavar="YYYY-MM-DD",
                      help="decide as if today were this date; for checking expiries")
    gate.set_defaults(handler=_gate)

    attack = commands.add_parser("attack", help="run only the team's attack tests")
    add_team_arguments(attack)
    attack.add_argument("--live", action="store_true", help="use the live agent (may need an API key)")
    attack.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="where run records go")
    attack.set_defaults(handler=_attack)

    record = commands.add_parser("record", help="record the live agent's answers for key-free replay")
    add_team_arguments(record)
    record.add_argument("--output", help="file to write (default: the team's recorded answers file)")
    record.add_argument("--judge", action="store_true",
                        help="record the live judge's verdicts on the current answers instead (judge.recorded)")
    record.set_defaults(handler=_record)

    compare = commands.add_parser("compare", help="compare two runs case by case: fixed, newly failing, still failing")
    compare.add_argument("before", help="run_records.jsonl (or its folder) holding the baseline run")
    compare.add_argument("after", help="run_records.jsonl (or its folder) holding the new run")
    compare.add_argument("--before-run", help="run id in the before file (default: its last run)")
    compare.add_argument("--after-run", help="run id in the after file (default: its last run)")
    compare.add_argument("--markdown", help="also write the comparison as Markdown to this file")
    compare.add_argument("--fail-on-new-failures", action="store_true",
                         help="exit 1 when a case that passed before fails now")
    compare.set_defaults(handler=_compare)

    repeat = commands.add_parser("repeat", help="ask chosen cases several times: which results hold, which vary")
    add_team_arguments(repeat)
    repeat.add_argument("--cases", help="case ids, comma separated, e.g. GD13,GD18")
    repeat.add_argument("--changed-between", nargs=2, metavar=("BEFORE", "AFTER"),
                        help="also every case whose result on any check differs between two saved runs")
    repeat.add_argument("--times", type=int, default=3, help="answers per case (default: 3)")
    repeat.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help=f"where {REPEAT_FILE} goes")
    repeat.add_argument("--output", help="file to write instead (started afresh)")
    repeat.set_defaults(handler=_repeat)

    validate = commands.add_parser("validate-judge", help="measure the team's judge against people's labels")
    add_team_arguments(validate)
    validate.add_argument("--split", choices=("tune", "holdout", "all"), default="tune",
                          help="tune: improve the judge here; holdout: the real measurement (default: tune)")
    validate.add_argument("--kind", help="use another judge kind, e.g. 'phrase' for a key-free plumbing run")
    validate.set_defaults(handler=_validate_judge)

    new_team = commands.add_parser("new-team", help="create a starter team folder that already runs")
    new_team.add_argument("name")
    new_team.add_argument("--teams-dir", default="teams")
    new_team.add_argument("--format", choices=("yaml", "json"), default="yaml")
    new_team.set_defaults(handler=_new_team)

    list_checks = commands.add_parser("list-checks", help="show the checks a team can use")
    list_checks.set_defaults(handler=_list_checks)

    list_attacks = commands.add_parser("list-attacks", help="show the attack families a team can use")
    list_attacks.set_defaults(handler=_list_attacks)

    review = commands.add_parser("review", help="what a person should look at from the team's latest run, and why")
    add_team_arguments(review)
    review.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="where the run records are")
    review.set_defaults(handler=_review)

    lint = commands.add_parser("lint", help="check the team's golden set for mistakes that cause false alarms")
    add_team_arguments(lint)
    lint.set_defaults(handler=_lint)

    ci_summary = commands.add_parser("ci-summary", help="one run page: an overview of every team's gate, then each team")
    ci_summary.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="where the run records are")
    ci_summary.set_defaults(handler=_ci_summary)

    dashboard = commands.add_parser("dashboard", help="one page: every team's latest gate and its saved runs over time")
    dashboard.add_argument("--output", default=f"{DEFAULT_OUTPUT_DIR}/dashboard.html", help="the HTML file to write")
    dashboard.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="where the latest run records are")
    dashboard.add_argument("--teams-dir", default="teams", help="folder holding team folders and their history")
    dashboard.set_defaults(handler=_dashboard)

    traces = commands.add_parser("export-traces", help="write a run as OpenTelemetry traces (OTLP JSON) for a tracing tool")
    traces.add_argument("runs", help="run_records.jsonl (or its folder)")
    traces.add_argument("--run", help="run id (default: the last run in the file)")
    traces.add_argument("--output", default=f"{DEFAULT_OUTPUT_DIR}/traces.json", help="the file to write")
    traces.set_defaults(handler=_export_traces)

    list_judges = commands.add_parser("list-judges", help="show the judge kinds a team can use")
    list_judges.set_defaults(handler=_list_judges)
    return parser


if __name__ == "__main__":
    sys.exit(main())
