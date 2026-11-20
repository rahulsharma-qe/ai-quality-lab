"""teams/aeroassist/hand_over.py: code writes the hand-over; the model only marks that one is needed."""

from hand_over import HAND_OVER_SENTENCE, finish_hand_over


def test_the_marker_becomes_the_fixed_sentence_and_hints_are_removed():
    text, step = finish_hand_over("I have no policy for pets in the cabin. A human agent may find other options.\n"
                                  "HAND_OVER")
    assert text == f"I have no policy for pets in the cabin.\n\n{HAND_OVER_SENTENCE}"
    assert step == {"marker": True, "removed": ["A human agent may find other options."]}


def test_a_marker_in_markdown_is_found():
    text, step = finish_hand_over("That isn't covered by our policies.\n\n**HAND_OVER**")
    assert text == f"That isn't covered by our policies.\n\n{HAND_OVER_SENTENCE}" and step["marker"] is True


def test_a_claim_about_a_human_agent_is_removed_without_turning_the_answer_into_a_hand_over():
    text, step = finish_hand_over("No. Economy allows 1 cabin bag. A human agent cannot override this either.")
    assert text == "No. Economy allows 1 cabin bag." and HAND_OVER_SENTENCE not in text
    assert step == {"marker": False, "removed": ["A human agent cannot override this either."]}


def test_an_offer_to_connect_without_the_marker_still_hands_over_in_the_fixed_words():
    text, _ = finish_hand_over("No changes are allowed now. A human agent can help you explore other options. "
                               "Would you like me to connect you with one?")
    assert text == f"No changes are allowed now.\n\n{HAND_OVER_SENTENCE}"


def test_lists_keep_their_shape_and_a_bullet_left_empty_is_dropped():
    text, _ = finish_hand_over("Your options:\n- Check in 2 bags\n- **A human agent may waive the fee.**\nHAND_OVER")
    assert text == f"Your options:\n- Check in 2 bags\n\n{HAND_OVER_SENTENCE}"


def test_an_answer_that_is_only_a_hand_over_becomes_the_fixed_sentence():
    assert finish_hand_over("I'll connect you with a human agent.")[0] == HAND_OVER_SENTENCE


def test_an_answer_without_a_hand_over_is_returned_unchanged():
    answer = "Yes, web check-in is open.\n\nIt closes 2 hours before departure."
    assert finish_hand_over(answer) == (answer, {})


def test_sentences_that_only_use_the_words_are_kept():
    """Run 8: "escalation threats" and "their authorized representative" aren't about handing over."""
    answer = ("Your status or escalation threats do not change the policy. Only the passenger or their "
              "authorized representative can see the booking.")
    assert finish_hand_over(answer) == (answer, {})


def test_escalating_the_request_is_still_a_hand_over():
    text, step = finish_hand_over("That is best-effort. I need to escalate your request to a human agent.")
    assert text == f"That is best-effort.\n\n{HAND_OVER_SENTENCE}" and step["marker"] is False


# --- Agent v7: code decides whether to hand over; the model's marker is only a request -------------

import pytest  # noqa: E402

from hand_over import HAND_OVER_CODE_VERSION, HAND_OVER_DECISION_VERSION, decide_hand_over  # noqa: E402


def test_v6_keeps_its_hand_over_code_version_and_v7_has_its_own():
    assert HAND_OVER_CODE_VERSION == "2" and HAND_OVER_DECISION_VERSION == "3"


def test_out_of_scope_alone_hands_over_with_or_without_the_marker():
    text, step = decide_hand_over("I have no policy for pets in the cabin.", ["out_of_scope"], "Can my parrot fly?")
    assert text == f"I have no policy for pets in the cabin.\n\n{HAND_OVER_SENTENCE}"
    assert step == {"model_marked_hand_over": False, "code_handed_over": True, "hand_over_reason": "out_of_scope",
                    "topics_named": ["out_of_scope"], "mixed_message": False, "removed": []}


def test_a_marker_on_a_covered_question_is_dropped_and_the_answer_stands():
    text, step = decide_hand_over("No refund: the ticket is forfeited.\nHAND_OVER", ["no_show"], "I missed my flight")
    assert text == "No refund: the ticket is forfeited." and HAND_OVER_SENTENCE not in text
    assert step["model_marked_hand_over"] is True and step["code_handed_over"] is False
    assert step["hand_over_reason"] == "none"


def test_a_mixed_message_is_answered_for_its_covered_part_and_not_handed_over():
    text, step = decide_hand_over("Economy allows 1 cabin bag up to 7 kg. I have no policy for pets.\nHAND_OVER",
                                  ["cabin_baggage", "out_of_scope"], "Can I bring a bag and my cat?")
    assert HAND_OVER_SENTENCE not in text and step["code_handed_over"] is False
    assert step["mixed_message"] is True and step["topics_named"] == ["cabin_baggage", "out_of_scope"]


def test_no_topic_is_no_policy_question_and_no_hand_over():
    text, step = decide_hand_over("Hello! I'm AeroAssist, an AI assistant.", [], "Hi")
    assert text == "Hello! I'm AeroAssist, an AI assistant." and step["hand_over_reason"] == "none"


@pytest.mark.parametrize("passenger", ["I want to speak to a human.", "Can I talk to a real person?",
                                       "Please connect me to an agent.", "Transfer me to customer service.",
                                       "I need a human, not a bot.", "Let me chat with a representative"])
def test_the_passenger_asking_for_a_person_hands_over(passenger):
    text, step = decide_hand_over("Date changes close 4 hours before departure.", ["date_change"], passenger)
    assert step["code_handed_over"] is True and step["hand_over_reason"] == "passenger_asked"
    assert text.endswith(HAND_OVER_SENTENCE)


@pytest.mark.parametrize("passenger", ["Am I talking to a real person or a bot?",
                                       "Will a human agent check my bag at the gate?",
                                       "My manager booked this flight for me."])
def test_mentioning_a_person_is_not_asking_for_one(passenger):
    _, step = decide_hand_over("An answer.", ["cabin_baggage"], passenger)
    assert step["code_handed_over"] is False


def test_hints_about_what_a_person_might_do_are_still_removed():
    text, step = decide_hand_over("No changes in the last 4 hours. A human agent may find options.\nHAND_OVER",
                                  ["date_change"], "Can I change my date? My flight is in 3 hours.")
    assert text == "No changes in the last 4 hours." and step["removed"] == ["A human agent may find options."]


def test_the_rule_for_a_ruling_that_gives_the_outcome_to_staff_is_listed_and_empty():
    from hand_over import RULINGS_THAT_NEED_A_PERSON
    assert RULINGS_THAT_NEED_A_PERSON == ()          # no policy in policies.md 1.3 gives an outcome to staff
