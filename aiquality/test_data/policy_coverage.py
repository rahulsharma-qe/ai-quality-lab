"""Coverage per policy: how many golden cases test each policy in the team's policies file.

A policy is a level-2 heading "## <ID> <separator> <title>": the ID is the first word, the separator
is an em dash, an en dash, a hyphen or a colon, and the title keeps any colons of its own
("## P2 — Baggage: Cabin" is policy P2, "Baggage: Cabin"). Other lines are ignored, so a policies file
written as prose is still valid: the judge reads it as plain text, and coverage just can't be counted.

A case tests a policy when the policy's id is in its expected_sources. The coverage report counts
cases and high-priority cases per policy and names the policies no case tests; it never blocks.
`check_policy_ids` is shared with lint: a repeated id, or an expected_sources entry that matches no
heading, is reported as a warning, never a failure. expected_sources names the documents a good answer
needs, which are the policy headings for a team like AeroAssist but may be knowledge-base ids or file
names for another team, so a mismatch is a question for the team, not proof of a mistake.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from aiquality.test_data.golden_case import GoldenSet

HEADING_FORMAT = "'## <ID> — <title>'"
_HEADING = re.compile(r"^##[ \t]+(\S+?)(?::[ \t]+|[ \t]+[—–:-][ \t]+)(.+?)\s*$")


@dataclass(frozen=True)
class Policy:
    id: str
    title: str


@dataclass
class PoliciesFile:
    path: Path
    policies: list[Policy]
    duplicate_ids: list[str]

    @property
    def ids(self) -> set[str]:
        return {p.id for p in self.policies}


@dataclass
class PolicyCoverageRow:
    policy: Policy
    case_ids: list[str] = field(default_factory=list)
    high_priority: int = 0


@dataclass
class PolicyCoverage:
    policies_file: PoliciesFile
    rows: list[PolicyCoverageRow]
    cases_with_sources: int
    warnings: list[str]


def read_policies(path: Path) -> PoliciesFile:
    """The id headings in a team's policies file, in file order; a file with none gives an empty list."""
    policies, duplicates = [], []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        match = _HEADING.match(line)
        if match is None:
            continue
        policy = Policy(id=match.group(1), title=match.group(2))
        if any(p.id == policy.id for p in policies):
            duplicates.append(policy.id)
            continue
        policies.append(policy)
    return PoliciesFile(path=Path(path), policies=policies, duplicate_ids=duplicates)


def uses_expected_sources(golden_set: GoldenSet) -> bool:
    return any(case.expected_sources for case in golden_set.cases)


def check_policy_ids(policies_file: PoliciesFile, golden_set: GoldenSet) -> list[str]:
    """Warnings about the policies file against the golden set's expected_sources: one per repeated id,
    and one per unknown id, naming every case that uses it. A prose file with no id headings gets a
    warning only when the golden set uses expected_sources."""
    name = policies_file.path.name
    uses_sources = uses_expected_sources(golden_set)
    if not policies_file.policies:
        return [f"{name} has no {HEADING_FORMAT} headings, so the expected_sources ids can't be checked"] \
            if uses_sources else []
    warnings = [f"{name}: duplicate policy id '{policy_id}'; each {HEADING_FORMAT} heading needs its own id"
                for policy_id in dict.fromkeys(policies_file.duplicate_ids)]
    if not uses_sources:
        return warnings
    unknown: dict[str, list[str]] = {}
    for case in golden_set.cases:
        for source in dict.fromkeys(case.expected_sources):
            if source not in policies_file.ids:
                unknown.setdefault(source, []).append(case.id)
    warnings += [f"'{source}' in expected_sources matches no {HEADING_FORMAT} heading in {name}; named by "
                 f"{', '.join(case_ids)}" for source, case_ids in unknown.items()]
    return warnings


def count_policy_coverage(policies_file: PoliciesFile, golden_set: GoldenSet) -> PolicyCoverage:
    rows = {p.id: PolicyCoverageRow(policy=p) for p in policies_file.policies}
    for case in golden_set.cases:
        for source in dict.fromkeys(case.expected_sources):
            row = rows.get(source)
            if row is not None:
                row.case_ids.append(case.id)
                row.high_priority += case.priority == "high"
    return PolicyCoverage(policies_file=policies_file, rows=list(rows.values()),
                          cases_with_sources=sum(1 for c in golden_set.cases if c.expected_sources),
                          warnings=check_policy_ids(policies_file, golden_set))


def render_policy_coverage(coverage: PolicyCoverage) -> str:
    if not coverage.policies_file.policies:
        return f"{coverage.policies_file.path.name} has no {HEADING_FORMAT} headings; coverage can't be counted"
    if coverage.cases_with_sources == 0:
        return "no golden case lists expected_sources; coverage can't be counted"
    lines = [f"{'policy':<8} {'cases':>5} {'high':>5}  case ids", "-" * 78]
    for row in coverage.rows:
        ids = ", ".join(row.case_ids) if row.case_ids else "not covered"
        lines.append(f"{row.policy.id:<8} {len(row.case_ids):>5} {row.high_priority:>5}  {ids}")
    uncovered = [row.policy.id for row in coverage.rows if not row.case_ids]
    lines.append("")
    lines.append(f"not covered: {', '.join(uncovered)}" if uncovered else "every policy is tested by at least one case")
    lines += [f"warning: {warning}" for warning in coverage.warnings]
    return "\n".join(lines)
