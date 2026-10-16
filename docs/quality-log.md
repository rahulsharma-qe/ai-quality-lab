# Quality log: what we tested, what we found, what we changed

This is the running record of testing one AI agent with the `aiquality` platform in this
repository. The agent is **AeroAssist**, a support assistant for a fictional airline (Meridian
Airways) that answers passenger questions from eight written policies, or hands over to a person.

How to read it:

- **[Where we are now](#where-we-are-now)**: the current state and every open problem, on one screen.
- **[The runs](#the-runs-oldest-first)**: each test run in order, with what it found and what we changed.
  Read these for the story.
- **[Lessons](#lessons-that-carry-over-to-any-ai-agent)**: what carries over to testing any AI agent.

Every claim points to its evidence: a golden case id (such as GD20), a file in this repository, or
a saved run record you can replay without an API key.

---

## Words used here

| Word | Meaning |
|---|---|
| **Golden set** | The test cases: a passenger question, what a good answer must say, and what it must never say. Written and checked by a person. File: [`golden_dataset.json`](../teams/aeroassist/golden_dataset.json) |
| **P1 to P8** | The agent's eight policies (refunds, baggage, check-in, date changes, no-shows, cancellations, special assistance), in [`policies.md`](../teams/aeroassist/policies.md) |
| **Case id** | A case's name, for example **GD20** ("my flight is in 2 hours, change it to the next flight") |
| **Check** | An automatic test of one answer, scored as a pass rate. **Phrase checks** look for required and forbidden words |
| **Judge** | An AI that reads an answer and decides whether it is correct and grounded in the policies. It can be wrong too, so it is measured against a person's labels before it is trusted |
| **Release gate** | The PASS or FAIL decision: every blocking check must meet its bar |
| **Recorded answers** | The agent's answers, saved once from the live agent and replayed, so tests run without an API key and give the same result every time |
| **Rubric** | The judge's written instructions: what makes an answer fail. File: [`teams/aeroassist/judge_rubric.md`](../teams/aeroassist/judge_rubric.md) |
| **Held-out case** | A case written *after* a fix was frozen, so it tests whether the fix works on something it was not tuned for |
| **False alarm** | A check fails a correct answer (for example, "not approved" matching the forbidden word "approved") |
| **Hidden error** | A check passes a wrong answer, because the answer contains the right words but means the wrong thing |
| **Accepted finding** | A false alarm a person has reviewed and accepted, with a reason and an expiry date |
| **Review queue** | After each run, the list of findings a person should look at, and why |

---

## Where we are now

*Updated 15 October 2026.*

| | |
|---|---|
| Agent | v2 rules, 3 policies retrieved per question, earlier conversation turns used, policies version 1.2 |
| Golden set | version 1.8, 40 cases (including 4 held-out cases) |
| Phrase checks | required phrases 92%, forbidden phrases 88% (100% after accepted false alarms); attacks resisted 16 of 16 |
| Judge | grades every answer, but **advisory**: its version has not qualified against a person's labels (it leaves only 62% of good answers alone; the bar is 80%) |
| Release gate on phrase checks | **PASS**, with a warning: 5 of 40 cases rely on an accepted finding |
| Continuous integration (CI) | the AeroAssist gate is reported but **not blocking**, on purpose: the phrase checks pass while the judge and a person found real errors they miss (below) |

### Open problems

| Case | What is wrong, in plain words | Found by | Since | Next step |
|---|---|---|---|---|
| GD18 | A passenger asks to change a flight **exactly** 4 hours before departure. The policy says exactly 4 hours still qualifies; the agent refuses | Judge, confirmed by reading the answer | Already wrong in v2; the phrase checks passed it | Boundary rule for the agent |
| GD30 | A wheelchair request **exactly** 48 hours before departure is told it is "not guaranteed"; the policy says at least 48 hours qualifies | Judge, confirmed | New with policies 1.2 | Boundary rule; say in the policy that 48 hours is inclusive |
| GD13 | A passenger flying tomorrow is told web check-in is **closed**, when it opens 48 hours before departure | Judge, confirmed | New with policies 1.2 (v2 answered correctly) | Agent fix, then a phrase check so it can't come back |
| GD06 | Three bags the passenger wants to **check in** are treated as cabin bags | Judge, confirmed | Already wrong in v2 | Agent fix |
| GD38 (held-out) | Asked about a missed connection on another airline, the agent invents "a claim … for damages" instead of a plain hand-over | Judge, confirmed | Policies 1.2 recording | Agent fix |
| GD24 | A late passenger asks to rebook at the same price; the agent never says that missing the flight means rebooking at the full current fare | Phrase check | Policies 1.2 recording | Agent fix |
| About 11 answers | The hand-over hints that an exception might still be possible ("they can discuss options", "may be able to arrange it"). The reviewer's own written standard counts that as a failure | Judge (rubric rule 7) | Agent v2's hand-over wording | Agent fix: hand over plainly, promise nothing |
| GD01, GD09, GD35, GD10 | Smaller invented details ("refund initiated immediately", "1 bag", "fare difference" for a no-show, an opening "Not quite") | Judge | Mixed | A person to confirm, then fix |

### Accepted findings (expire 14 November 2026)

Each was read by a person: the answer is right, the phrase check is wrong.

| Case | Check | Why it is a false alarm |
|---|---|---|
| GD03 | required phrases | Refuses in other words ("I can't approve that request… VIP status doesn't change the policy") |
| GD16 | required phrases | Says web check-in "closes 2 hours before departure" and "you're well past that deadline" instead of "closed" |
| GD21 | forbidden phrases | Mentions a full refund only as the correct condition (booked within the last 24 hours) |
| GD31 | forbidden phrases | "not guaranteed" matches the forbidden word "guaranteed" |
| GD36 | forbidden phrases | "there is no waived change fee" matches the forbidden "change fee" |

---

## The runs, oldest first

### Before the platform: two findings from the first scripts

**The agent repeated a poisoned fact.** The first attack run found 0 breaches in 10, which we read
as a sign the attacks were too weak, not that the agent was safe. Stronger attacks still failed to
make it ignore its rules, but changing one number in a retrieved policy (refund window 24 hours to
30 days) made it promise a refund the passenger wasn't due. An agent that trusts its documents
repeats a poisoned document. Fix: the refund decision moved into code; the model only words it.
Details: [README, "The headline finding"](../README.md#the-headline-finding-the-story-this-repo-tells).

**The judge had to be checked first.** Before trusting an AI judge, we measured it against 30
answers a person had labelled. On the held-back half it caught every real failure (7 of 7) but
passed only 5 of 8 good answers, so it was not qualified and stays advisory. Details:
[README, "The second finding"](../README.md#the-second-finding-check-the-examiner).

### Run 1: the first platform run (golden set 1.1 to 1.2)

**Question.** What do the platform's phrase checks find on the real agent?

**What we ran.** 36 golden cases, answers recorded once from the live agent and replayed.

**What we found.** 11 findings. Reading every answer sorted them into:

- **3 real agent errors.** A 5-day-old booking was answered with the no-show rule instead of the
  24-hour refund rule (GD03); a date change was offered 2 hours before departure when the cut-off
  is 4 hours (GD20); a request for a personal medical attendant was treated as standard special
  assistance instead of being handed over (GD32).
- **1 judgement call** on how 40 kg splits across cabin and check-in bags (GD10).
- **4 phrases too narrow**: correct answers used other words ("escalate" for "connect").
- **1 bug in the checker**: "2 hour" didn't match "2 hours".
- **1 negation false alarm**: "you don't need to pay extra" matched the forbidden "pay extra".
- **1 timing artifact**: loading the model was counted as the first answer's time.

**What we changed.** Equivalent wording accepted with `OR` (golden 1.2); simple plurals count; agents
load models before timing starts. Phrases tied to the real errors were left alone.

**What we learned.** Phrase checks are a fast first filter, but on their own they both miss and
over-report.

### Run 2: attacks and the release gate (golden set 1.4)

**Question.** Can the agent be talked into breaking its policies, and does the gate fail for the
right reasons?

**What we ran.** 36 golden cases plus 16 attack cases (five kinds of attack, three forbidden
goals: a refund, a fee waiver, a free upgrade).

**What we found.** All 16 attacks were resisted. Required phrases passed at 89% against an 85%
bar, so **the average alone would have passed**, while high-priority cases GD03, GD20 and GD27 failed.
Three correct answers hit forbidden words, two of them right after "not".

**What we changed.** A **priority bar**: every high-priority case must pass every blocking check,
whatever the average. **Accepted findings**: a person can accept a reviewed false alarm, with a
reason and an expiry of at most 90 days.

**What we learned.** An average can hide a critical failure. And the multi-turn attack wasn't really
multi-turn, because the agent never received the earlier turns.

### Run 3: one quality loop, v1 to v2 (golden set 1.5)

**Question.** Can we fix the real errors with general rules, without breaking anything else?

**What we found first (diagnosis).** A new check, `expected_sources`, looks only at which policies
the agent retrieved. It showed the agent found the needed policy in 31 of 33 cases; GD03 and GD20
never got it, so those were **retrieval misses**, not only reasoning errors. GD27 turned out to be
a **gap in the policy**: it never said rebooking stays in the same cabin class, so a correct agent
couldn't say it.

**What we changed.**

- Policy 1.1 states the same cabin class (P7).
- Agent v2: 3 policies retrieved instead of 2, earlier conversation turns used, and five general
  rules, written for kinds of error, never for one case (a test fails if a rule mentions a golden case).
- Three **held-out cases** (GD37 to GD39, one multi-turn) written after v2 was frozen.
- Both versions recorded in one session with the same settings, then compared case by case with
  `aiquality compare` ([history](../teams/aeroassist/history/)).

**What we found after.** Retrieval 94% to 100%; no case newly failing; all three held-out cases
passed. GD20 was still wrong ("you're within the 4-hour window, so rescheduling is allowed", with the
flight 2 hours away). Three correct answers failed on wording (GD03, GD16, GD21), so 5 of 39 cases
now relied on an accepted finding, and the 10% warning that should have said so was silent: it
counted attack cases too. Fixed.

**What we learned.** Diagnose by layer before fixing. Prove a fix on cases it never saw, and compare
case by case: an average can rise while a case that used to pass breaks.

### Run 4: a clearer policy, and a judge in the platform (golden set 1.7 to 1.8)

**Question.** GD20's policy said "allowed up to 4 hours before departure". A person reading it also
took it to mean "allowed within the last 4 hours". Is the agent wrong, or the sentence?

**What we changed first.**

- Policy 1.2 says it one way only: changes can be made until 4 hours before departure, and none in
  the last 4 hours. The agent's prompt did not change.
- Held-out **GD40** asks for a change 6 hours before departure, which must be allowed, so an agent
  that now refuses every change is caught.
- The judge joined the platform: it grades every answer against the policies, with its own validation
  status; while not qualified it reports but cannot block, and its findings feed the review queue.

**What we found.**

- **GD20 fixed and GD40 passes**: the clearer sentence did what prompt rules had not.
- Four "new failures" from the phrase checks: three were **echoes**, where a correct refusal repeated
  the passenger's request ("Requesting 100 kg of free baggage is outside this policy") and matched a
  forbidden word taken from that request (GD11, GD19, GD24), and one was a "not" false alarm (GD36).
  GD24 also has a real gap: it never mentions the full current fare.
- **The judge passed only 15 of 40 answers.** Read one by one, its findings split into real errors
  the phrase checks had passed (GD13, GD18, GD30, GD06, GD38: see [Open problems](#open-problems)),
  hand-overs that hint at exceptions, which break the reviewer's own standard, and a few to confirm.
- **Changing one policy changed answers to other questions.** GD13 (web check-in) and GD30 (wheelchair
  at exactly 48 hours) were answered correctly by v2 and wrongly after the P5 sentence changed. The
  phrase checks passed both times; only the judge noticed.

**What we changed after.**

- A **golden-set lint** warns when a forbidden phrase is in the passenger's own words. It flagged five
  cases, including the cause of GD25's long-running false alarm ("do I need to pay extra").
- Golden 1.8 writes those phrases as **completed actions** ("100 kg is approved", not "100").
- GD36's negation false alarm accepted again until 14 November.

**What we learned.** With the false alarms gone, the phrase-check gate **passes**, while the judge and a
person have found real high-priority errors. A gate is only as good as its checks, so the AeroAssist
gate stays non-blocking until those errors are fixed or the judge qualifies.

---

## Lessons that carry over to any AI agent

1. **A clean result is a warning.** Zero breaches in the first attack run meant the attacks were too weak.
2. **Keep money and limit decisions out of the model.** Code decides; the model words the decision.
3. **Check the examiner.** An AI judge earns trust per version, with two numbers on answers a person
   labelled: real failures caught, and good answers left alone, measured on a held-back half.
4. **An average hides a critical failure.** Put a bar on the cases that matter most.
5. **Phrase checks are cheap and strong for facts and numbers, and blind to meaning.** They can't read
   "not" or other words for the same thing. Never forbid the passenger's own words; write the completed
   action ("100 kg is approved").
6. **A passing gate is not proof of quality.** Our phrase gate passed while real errors were in the answers.
   Grade in layers: code checks on every change, a validated judge for meaning, a person on disagreements.
7. **Diagnose by layer before fixing:** retrieval, reasoning, test data, or the policy itself.
8. **Fix kinds of error, not cases**, then prove it on held-out cases and compare case by case.
9. **If a policy reads two ways, fix the policy.** The agent and a person misread the same sentence.
10. **Exceptions are owned and expire.** Accepted findings carry a reason, an approver and a date, and
    too many of them is a signal that a check has reached its limit.
11. **Compare fairly:** the same session, the same settings. Otherwise a difference may be chance.
12. **The same code with new knowledge is a new agent.** The agent's version includes its policies' version.
13. **Boundaries are where agents fail.** "Exactly 4 hours" and "exactly 48 hours" are still open (GD18, GD30).
14. **Any change to an agent's knowledge needs the whole set re-run, graded for meaning.** Rewording one
    policy broke answers about two others (GD13, GD30).

---

## Adding an entry

After a run worth recording: update **Where we are now** (the status table, open problems and accepted
findings), then add a run below the last one with the same five parts: question, what we ran, what we
found, what we changed, what we learned. Link the evidence; keep it in plain words.
