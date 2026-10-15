"""Example 11: every report format from one gate run.

console        printed (what you see in a CI log)
html           <team>-report.html: open in a browser, keep as a CI artifact
junit_xml      <team>-junit.xml: CI test views (GitHub Actions, Jenkins, GitLab)
github_summary <team>-summary.md: also appended to the Actions run page inside GitHub Actions
All of them read the same run record, so they always agree.
Run:  python examples/11_generate_all_reports.py
"""

import tempfile
from pathlib import Path

from aiquality import TeamConfig
from aiquality.commands import gate_team, write_reports

output = Path(tempfile.mkdtemp())
config = TeamConfig.load(Path(__file__).parent / "gate_demo" / "regressed_team")
record, _ = gate_team(config, output_dir=output, print_reports=False)

for path in write_reports(record, ["html", "junit_xml", "github_summary"], output):
    print(f"{path.name:<32} {path.stat().st_size:>7} bytes")
print("\nFirst lines of the GitHub summary:\n")
print("\n".join((output / "store_regressed-summary.md").read_text(encoding="utf-8").splitlines()[:6]))
