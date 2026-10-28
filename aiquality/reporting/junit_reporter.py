"""JUnit XML: CI tools (GitHub Actions, Jenkins, GitLab) show it as a native test view.

One test case per golden or attack case and check. FAIL -> failure, ERROR -> error,
NOT_APPLICABLE and accepted findings -> skipped (with the reason). The gate decision is
one more test case, so a failed gate is visible in the same view.
"""

import xml.etree.ElementTree as ElementTree
from pathlib import Path

from aiquality.reporting.report_data import accepted_pairs
from aiquality.reporting.reporters import Reporter, register_reporter
from aiquality.reporting.run_record import RunRecord
from aiquality.dates import shown_day


@register_reporter("junit_xml")
class JunitXmlReporter(Reporter):
    def write(self, record: RunRecord, output_dir: Path):
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"{record.team}-junit.xml"
        ElementTree.ElementTree(build_junit_tree(record)).write(path, encoding="utf-8", xml_declaration=True)
        return path


def build_junit_tree(record: RunRecord) -> ElementTree.Element:
    accepted = accepted_pairs(record)
    suites = ElementTree.Element("testsuites", name="aiquality")
    suite = ElementTree.SubElement(suites, "testsuite", name=record.team)
    counts = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}

    for outcome in record.outcomes:
        prefix = "attack" if outcome.get("category") == "attack" else "golden"
        for result in outcome["results"]:
            case = ElementTree.SubElement(suite, "testcase", classname=f"{record.team}.{prefix}.{result['check']}",
                                          name=outcome["case_id"])
            counts["tests"] += 1
            key = (outcome["case_id"], result["check"])
            if result["status"] == "FAIL" and key in accepted:
                a = accepted[key]
                ElementTree.SubElement(case, "skipped", message=f"accepted until {shown_day(a['expires'])}: {a['reason']}")
                counts["skipped"] += 1
            elif result["status"] == "FAIL":
                failure = ElementTree.SubElement(case, "failure", message=result["reason"])
                failure.text = result.get("evidence") or ""
                counts["failures"] += 1
            elif result["status"] == "ERROR":
                ElementTree.SubElement(case, "error", message=result["reason"])
                counts["errors"] += 1
            elif result["status"] == "NOT_APPLICABLE":
                ElementTree.SubElement(case, "skipped", message=result["reason"])
                counts["skipped"] += 1

    if record.gate_decision:
        gate_case = ElementTree.SubElement(suite, "testcase", classname=f"{record.team}.gate", name="release_gate")
        counts["tests"] += 1
        if not record.gate_decision["passed"]:
            failure = ElementTree.SubElement(gate_case, "failure", message="release gate failed")
            failure.text = "\n".join(record.gate_decision["failures"])
            counts["failures"] += 1

    for name, value in counts.items():
        suite.set(name, str(value))
    return suites
