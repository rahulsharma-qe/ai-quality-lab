"""A team's judge, built from its config: validate it against people's labels, and look up whether
this exact judge version has earned the right to gate.

    judge = build_judge(config)                     # the judge the 'judge:' block describes
    run = validate_team_judge(config, "holdout")    # measured against labels, saved with its version
    team_judge_status(config, judge)                # 'qualified', 'not_qualified' or 'unvalidated'
    judge, mode = judge_for_run(config, live=False) # recorded verdicts when configured, else the live judge
"""

from typing import Optional

from aiquality.config import TeamConfig
from aiquality.config.judge_settings import POLICY_JUDGE
from aiquality.errors import ConfigError
from aiquality.judges import create_judge
from aiquality.judges.policy_judge import policy_judge_version
from aiquality.judges.recorded import RecordedJudge
from aiquality.models import JUDGE_MODEL
from aiquality.judges.validation import (STATUS_QUALIFIED, STATUS_UNVALIDATED, ValidationRun, held_back_measurements, judge_status,
                                         labels_sha, load_labels, save_run, validate_judge)


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
    judge = judge or build_judge(config, kind)
    run = validate_judge(judge, items, split, skipped_unlabelled=skipped, labels=labels_sha(settings.labels),
                         earlier_measurements=held_back_measurements(judge.version, settings.results))
    save_run(run, settings.results)
    return run


def team_judge_status(config: TeamConfig, judge) -> str:
    settings = _judge_settings(config)
    return judge_status(judge.version, settings.results, labels_sha(settings.labels) if settings.labels else "")


def judge_for_run(config: TeamConfig, live: bool):
    """(judge, mode) for an evaluation: the recorded verdicts when the team keeps them and the run is
    not live, otherwise the live judge."""
    settings = _judge_settings(config)
    if settings.recorded and not live:
        return RecordedJudge(settings.recorded), "recorded"
    return build_judge(config), "live"


def judge_summary(config: TeamConfig, judge, mode: str, configured_blocking: bool) -> dict:
    """What a run record says about its judge, including whether it was allowed to block. Recorded verdicts
    from a judge other than the one the config now describes (its policies or rubric changed since) don't
    carry that judge's status."""
    status, note = team_judge_status(config, judge), ""
    configured = configured_judge_version(config) if mode == "recorded" else None
    if configured and judge.version != configured:
        if configured.startswith(judge.version + ":"):
            note = ("the recorded verdicts were graded before judge versions included the policies: record the "
                    "judge again to check them against today's policies")
        else:
            status = STATUS_UNVALIDATED
            note = (f"the recorded verdicts were graded by judge {judge.version}, but the config now describes "
                    f"{configured} (policies or rubric changed): record the judge again")
    summary = {"check": "answer_judge", "version": judge.version, "mode": mode, "status": status,
               "blocking": configured_blocking and status == STATUS_QUALIFIED}
    if note:
        summary["note"] = note
    return summary


def configured_judge_version(config: TeamConfig) -> Optional[str]:
    """The version of the policy judge the config describes, without building it (no model client needed)."""
    settings = _judge_settings(config)
    if settings.kind != POLICY_JUDGE:
        return None
    rubric = settings.rubric.read_text(encoding="utf-8") if settings.rubric else None
    rubric_version = (settings.rubric_version or settings.rubric.stem) if settings.rubric else "default-v1"
    return policy_judge_version(settings.model or JUDGE_MODEL, rubric_version, rubric,
                                config.policies.read_text(encoding="utf-8"))


def _judge_settings(config: TeamConfig):
    if config.judge is None:
        raise ConfigError(config.source, ["no 'judge' block in the team config"])
    return config.judge
