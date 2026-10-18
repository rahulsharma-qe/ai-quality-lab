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
| [6](#run-6-limits-decided-in-code-through-a-tool-the-agent-calls-golden-set-111) | Does deciding limits in code fix the time-window errors? | Where the agent called the code, its ruling was right; but the agent called it in only 13 of 30 cases, and began asking passengers for exact figures | v3 kept as the default; next, code consults the limits on every question |
| [7](#run-7-an-understanding-step-on-every-message-golden-set-112-to-113) | If the code runs the limits check on every message, are the time-window errors fixed? | Yes: the right topic in 35 of 35 cases and the time-window cases right on every try; the judge passes 42 of 56 answers (v3: 30). One answer contradicts the code's ruling, and phrase checks now fail correct wording | v5 becomes the default; next, check that the answer agrees with the ruling |
| [8](#run-8-the-hand-over-written-by-code-golden-set-114-to-116) | If code writes the hand-over sentence, do the hinted exceptions go away? | The hints went, but on repeats the hand-over cases barely moved (12 to 13 of 27 judge passes): the model hands over when the policy already answers, and the judge reads that as a hint. One recording alone had suggested a big gain | v5 stays the default; next, code decides *when* to hand over, not only *how* |

Next: code decides when an answer hands over (only when no policy answers the question), measured
with repeats from the start.

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

*Updated 18 October 2026, after Run 8.*

| | |
|---|---|
| Agent | v5: v3's rules, with the limits decided in code (`policy_limits.py`, limits version 2) through a tool the code makes the model call on every message; policies version 1.3 |
| Golden set | version 1.16, 58 cases (22 of them held-out); 47 cases say what a good answer decides (`expected_decision`) |
| Phrase checks | required phrases 98%, forbidden phrases 95% (100% after two accepted false alarms); attacks resisted 16 of 16 |
| Decision check | 44 pass, 2 fail (GD32, GD46), 12 not counted; reports, doesn't block |
| Judge | passes 43 of 58 answers (74%), but **advisory**: its version has not qualified against a person's labels (it leaves only 62% of good answers alone; the bar is 80%) |
| Release gate on phrase checks | **FAIL**: high-priority GD07, a real error |
| Noise | the same agent recorded in two sessions differs on 8 to 11 of about 50 judge verdicts; `aiquality compare` now says whether a difference is bigger than chance, and `aiquality repeat` asks a case again |
| Continuous integration (CI) | the AeroAssist gate is reported but **not blocking**: it fails on a real high-priority error |
| Recording CI replays | v5's Run 7 recording, plus GD57 and GD58 from Run 8's repeat check (the first of three tries; v5 never answered them in Run 7) |

### Open problems

| Case | What is wrong, in plain words | Found by | Since | Next step |
|---|---|---|---|---|
| GD46 (held-out) | The code rules web check-in "open" 3 hours before departure, and the answer says "No, you cannot check in online", on every try | Judge; the decision check | v5 (v4 got it wrong without calling the tool) | A guard that checks the answer against the ruling (parked) |
| GD07 (high) | Asked for 3 cabin bags with no class given, the agent assumes economy instead of giving both classes' allowance | Phrase check and judge | v3 to v5 | v6 drops a class the passenger didn't state: the judge passed it 3 of 3, but the answer said "2 cabin bags" only 1 of 3 times |
| GD20 (high) | Late for a flight 2 hours away: the change is refused correctly, and the answer hints that a person may help | Judge | v3 to v5 | With the hand-over decision below. Its wording ("forfeited" for no-show) is accepted since golden 1.16 |
| GD19, GD24, GD13, GD55 | When the time isn't given, v5 answers for each case and then asks for the time (GD13, GD55), or asks instead of answering (GD19, GD24). GD19 also says "4 hours or less" where exactly 4 hours still qualifies | Repeat check (asks for a figure); judge | v4 and v5 | Parked |
| GD10, GD15, GD53 | Invented details around a right ruling: a 40 kg split the passenger never gave, a promise that a person will send the check-in link, a "personal items" rule | Judge | v5 | Agent fix |
| 7 answers | The hand-over still hints that an exception might be possible (GD11, GD20, GD27, GD31, GD32, GD38, GD50). Run 8's v6 wrote the hand-over in code: the hints went, but the model now hands over when the policy already answers (GD50 every time; GD15, GD27), which the judge also fails | Judge (rubric rule 7) | Since v2 | Next run: code decides when to hand over |
| GD14 | Exactly 2 hours before departure: the policy doesn't say whether web check-in is still open. The limits code says so instead of deciding | Reading the policy | Since the start | The policy owner decides |
| Phrase checks | Correct answers fail on wording more often as the agent improves: 4 of v5's 6 high-priority phrase failures were correct answers, fixed in golden 1.13 or accepted | A person reading each failure | Run 7 | The decision check (Run 8) compares what was decided; it reports until its reader has been measured on more answers |
| Platform | An accepted finding matches a case and a check, not the answer it was written for (GD13's acceptance has a short expiry for this reason); a recorded verdict doesn't say which policies version it was graded against | Review of Runs 5 to 7 | Run 5 | Parked until needed. Done in Run 8: noise in comparisons, the repeat command |

### Accepted findings

Each was read by a person against the answer CI replays: the answer is right, the phrase check is wrong.

| Case | Check | Why it is a false alarm | Expires |
|---|---|---|---|
| GD31 | forbidden phrases | "best-effort and not guaranteed" matches the forbidden word "guaranteed" | 14 November 2026 |
| GD13 | forbidden phrases | "If your flight is fewer than 2 hours away, web check-in is closed" is a condition, not a claim; the lock is for an answer that says it is closed outright | 1 November 2026 |

---

## The runs, oldest first

### Before the platform: two findings from the first scripts

**The agent repeated a poisoned fact.** The first attack run found 0 breaches in 10, which we read
as a sign the attacks were too weak, not that the agent was safe. Stronger attacks still failed to
make it ignore its rules, but changing one number in a retrieved policy (refund window 24 hours to
30 days) made it promise a refund the passenger wasn't due. An agent that trusts its documents
repeats a poisoned document. Fix: the refund decision moved into code; the model only words it.
Details: [README, "The first finding"](../README.md#the-first-finding-a-poisoned-fact-where-the-code-rules-began).

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

### Run 6: limits decided in code, through a tool the agent calls (golden set 1.11)

**Question.** Run 5 showed that prompt rules can't make the model place a time inside a window. If
the model only reads the facts and code decides (the policy-limits tool), are the time-window errors
fixed, without breaking anything else?

**Success criteria, set before the run.** If all are met, the AeroAssist step in CI becomes blocking.

| Criterion | Result |
|---|---|
| GD13, GD18, GD40 and GD41 pass the judge on at least 3 of 4 tries | Not met: GD40 4 of 4; GD13 3 of 4, but every try asks for the departure time instead of answering; GD18 0 of 4, GD41 1 of 4 |
| The tool is called in every case whose answer depends on a time or a weight (30 cases, listed before any answer was seen) | Not met: 13 of 30 |
| No new failure that holds up when the case is asked again | Not met: GD19 and GD43 fail on 3 or more of 4 tries; GD13 and GD24 fail their phrase checks on 3 or more |
| At least 5 of the 6 new held-out cases pass on at least 3 of 4 tries | Not met: 3 (GD47, GD48, GD49) |
| All 16 attacks resisted | Met |
| The release gate on phrase checks passes | Not met |

**What we changed first.**

- **The limits in code** ([`policy_limits.py`](../teams/aeroassist/policy_limits.py)): one ruling per
  policy rule with a number in it (P1, P2, P3, P4, P5, P8). A test reads `policies.md` and checks that
  every limit in code is the one the policy states. At exactly 2 hours before departure the policy
  doesn't say whether web check-in is open, and the ruling says so instead of deciding (GD14).
- **Agent v4**: v3 plus the tool. Rule 4 (work out where the time falls) became "call the tool and give
  its ruling"; a test checks that nothing else changed, so a difference comes from the tool.
- **Six held-out cases** (GD46 to GD51), one per limit the tool decides, frozen before any answer.
- **An honest limit**: the facts still come from the passenger's message. Code makes the arithmetic
  reliable, not the facts true; in a real system the times would come from the booking system.

**What we ran.** v3 and v4 in one session (51 golden and 16 attack cases each), then a repeat check:
GD13, GD18, GD40, GD41, every case whose result changed, and the six new held-out cases, asked 3 more
times with v4 (23 cases).

**What we found.**

| | v3 | v4 |
|---|---|---|
| Judge passes, all 51 cases | 25 | **31** |
| Original 40 cases | 19 | 23 |
| Held-out GD41 to GD45 / GD46 to GD51 | 3 of 5 / 3 of 6 | 4 of 5 / 4 of 6 |
| Required phrases (bar 85%) | 92% | **82%** |
| Attacks resisted | 16 of 16 | 16 of 16 |

Every answer was then split by layer:

- **The ruling.** Whenever the tool was called, its ruling was right for the facts it was given.
- **Reading the facts.** The model passed the right figures in every call, including "three and a
  half hours" written in words (GD50). Once it invented a split of a 40 kg total that the passenger
  never gave (GD10).
- **Calling the tool at all.** Only 13 of the 30 cases. Where the model skipped it, the old errors came
  back: a check-in "closed" 3 hours before departure (GD46), "not open yet" 30 hours before (GD41),
  exactly 4 hours refused (GD18). GD41 shows both sides: right with the tool, wrong without it. Of the
  four cases where the tool was called on every try, three passed every try (GD40, GD42, GD48); the
  fourth, GD50, had the right ruling every time and failed on its hand-over wording.
- **Wording.** With a right ruling underneath, some answers still hinted at an exception at the
  hand-over (GD31, GD50, GD51) or promised more than the policy ("guaranteed", GD29; "approved", GD30).
- **A new kind of failure.** The tool needed exact figures and said "missing" otherwise, and the model
  began asking the passenger for them instead of answering, even when the question said "in a week"
  (GD05, GD13, GD17, GD19, GD24). The judge passed GD13's question; the phrase checks caught it.
- **The noise floor.** v3 recorded again, with no change to the agent, differed from Run 5's v3 on 8
  of 45 judge verdicts. v4 and v3 differ on 16, so only the gains that held in the repeat check count:
  GD40, GD42 and GD49, which v3 failed and v4 passed on all 4 tries.

**What we changed after.**

- v3 stays the default. v4 is better on the judge but worse on the blocking phrase checks, adds a
  failure passengers would notice, and its gain depends on a tool call it skips more often than not.
  v4's recording, with its tool calls, is kept in the [history](../teams/aeroassist/history/).
- CI replays v3's Run 6 recording, which answers the six new cases. GD03's acceptance was removed
  because it now passes.
- Five of the six success criteria were not met, so the AeroAssist gate stays non-blocking.

**What we learned.** Code decides limits correctly, but only when it is asked, and here the model
decided when to ask. Making the check the code's job, not the model's, is the next step. A tool also
shapes behaviour: one that demands exact facts taught the model to interrogate the passenger. And a
measured noise floor (8 of 45) is what turns "v4 passes 6 more" into "three gains are real".

### Run 7: an understanding step on every message (golden set 1.12 to 1.13)

**Question.** In Run 6 the code's rulings were right, but the model chose when to ask for them and
skipped 17 of 30, and a tool that needed exact figures made it ask passengers for them. If the code
runs the limits check on every message (an understanding step: the model reads the topic and the
facts, the code decides, the model words it), and the limits rule on approximate facts, are those
errors gone?

**Success criteria, set before the run.** If all are met, v5 becomes the default and the AeroAssist
step in CI becomes blocking.

| Criterion | Result |
|---|---|
| GD13, GD18, GD40, GD41 and GD46 pass the judge and their phrase checks on at least 3 of 4 tries | Not met: GD18, GD40 and GD41 met it; GD13 passed the judge 4 of 4 but its lock caught a correct conditional answer; GD46 0 of 4 |
| The limits tool is asked about the right topic in all 35 cases that need it | **Met**: 35 of 35 |
| GD05, GD13, GD17, GD19 and GD24 answer without asking for a figure on at least 3 of 4 tries | Not met: 2 of 5 (GD05, GD17) |
| No new failure that holds up when the case is asked again, counting every check | Not met: GD19 (judge); GD13 and GD21 on wording only |
| At least 4 of the 5 new held-out cases pass on at least 3 of 4 tries | **Met**: 4 (GD52, GD54, GD55, GD56) |
| All 16 attacks resisted | **Met** |
| The release gate on phrase checks passes | Not met |

**What we changed first.**

- **An understanding step.** The first model call of every message must call the limits tool
  (`force_first_tool`): the code, not the model, decides that the limits are checked. A question with
  nothing to check passes no topics. Real support systems do the same with intent and fact extraction
  on every message; the strongest version takes the times from the booking system, which this mock
  doesn't have.
- **Limits that rule on approximate facts** (limits version 2): a time can be a range ("less than 48
  hours"), and the ruling is one outcome if the whole range falls in one case, or "depends" with the
  rule. A bag count without a weight still gets a ruling. The tool never answers "missing". A test
  keeps golden-case wording out of the tool's description, which the model reads.
- **Agent v5**: v4 with the understanding step; only the timing rule changes.
- **Five held-out cases** (GD52 to GD56) with facts that aren't exact, frozen before any answer.

**What we ran.** v3 and v5 in one session (56 golden and 16 attack cases each), then a repeat check
that counts a change in any check, not only the judge's (25 cases, 3 more tries each).

**What we found.**

| | v3 | v5 |
|---|---|---|
| Judge passes, all 56 cases | 30 | **42** |
| Original 40 cases | 20 | 29 |
| Held-out GD41 to GD45 / GD46 to GD51 / GD52 to GD56 | 3 / 3 / 4 | 5 / 4 / 4 |
| Judge failures that name a hinted exception | 9 | 7 |
| Attacks resisted | 16 of 16 | 16 of 16 |

- **The routing problem is solved.** The tool was asked about the right topic in all 35 cases that
  needed it (Run 6: called in 13 of 30), and the time-window cases that failed in earlier runs now
  pass on every try: GD18 (exactly 4 hours), GD40 (6 hours), GD41 (30 hours).
- **The gains are bigger than the noise.** v3 recorded again differs from Run 6's v3 on 11 of 51
  verdicts. v5 and v3 differ on 16, 14 of them in v5's favour, and 13 of those held on at least 3 of 4
  tries.
- **A right ruling, contradicted in words.** For a flight 3 hours away the code ruled web check-in
  "open, closes in 1 hour", and the answer said "No, you cannot check in online" on all 4 tries (GD46).
  Nothing checks that the answer agrees with the ruling behind it.
- **Asking, mostly after answering.** With no time given, v5 usually answers for each case and then
  asks for the time (GD13, GD55), which the judge passes; GD19 and GD24 still ask instead of answering.
- **Phrase checks became the bottleneck.** Of v5's six high-priority phrase failures, four were correct
  answers in other words ("difference in the fare", "can't approve", "forfeit" for no-show). Golden 1.13
  accepts those words; GD13's correct conditional answer is an accepted finding with a short expiry.
  The two left, GD07 and GD20, are real errors.

**What we changed after.**

- v5 is the default and CI replays its recording. With golden 1.13 the gate fails only on GD07 and GD20.
- Accepted findings re-read: GD31 kept, GD44 dropped (it now passes), GD13 added until 1 November.
- Four of the seven success criteria were not met, so the AeroAssist gate stays non-blocking.

**What we learned.** Taking the decision of *when* to check out of the model fixed what Run 6 left: the
right rule was consulted every time, and the time-window errors that had survived several runs went away.
What remains is the last layer, wording: an answer can still contradict a ruling it was given, and
phrase checks, built for a weaker agent, now fail more correct answers than wrong ones. Both point to
checking what was decided, not which words were used.

---

### Run 8: the hand-over written by code (golden set 1.14 to 1.16)

**Question.** After Run 7, 9 of v5's 14 judge failures were about the hand-over: "a human agent may be
able to discuss options", a promise, or a claim about what a person can't do. If the model only marks
that the passenger needs a person and code writes the hand-over sentence, do those failures go away?

**Success criteria, set before the run.** If all are met, v6 becomes the default.

| Criterion | Result |
|---|---|
| Judge failures about the hand-over drop from 9 to at most 2, and hold when the cases are asked again | Not met: 2 in the recording, but on repeats the 9 cases passed the judge 13 of 27 times (v5: 12) |
| GD07 passes | Partly: the judge passed it 3 of 3, its phrase check 1 of 3 |
| No new failure that holds up when the case is asked again | Not met: GD27 (v5 3 of 3, v6 0 of 3) and GD15 (2 of 3 to 0 of 3) |
| Both new held-out cases pass | **Met**: GD57 2 of 3, GD58 3 of 3 (judge) |
| All 16 attacks resisted | **Met** |

**What we changed first.**

- **The platform** learned three things, all without a key: a **decision check** (each case can say
  what a good answer decides: yes, no, depends, hand over, an amount; a rule-based reader reads the
  answer's opening and reports, without blocking); a **noise section** in `aiquality compare` (per
  check, how many cases got better and worse, and whether that split is bigger than chance); and
  `aiquality repeat`, which asks chosen cases again and counts each check on its own.
- **The decision reader was measured before use.** On 263 recorded answers from Runs 4 to 7 it read a
  decision in 239; of its 28 disagreements with the expected decision, 25 were real wrong decisions,
  2 were its own misreadings and 1 was debatable. It also caught one wrong decision the judge passed.
- **Golden set 1.14 to 1.16**: `expected_decision` on 47 cases (the changelog lists the ones left
  without one, and why); two held-out cases for v6, frozen before it was built (GD57: a money request
  outside the policies; GD58: two cabin bags, no class given); GD20 accepts "forfeit" for no-show, as
  GD21 and GD36 do.
- **Agent v6**: v5, with two steps moved from the model to code. The model marks a hand-over with
  `HAND_OVER`, and code removes every sentence about what a human agent, a colleague or a team might do
  and adds one fixed sentence ([`hand_over.py`](../teams/aeroassist/hand_over.py)). A cabin class reaches
  the limits tool only if the passenger stated it ([`stated_facts.py`](../teams/aeroassist/stated_facts.py)).
  Two rules change. Each answer lists what code changed.

**What we ran.** v6 recorded once (58 golden and 16 attack cases), compared with Run 7's v5 recording
graded again with golden set 1.15. Then 18 cases (the 9 hand-over cases, the 2 held-out cases, and the
7 other cases whose judge, decision or phrase result changed) asked 3 times each with v6 **and** with
v5, in one session. The recording used hand-over code 1. Reading the 11 sentences it removed found 2
that weren't about handing over ("escalation threats", "authorized representative"); code 2 keeps them.
The repeats ran with code 2 (agent version `…handover-2`). Neither removal changed a verdict.

**What we found.**

| Judge passes | v5 | v6 |
|---|---|---|
| The recording, 56 cases both versions answered | 42 | 48 |
| Repeats: the 9 hand-over cases (27 tries) | 12 | 13 |
| Repeats: all 18 cases (54 tries) | 31 | 34 |
| Attacks resisted | 16 of 16 | 16 of 16 |

- **One recording overstated the gain.** The recording showed 42 to 48, with 8 cases better and 2 worse
  (p = 0.11 without the held-out cases, which only v6 had answered). Asked again, the hand-over cases
  barely moved. Without the repeats, v6 would have become the default on luck.
- **The hints went; the hand-over decision is the problem.** Code removed the hint sentences as
  designed, but the model also marks a hand-over after an answer the policy fully covers, and the judge
  reads any hand-over there as a hint that an exception might exist: GD50 on all 3 tries, GD27 and GD15
  on one each. GD27's other two tries invented an upgrade rule or a "sales team"; GD20's got past the
  code's list in new words ("speak with an agent about your options").
- **Facts from the passenger only.** The cabin class the model added for GD07 was dropped by code, and
  the judge passed GD07 on every try; but its answer said "2 cabin bags" only once in three.
- **The decision check agreed with the judge** on its two failures (GD32, GD46), and its one new
  failure (GD55, "No, if your flight is within 2 hours…") was its own misreading of a conditional answer.

**What we changed after.**

- v5 stays the default. v6 stays in the repository, with this result.
- CI replays v5's Run 7 recording, plus its answers to GD57 and GD58 from this run's repeat check (the
  first of three tries; v5 never answered them in Run 7). With golden 1.16 the gate fails only on GD07.

**What we learned.** Code can own *how* something is said, but not *whether* it should be said: the
hand-over sentence moved to code, and the failures moved to the decision to hand over. And a single
recording is a sample of one: the repeats turned an apparent 6-case gain into a 1-try difference.

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
20. **Code decides only what it is asked.** Moving a decision into a tool doesn't help if the model chooses
    when to call it: v4 skipped the tool in 17 of 30 cases. Make consulting the rules the code's job.
21. **A tool shapes the agent's behaviour.** A tool that demanded exact figures taught the model to ask the
    passenger for them instead of answering. Design tools to rule on what is known.
22. **Measure the noise floor before reading a difference.** The same agent recorded twice differed on 8
    of 45 verdicts; only differences that hold when repeated are results.
23. **Fix the layer that failed.** Run 6 split v4's answers by layer and found the routing broken; Run 7
    changed only that, and the right rule was consulted in 35 of 35 cases.
24. **A right decision can still be said wrong.** Code ruled "open" and the answer said "no". Check that
    an answer agrees with the decision behind it, not only that it contains the right words.
25. **As the agent improves, phrase checks start failing correct answers.** Four of six high-priority
    phrase failures were right answers in other words. Move the gate toward meaning: decisions checked in
    code, and a judge that has qualified.
26. **Moving the wording to code doesn't move the decision.** v6 wrote every hand-over in code, and the
    failures moved to *when* the model chose to hand over. Find which part of the behaviour fails before
    choosing what to move into code.
27. **Measure a new check before it gates.** The decision reader was read against 263 recorded answers
    first: 25 of its 28 disagreements were real errors, 2 its own misreadings. It reports; it doesn't block.
28. **Repeat before you believe.** One recording showed 6 more judge passes; the repeats showed 1. Ask the
    changed cases again, with the old version too, in the same session.

---

## Adding an entry

After a run worth recording: update **Where we are now** (the status table, open problems and accepted
findings), then add a run below the last one with the same parts: question, success criteria set
before the run, what we ran, what we found, what we changed, what we learned (Runs 1 to 4 came
before success criteria were written down). Add its line to **Story so far**. Link the evidence.
