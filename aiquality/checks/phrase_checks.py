"""Key-free checks based on the golden case's phrase lists."""

from aiquality.checks.base import Check
from aiquality.checks.phrase_matching import find_any
from aiquality.checks.registry import register_check

POSSIBLE_FALSE_ALARM = "possible_false_alarm"


@register_check("required_phrases")
class RequiredPhrases(Check):
    description = ("Every phrase in must_include appears in the answer (whole words, any case, "
                   "simple plurals; 'a OR b' accepts either).")

    def evaluate(self, case, response):
        if not case.must_include:
            return self.not_applicable(case, "case has no must_include phrases")
        missing = [p for p in case.must_include if find_any(response.answer_text, p) is None]
        if missing:
            return self.failed(case, f"missing: {', '.join(repr(p) for p in missing)}")
        return self.passed(case, f"all {len(case.must_include)} required phrases present")


@register_check("forbidden_phrases")
class ForbiddenPhrases(Check):
    description = ("No phrase in must_not_include appears in the answer. A cheap safety signal: "
                   "a match right after 'not', 'no' or 'never' is flagged as a possible false alarm.")
    safety = True

    def evaluate(self, case, response):
        if not case.must_not_include:
            return self.not_applicable(case, "case has no must_not_include phrases")
        matches = [m for m in (find_any(response.answer_text, p) for p in case.must_not_include) if m]
        if not matches:
            return self.passed(case, "no forbidden phrase found")
        found = ", ".join(repr(m.phrase) for m in matches)
        reason = f"forbidden phrase found: {found}"
        flags = []
        if all(m.follows_negation for m in matches):
            reason += " (right after a negation word: possible false alarm, check the sentence)"
            flags.append(POSSIBLE_FALSE_ALARM)
        evidence = " | ".join(m.sentence for m in matches)
        return self.failed(case, reason, evidence=evidence, flags=flags)


@register_check("response_time")
class ResponseTime(Check):
    description = "The answer arrived within max_ms milliseconds (default 10000)."

    def evaluate(self, case, response):
        max_ms = float(self.options.get("max_ms", 10_000))
        if response.latency_ms is None:
            return self.not_applicable(case, "the adapter did not report a response time")
        if response.latency_ms <= max_ms:
            return self.passed(case, f"{response.latency_ms:.0f} ms (limit {max_ms:.0f} ms)")
        return self.failed(case, f"{response.latency_ms:.0f} ms is over the {max_ms:.0f} ms limit")
