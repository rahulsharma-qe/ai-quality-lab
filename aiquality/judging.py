"""A team's judge, built from its config: validate it against people's labels, and look up whether
this exact judge version has earned the right to gate.

    judge = build_judge(config)                     # the judge the 'judge:' block describes
    run = validate_team_judge(config, "holdout")    # measured against labels, saved with its version
    team_judge_status(config, judge)                # 'qualified', 'not_qualified' or 'unvalidated'
"""

from typing import Optional

from aiquality.config import TeamConfig
from aiquality.config.judge_settings import POLICY_JUDGE
from aiquality.errors import ConfigError
from aiquality.judges import create_judge
from aiquality.judges.validation import ValidationRun, judge_status, load_labels, save_run, validate_judge


def build_judge(config: TeamConfig, kind: Optional[str] = None, chat=None):
    """The team's judge. kind overrides the configured kind (e.g. 'phrase' for a key-free plumbing run);
    chat replaces the model client (tests)."""
    settings = _judge_settings(config)
    kind = kind or settings.kind
    if kind != POLICY_JUDGE:
        return create_judge(kind, **settings.options)
    options = {"policy_text": config.policies.read_text(encoding="utf-8")}
    if settings.rubric:
        options["rubric"] = settings.rubric.read_text(encoding="utf-8")
        options["rubric_version"] = settings.rubric_version or settings.rubric.stem
    if settings.model:
        options["model"] = settings.model
    if chat is not None:
        options["chat"] = chat
    return create_judge(POLICY_JUDGE, **options)


def validate_team_judge(config: TeamConfig, split: str = "tune", kind: Optional[str] = None,
                        judge=None) -> ValidationRun:
    """Measure the team's judge against its labels and append the result to its results file."""
    settings = _judge_settings(config)
    if not settings.labels:
        raise ConfigError(config.source, ["validating a judge needs 'judge.labels': people's PASS / FAIL labels"])
    items, skipped = load_labels(settings.labels, split)
    if not items:
        raise ConfigError(config.source, [f"no labelled cases in the '{split}' split of {settings.labels}"])
    run = validate_judge(judge or build_judge(config, kind), items, split, skipped_unlabelled=skipped)
    save_run(run, settings.results)
    return run


def team_judge_status(config: TeamConfig, judge) -> str:
    return judge_status(judge.version, _judge_settings(config).results)


def _judge_settings(config: TeamConfig):
    if config.judge is None:
        raise ConfigError(config.source, ["no 'judge' block in the team config"])
    return config.judge
