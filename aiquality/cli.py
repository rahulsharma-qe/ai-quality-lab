"""Command line:  aiquality <command> ...

  aiquality evaluate --team aeroassist          score the team's agent on its golden set
  aiquality evaluate --team aeroassist --live   use the live agent instead of recorded answers
  aiquality record   --team aeroassist          record the live agent's answers for replay
  aiquality new-team claims_assist --format json
  aiquality list-checks

Exit codes: 0 done · 2 setup problem (bad config, missing file, agent unreachable).
(1 is reserved for "quality below the bar", used by the release gate.)
"""

import argparse
import sys
from pathlib import Path

from aiquality.checks import describe_checks
from aiquality.commands import DEFAULT_OUTPUT_DIR, create_team_scaffold, evaluate_team, record_team
from aiquality.config import TeamConfig
from aiquality.errors import SetupError

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


def _record(args) -> int:
    config = TeamConfig.load(_team_path(args.team, args.teams_dir))
    path, summary = record_team(config, Path(args.output) if args.output else None)
    print(f"recorded {summary.written} answers to {path}")
    for case_id, reason in summary.failed.items():
        print(f"  not recorded {case_id}: {reason}")
    return EXIT_OK if not summary.failed else EXIT_SETUP_ERROR


def _new_team(args) -> int:
    folder = create_team_scaffold(args.name, Path(args.teams_dir), args.format)
    print(f"created {folder}\nnext: edit agent.py and golden_set.csv, then run:\n"
          f"  aiquality evaluate --team {args.name}")
    return EXIT_OK


def _list_checks(args) -> int:
    for name, description in describe_checks().items():
        print(f"{name:<20}{description}")
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

    record = commands.add_parser("record", help="record the live agent's answers for key-free replay")
    add_team_arguments(record)
    record.add_argument("--output", help="file to write (default: the team's recorded answers file)")
    record.set_defaults(handler=_record)

    new_team = commands.add_parser("new-team", help="create a starter team folder that already runs")
    new_team.add_argument("name")
    new_team.add_argument("--teams-dir", default="teams")
    new_team.add_argument("--format", choices=("yaml", "json"), default="yaml")
    new_team.set_defaults(handler=_new_team)

    list_checks = commands.add_parser("list-checks", help="show the checks a team can use")
    list_checks.set_defaults(handler=_list_checks)
    return parser


if __name__ == "__main__":
    sys.exit(main())
