"""The offline check before agent v8's disclosure step: adding the fixed sentence to a stored answer must not
change the decision check or any rule check (the ai_disclosure check is meant to change, and is left out)."""

import json

import live_session as ls
from disclosure_offline_check import DISCLOSURE_SENTENCE, compare_with_disclosure, with_disclosure

from aiquality.checks.disclosure_check import AiDisclosure
from aiquality.test_data import GoldenCase

READER = AiDisclosure()


def case(**fields):
    return GoldenCase.from_dict({"id": "X1", "input": "Hi", "category": "happy", **fields})


def test_the_sentence_is_added_at_the_start_of_a_first_reply():
    assert with_disclosure("Economy allows 15 kg.", case(), READER) == f"{DISCLOSURE_SENTENCE}\n\nEconomy allows 15 kg."


def test_an_answer_that_already_says_it_is_an_ai_is_left_as_it_is():
    assert with_disclosure("I'm an AI assistant. Economy allows 15 kg.", case(), READER) == \
        "I'm an AI assistant. Economy allows 15 kg."


def test_a_reply_after_earlier_turns_is_not_a_first_reply():
    history = [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello."}]
    assert with_disclosure("Economy allows 15 kg.", case(conversation_history=history), READER) == "Economy allows 15 kg."


def test_the_reader_is_the_checks_own():
    assert READER.says_it_is_an_ai("You're chatting with our virtual assistant.") == "virtual assistant"
    assert READER.says_it_is_an_ai("This is our automated support system.") is None


def test_on_the_recorded_answers_the_sentence_changes_no_check_but_ai_disclosure(tmp_path):
    ls.run_session(tmp_path, dry_run=True, log=lambda *_: None)
    session = ls.Session(tmp_path, dry_run=True, log=lambda *_: None)
    report = compare_with_disclosure(session, "v7")
    assert report["answers"] > 0 and report["changed"] == []


def test_a_change_is_named_with_the_case_try_check_and_both_results(tmp_path):
    ls.run_session(tmp_path, dry_run=True, log=lambda *_: None)
    session = ls.Session(tmp_path, dry_run=True, log=lambda *_: None)
    record = next(r for r in ls.records_for(session, "v7") if r["case_id"] == "GD46")
    record["answer_text"] = "Line one.\nLine two.\nLine three.\nNo, you can't check in online."
    report = compare_with_disclosure(session, "v7", records=[record])
    assert report["changed"] and report["changed"][0][:3] == ("GD46", record["try"], "decision")
