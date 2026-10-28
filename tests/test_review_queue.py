"""The human review queue: what lands in it, what stays out, and the review command."""

import json
from datetime import date

from aiquality import TeamConfig
from aiquality.cli import EXIT_OK, main
from aiquality.commands import gate_team, record_judge_verdicts
from aiquality.models import ChatModel
from aiquality.review import build_review_queue, render_review_queue

from conftest import BASE_CONFIG, write_team

TODAY = date(2026, 10, 15)
ROWS = ("id,input,category,priority,must_include,must_not_include\n"
        "C1,What are your opening hours?,happy,high,9 am,24/7\n"
        "C2,Is my refund approved?,edge,medium,human,approved\n"
        "C3,Can I return an item?,edge,high,30 days,\n"
        "C4,Do you deliver on Sundays?,out_of_scope,low,human,\n")
AGENT = '''
def answer(question, conversation=None):
    if "hours" in question:
        return "We open at nine in the morning and close at six."           # right, in other words
    if "refund" in question:
        return "Your refund is not approved yet; a human will review it."   # "not approved"
    if "return" in question:
        return "Returns within 30 days, no receipt needed."                 # words fine, meaning wrong
    return "No idea."                                                       # plainly wrong
'''


class JudgeFailsWaivers(ChatModel):
    def __init__(self):
        super().__init__("fake-judge")

    def complete(self, system, user):
        answer = user.split("ASSISTANT ANSWER:")[1]
        failed = "no receipt" in answer or "No idea" in answer
        return json.dumps({"reason": "scripted", "verdict": "FAIL" if failed else "PASS"})


def team(tmp_path, with_judge=True, accepted=None):
    config = dict(BASE_CONFIG, checks={"required_phrases": {"threshold": 0.9},
                                       "forbidden_phrases": {"threshold": 1.0}},
                  accepted_findings=accepted or [])
    if with_judge:
        config.update(policies="policies.md", judge={"kind": "policy_answer", "recorded": "verdicts.jsonl"})
        config["checks"]["answer_judge"] = {"threshold": 1.0}
    folder = write_team(tmp_path / "team", config, ROWS, AGENT)
    (folder / "policies.md").write_text("Returns within 30 days with a receipt.")
    loaded = TeamConfig.load(folder, today=TODAY)
    if with_judge:
        record_judge_verdicts(loaded, chat=JudgeFailsWaivers())
    return loaded


def queue(config, tmp_path):
    record, _ = gate_team(config, output_dir=tmp_path / "runs", print_reports=False, today=TODAY)
    return {(i.case_id, i.check): i for i in build_review_queue(record, today=TODAY)}


def test_disagreements_and_hidden_errors_land_in_the_queue(tmp_path):
    items = queue(team(tmp_path), tmp_path)
    assert items[("C1", "required_phrases")].kind == "check_vs_judge"        # a likely false alarm
    assert items[("C2", "forbidden_phrases")].kind == "check_vs_judge"
    assert items[("C3", "answer_judge")].kind == "judge_only"                # a hidden error the words missed
    assert ("C4", "required_phrases") not in items                          # check and judge agree: no person needed
    snippet = items[("C1", "required_phrases")].accept_snippet
    assert "case: C1" in snippet and "check: required_phrases" in snippet and "expires: 14-11-2026" in snippet
    assert items[("C3", "answer_judge")].accept_snippet is None             # a possible error is never pre-accepted


def test_without_a_judge_only_self_doubting_checks_are_queued(tmp_path):
    items = queue(team(tmp_path, with_judge=False), tmp_path)
    assert list(items) == [("C2", "forbidden_phrases")] and items[("C2", "forbidden_phrases")].kind == \
        "possible_false_alarm"


def test_accepted_findings_leave_the_queue_until_they_are_about_to_expire(tmp_path):
    accepted = [{"case": "C2", "check": "forbidden_phrases", "reason": "negation", "approved_by": "qa-lead",
                 "expires": "2026-10-20"}]
    items = queue(team(tmp_path, with_judge=False, accepted=accepted), tmp_path)
    assert list(items) == [("C2", "forbidden_phrases")]
    assert items[("C2", "forbidden_phrases")].kind == "acceptance_expiring"


def test_review_command_reads_the_latest_run(tmp_path, capsys):
    config = team(tmp_path)
    gate_team(config, output_dir=tmp_path / "runs", print_reports=False, today=TODAY)
    assert main(["review", "--team", str(config.folder), "--output-dir", str(tmp_path / "runs")]) == EXIT_OK
    out = capsys.readouterr().out
    assert "item(s) need a person" in out and "C3 · answer_judge · judge_only" in out
    assert (tmp_path / "runs" / "test_team-review-queue.jsonl").is_file()
    assert render_review_queue([], "x") == "review queue · team x: nothing needs a person"
