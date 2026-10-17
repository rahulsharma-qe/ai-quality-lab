# Quality log: what we tested, what we found, what we changed

This is the running record of testing one AI agent with the `aiquality` platform in this
repository. The agent is **AeroAssist**, a support assistant for a fictional airline (Meridian
Airways) that answers passenger questions from eight written policies, or hands over to a person.

How to read it:

- **[Story so far](#story-so-far)**: one line per run, and what each run led to.
- **[Where we are now](#where-we-are-now)**: the current state and every open problem, on one screen.
- **[The runs](#the-runs-oldest-first)**: each test run in order, with what it found and what we changed.
  Read these for the story.
- **[Lessons](#lessons-that-carry-over-to-any-ai-agent)**: what carries over to testing any AI agent.

Every claim points to its evidence: a golden case id (such as GD20), a file in this repository, or
a saved run record you can replay without an API key.

---

## Story so far

Terms such as *held-out case* and *judge* are explained in [Words used here](#words-used-here).

| Run | Question | What we found | What it led to |
|---|---|---|---|
| [1](#run-1-the-first-platform-run-golden-set-11-to-12) | What do phrase checks find on the real agent? | 11 findings, 3 of them real agent errors | Equivalent wording accepted; a plural fix in the matcher and a timing fix in the runner |
| [2](#run-2-attacks-and-the-release-gate-golden-set-14) | Can the agent be talked into breaking its policies? | 16 of 16 attacks resisted, but an 89% average hid three failing high-priority cases | A bar for high-priority cases; accepted findings that expire |
| [3](#run-3-one-quality-loop-v1-to-v2-golden-set-15) | Can general fixes work without breaking anything? | Retrieval 94% to 100%, nothing newly failing, every held-out case passed | Case-by-case comparison and held-out cases as standard practice |
| [4](#run-4-a-clearer-policy-and-a-judge-in-the-platform-golden-set-17-to-18) | Was the agent wrong, or the policy sentence? | The reworded sentence fixed GD20; the new judge found errors the phrase checks passed | A golden-set lint; the AeroAssist gate kept non-blocking |
| [5](#run-5-general-rules-for-the-kinds-of-error-run-4-found-golden-set-19-to-110) | Can prompt rules fix whole kinds of error? | Partly: hinted exceptions halved, but time-window answers broke, and results change from try to try | Agent v3 kept as the default; next, limits are decided in code |

Next: Run 6 tests whether working out time windows and fees in code, with the model only wording
the result, fixes the time-window errors that prompt rules could not.

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
| **Repeat check** | The same cases asked again, to see how often a result changes on its own |

---

## Where we are now

*Updated 17 October 2026, after Run 5.*

| | |
|---|---|
| Agent | v3: v2's settings plus nine general rules for the kinds of error Run 4 found; policies version 1.3 |
| Golden set | version 1.10, 45 cases (9 of them held-out) |
| Phrase checks | required phrases 89% (91% after an accepted false alarm), forbidden phrases 97% (100% after one); attacks resisted 16 of 16 |
| Judge | passes 24 of 45 answers (53%), but **advisory**: its version has not qualified against a person's labels (it leaves only 62% of good answers alone; the bar is 80%) |
| Release gate on phrase checks | **FAIL**: high-priority GD18 and GD40, both wrong about a time window |
| Repeat check | the judge's verdict changed at least once in 4 tries for 13 of the 24 cases asked again, so one recording can't tell a change of 2 or 3 cases from noise |
| Continuous integration (CI) | the AeroAssist gate is reported but **not blocking**: it fails, and the judge finds errors the phrase checks miss |

### Open problems

| Case | What is wrong, in plain words | Found by | Since | Next step |
|---|---|---|---|---|
| GD40, GD18 (high) | A date change **6 hours** before departure is refused ("you're within the final 4-hour window"), and so is one **exactly** 4 hours before. The policy allows both | Phrase checks and judge (GD40 on every try) | GD18 since v2; GD40 since policies 1.3 (v2 too) | Run 6: the time-window decision moves into code; the model only words it |
| GD41 (held-out), GD13 | Web check-in: 30 hours before departure the agent says it is "not yet open"; for a flight tomorrow it says check-in "opened 48 hours ago" | Judge. GD41's phrase checks miss "not yet open" | GD41: v3. GD13: since policies 1.2, now a different error | Run 6; add "not yet open" to GD41's forbidden phrases |
| GD14 | "My flight is in 2 hours": web check-in closes 2 hours before departure, but the policy doesn't say whether exactly 2 hours is still open | Reading the policy | Since the start | The policy owner decides, as P8 did in policies 1.3 |
| GD22, GD40 | v3 says no policy covers a missed flight (P6 does) or a late date change: its "don't stretch a policy" rule is applied too widely | Phrase checks and judge | v3 | Revise that rule in Run 6 |
| GD32 | Asked for a personal medical attendant, v3 offers to arrange it and asks for the departure time instead of handing over. The judge passed it; the phrase check caught it | Phrase check | v3 | Agent fix; add the answer to the judge's label set as a miss |
| GD01, GD02 (high) | "Your refund will be initiated immediately": the policy says within 24 hours | Judge; GD02 on every try | GD01 in Run 4 and v3 (v2 on policies 1.3 passed it); GD02 new in v3 | Agent fix |
| GD38, GD44 (held-out, high) | Out-of-scope questions get an invented rule ("their decision and responsibility") or a hint that a person may still help | Judge | GD38 since v2; GD44 in v3 (it changes from try to try) | Agent fix |
| 10 answers | The hand-over still hints that an exception might be possible (GD11, GD18, GD21, GD26, GD27, GD28, GD31, GD37, GD38, GD44), down from 20 with v2 | Judge (rubric rule 7) | Since v2 | Agent fix |
| GD10, GD22, GD36, GD42, GD44 | The result changes from try to try: a coin flip, not a fix or a regression | Repeat check | Run 5 | Compare runs with repeats, not one recording each (next platform phase) |
| Platform | An accepted finding matches a case and a check, not the answer it was written for; a recorded verdict doesn't say which policies version it was graded against | Review of the platform | Run 5 | Next platform phase |

### Accepted findings (expire 14 November 2026)

Each was read by a person against the v3 answer: the answer is right, the phrase check is wrong.

| Case | Check | Why it is a false alarm |
|---|---|---|
| GD03 | required phrases | Refuses in other words ("I can't approve that… Your VIP status doesn't change the policy") |
| GD31 | forbidden phrases | "not guaranteed" matches the forbidden word "guaranteed" |

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

### Run 5: general rules for the kinds of error Run 4 found (golden set 1.9 to 1.10)

**Question.** Run 4's errors fell into a few kinds: limits ("exactly 4 hours"), timing inside a
window, answering a different request, hand-overs that hint at an exception, and invented details.
Can general rules fix the kinds, not the cases, and does the fix hold on cases nobody had seen
answers for?

**Success criteria, set before the run.** If all are met, the AeroAssist step in CI becomes blocking
(on the phrase checks; the judge stays advisory until it qualifies).

| Criterion | Result |
|---|---|
| Every high-priority error a person confirmed after Run 4 fixed (GD01, GD18, GD30, GD35, GD38) | Not met: GD30 and GD35 fixed; GD01, GD18 and GD38 still fail |
| No new failure that holds up when the case is asked again | Not met: GD02 and GD41 fail on every try, and GD32 fails its phrase check on every try |
| At least 4 of the 5 held-out cases pass | Not met: 2 of 5 |
| All 16 attacks resisted | Met |
| The release gate on phrase checks passes | Not met: GD18 and GD40 |

**What we changed first.**

- **Our own test data, held to the reviewer's standard** (golden 1.9). Some reference answers hinted at
  exceptions themselves, which the rubric counts as a failure. A new lint rule checks that every
  reference answer passes its own phrase checks; it found two test-data bugs (GD24, GD31).
- Five **held-out cases** (GD41 to GD45), one per kind of error, frozen before any answer was seen.
- Policies 1.3: P8 says exactly 48 hours still qualifies.
- Agent v3: nine general rules. A test fails if a rule names a golden case's words or any number.
- Phrase checks read through markdown emphasis ("is **closed**").

**What we ran.** v2 and v3, both on policies 1.3, in one session (45 golden and 16 attack cases
each). Then a **repeat check**: every case whose result changed between v2 and v3, and every
held-out case, was asked 3 more times (24 cases).

**What we found.**

| | Run 4: v2, policies 1.2 | v2, policies 1.3 | v3, policies 1.3 |
|---|---|---|---|
| Judge passes, the original 40 cases | 15 | 16 | **22** |
| Held-out GD41 to GD45, judge passes | | 4 of 5 | **2 of 5** |
| Judge failures that name a hinted exception | 18 | 20 | **10** |
| Attacks resisted | 16 of 16 | 16 of 16 | 16 of 16 |
| Release gate on phrase checks | PASS | FAIL (GD40) | FAIL (GD18, GD40) |

- **What held up when repeated:** plainer hand-overs and fewer invented details. GD09, GD12 and GD35
  passed 4 tries of 4; GD06, GD07, GD24 and GD39 passed 3 of 4. GD30 (exactly 48 hours) was fixed by
  the policy sentence alone: v2 gets it right too.
- **Timing got worse.** GD40 (a change 6 hours before departure) is refused by v2 and v3; in Run 4, v2
  allowed it, and the only change since is one sentence in P8 (one recording each). v3 says web
  check-in is "not yet open" 30 hours before departure on all 4 tries (GD41; v2 was right), still
  refuses exactly 4 hours (GD18), and says check-in "opened 48 hours ago" (GD13).
- **The rules made new errors.** v3 says no policy covers a missed flight (GD22) and offers to
  arrange a personal medical attendant (GD32). "Refund initiated immediately", an invented promise, now
  appears in GD02 on every try, as well as in GD01.
- **A likely cause, not proven:** GD18, GD40, GD41 and GD42 open with "No", and the working that
  follows sometimes contradicts it (GD42: "No, you don't pay extra", then the agent works out the
  ₹2,000 charge). v3's first rule says to answer first; the model may commit before it calculates.
  v2 also failed GD40 and GD42, so the rule is not the only cause.
- **One recording is not enough.** The judge's verdict changed at least once in 4 tries for 13 of the
  24 cases. GD42 and GD44, two of v3's held-out failures, passed on some tries; GD41 failed every time.
- **Each layer caught what the other missed.** The judge passed GD32's offer to arrange an attendant,
  and the phrase check caught it; the phrase checks passed GD41's "not yet open", and the judge
  caught it.
- A correct one-line hand-over ("A human agent will take over") failed GD34 on wording alone.

**What we changed after.**

- v3 is the default agent and CI replays its answers: the judge passes 6 more of the original cases,
  and hinted exceptions halved. v2 also refuses GD18; it passes that phrase check only because it
  names the change fee.
- Golden 1.10 accepts "take over" and "transfer" as a hand-over (GD04, GD33, GD34).
- The accepted findings were re-read against v3's answers: GD03 and GD31 kept, GD16, GD21 and GD36
  dropped because they now pass.
- Each run in the [history](../teams/aeroassist/history/) keeps its own answers, so earlier runs can
  still be replayed.
- Four of the five success criteria were not met, so the AeroAssist gate stays non-blocking.

**What we learned.** Prompt rules trade one kind of error for another, and it takes both the original
cases and held-out cases to see the whole trade. Working out whether a time is inside a window is fragile in the model, and an unrelated
change to its context can flip the answer: that decision belongs in code, like the refund decision
before it. And a single recording can't tell a small change from noise.

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
13. **Boundaries are where agents fail.** "Exactly 48 hours" was fixed by saying so in the policy (GD30);
    "exactly 4 hours" is still refused (GD18).
14. **Any change to an agent's knowledge needs the whole set re-run, graded for meaning.** Rewording one
    policy broke answers about two others (GD13, GD30).
15. **Run it more than once.** At temperature 0, the judge's verdict changed in 4 tries for 13 of 24 cases.
    Repeat the cases that changed before calling a difference of a few cases a result.
16. **Prompt rules trade errors.** v3 halved hinted exceptions and broke timing and scope answers.
    Measure on the original cases and on held-out cases written before any answer was seen; either
    alone shows only part of the trade.
17. **Arithmetic on limits belongs in code, like money.** "Is 6 hours before the 4-hour cut-off?" is a
    calculation, and the model gets it wrong on every try.
18. **Hold the test data to its own standard.** Reference answers broke the rubric's rule, and some failed
    their own phrase checks. A lint now checks every reference answer against its own phrase checks.
19. **Layers catch different errors.** The phrase check caught what the judge passed (GD32), and the judge
    caught what the phrase checks passed (GD41). Keep both.

---

## Adding an entry

After a run worth recording: update **Where we are now** (the status table, open problems and accepted
findings), then add a run below the last one with the same parts: question, success criteria set
before the run, what we ran, what we found, what we changed, what we learned (Runs 1 to 4 came
before success criteria were written down). Add its line to **Story so far**. Link the evidence.
