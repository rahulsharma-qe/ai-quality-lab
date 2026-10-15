"""The 'judge:' block of a team config: which judge grades meaning, and where its evidence lives.

    judge:
      kind: policy_answer            # aiquality list-judges; or a team's own @register_judge kind
      rubric: judge_rubric.md        # optional: the team's own instructions for the judge
      rubric_version: v2             # a name for this rubric; part of the judge's version
      model: claude-sonnet-5-5       # optional: defaults to JUDGE_MODEL
      labels: judge_labels.json      # people's PASS / FAIL labels, for: aiquality validate-judge
      results: judge_validation_results.jsonl   # where validation runs are kept (default shown)
      recorded: judge_verdicts.jsonl # optional: replay recorded verdicts (CI needs no key);
                                     # record with: aiquality record --team <team> --judge
      options: {}                    # extra settings passed to a team's own judge kind

Paths are relative to the config file's folder. The policy_answer judge also needs the team's
'policies:' file, which it grades against.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from aiquality.judges import available_judges

JUDGE_SETTINGS = {"kind", "rubric", "rubric_version", "model", "labels", "results", "recorded", "options"}
DEFAULT_RESULTS_FILE = "judge_validation_results.jsonl"
POLICY_JUDGE = "policy_answer"


@dataclass
class JudgeSettings:
    kind: str
    rubric: Optional[Path] = None
    rubric_version: Optional[str] = None
    model: Optional[str] = None
    labels: Optional[Path] = None
    results: Optional[Path] = None
    recorded: Optional[Path] = None
    options: dict = field(default_factory=dict)


def parse_judge_settings(raw, folder: Path, has_policies: bool):
    """Return (JudgeSettings or None, problems). None when the team has no judge block."""
    if raw is None:
        return None, []
    if not isinstance(raw, dict):
        return None, ["'judge' must be a block of settings, e.g. {kind: policy_answer}"]
    problems = [f"'judge.{key}' is not a judge setting. Allowed: {', '.join(sorted(JUDGE_SETTINGS))}"
                for key in sorted(set(raw) - JUDGE_SETTINGS)]
    kind = raw.get("kind")
    if kind not in available_judges():
        problems.append(f"'judge.kind' must be one of: {', '.join(available_judges())}")
    if kind == POLICY_JUDGE and not has_policies:
        problems.append("the policy_answer judge grades against the team's policies: add 'policies: <file>'")
    if not isinstance(raw.get("options", {}), dict):
        problems.append("'judge.options' must be a block of settings")

    paths = {}
    for key in ("rubric", "labels"):
        if raw.get(key) is not None:
            paths[key] = (folder / raw[key]).resolve()
            if not paths[key].is_file():
                problems.append(f"judge {key} file not found: {paths[key]}")
    results = (folder / raw.get("results", DEFAULT_RESULTS_FILE)).resolve()
    recorded = (folder / raw["recorded"]).resolve() if raw.get("recorded") else None
    if problems:
        return None, problems
    return JudgeSettings(kind=kind, rubric=paths.get("rubric"), rubric_version=raw.get("rubric_version"),
                         model=raw.get("model"), labels=paths.get("labels"), results=results, recorded=recorded,
                         options=dict(raw.get("options") or {})), []
