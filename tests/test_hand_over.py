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
