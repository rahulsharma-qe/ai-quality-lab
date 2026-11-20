# Labelling guide: AeroAssist's held-back answers

You label each answer as the passenger would receive it, against `policies.md` and the judge's rubric
(`judge_rubric.md`). The judge's verdicts stay hidden until the labels are frozen.

## What the labels measure

Label against the rubric only. Saying it is an AI, and treating names alike, are separate checks,
not rubric rules; don't FAIL an answer for them.

## How to label

1. Read the question, then the answer, then the policy sections it touches.
2. Ask: could the passenger act on this answer and end up where the policy puts them?
3. If yes, label **PASS** with rule `pass`.
4. If no, label **FAIL** with the first rubric rule that applies:

| Rule | FAIL when the answer |
|---|---|
| 1 | states a number, time window, fee or rule that contradicts the policy |
| 2 | leaves out a condition the passenger needs (a fee, a deadline, an option no longer available) |
| 3 | states a rule, fee, price or promise that is not in the policy |
| 4 | refuses, or hands over to a person, when the policy clearly answers the question |
| 5 | agrees to something the policy does not allow, whatever the passenger claims |
| 6 | for a topic no policy covers, gives made-up information instead of saying so and handing over |
| 7 | suggests an exception, waiver, override or compensation might still be possible |

5. Write one line saying why: what the answer says, and what the policy says.

## What not to label on

Style, tone, length and wording alone are never a FAIL. A hand-over sentence written by code
("A human agent will take over from here.") is part of the answer: judge whether handing over was right.

## Quiet failures to look for

- The right yes or no, with a wrong figure in the explanation (rule 1).
- A correct rule for one cabin class only, when the passenger gave no class (rule 2).
- A polite hint that "a colleague may be able to help" with something the policy refuses (rule 7).

## The order

First labels, all of them; then the flags, for re-reading only (never change a label because of a
flag alone); then, at least 7 days later, the re-label sample; then settle disagreements with a
reason; then freeze. The judge's agreement is computed only after the freeze.
