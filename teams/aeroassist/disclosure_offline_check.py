"""Before agent v8 adds an AI disclosure in code, check offline that the sentence breaks nothing.

v8 puts one fixed sentence at the start of a conversation's first reply, unless the answer already says it
is an AI (read by the ai_disclosure check's own words). This tool adds the sentence to stored answers the
same way and grades each answer twice, with and without it, using team.yaml's checks except the judge
(a model call) and ai_disclosure (which the sentence is meant to change). Any check whose result changes
is named, so it is fixed before a paid session. No API call.

    from disclosure_offline_check import compare_with_disclosure
    report = compare_with_disclosure(Session(folder, dry_run=True), "v7")
    report["answers"], report["changed"]     # changed: [(case, try, check, without, with), ...]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from aiquality.checks.disclosure_check import AiDisclosure  # noqa: E402
from aiquality.evaluation import evaluate_runs  # noqa: E402
from aiquality.runner import CaseRun  # noqa: E402

import live_session as ls  # noqa: E402

DISCLOSURE_SENTENCE = "I'm AeroAssist, Meridian Airways' AI assistant."
LEFT_OUT = (ls.JUDGE_CHECK, "ai_disclosure")


def with_disclosure(answer_text: str, case, reader: AiDisclosure) -> str:
    """The answer as v8 would send it: the sentence first on a first reply that doesn't already say it is an AI."""
    if case.conversation_history or reader.says_it_is_an_ai(answer_text):
        return answer_text
    return f"{DISCLOSURE_SENTENCE}\n\n{answer_text}"


def compare_with_disclosure(session, version: str, records=None) -> dict:
    """Grade the version's stored answers with and without the sentence; name every check that changes."""
    records = [r for r in (records if records is not None else ls.records_for(session, version))
               if r.get("answer_text") is not None]
    disclosure = session.config.checks.get("ai_disclosure")
    reader = AiDisclosure(**(disclosure.options if disclosure else {}))
    cases = {case.id: case for case in session.cases}
    settings = {name: s for name, s in session.config.checks.items() if name not in LEFT_OUT}
    changed = []
    by_try: dict = {}
    for record in records:
        by_try.setdefault(record["try"], []).append(record)
    for try_number, group in sorted(by_try.items()):       # one try at a time, so counterfactual groups stay whole
        plain = [CaseRun(cases[r["case_id"]], ls._response(r), r["error"]) for r in group]
        added = []
        for r in group:
            response = ls._response(r)
            response.answer_text = with_disclosure(response.answer_text, cases[r["case_id"]], reader)
            added.append(CaseRun(cases[r["case_id"]], response, r["error"]))
        before = _statuses(evaluate_runs(plain, settings, default_client=session.config.client))
        after = _statuses(evaluate_runs(added, settings, default_client=session.config.client))
        for key in sorted(before):
            if before[key] != after.get(key):
                changed.append((key[0], try_number, key[1], before[key], after.get(key)))
    return {"version": version, "answers": len(records), "sentence": DISCLOSURE_SENTENCE, "changed": changed}


def _statuses(evaluation) -> dict:
    return {(r.case_id, r.check_name): r.status.value for o in evaluation.outcomes for r in o.results}
