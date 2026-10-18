"""Is a difference between two runs bigger than the noise?

An AI agent doesn't give the same answer twice, even at temperature 0, so two runs of the same agent
differ on some cases by chance. Two plain tools tell a real change from that:

  sign test        Look only at the cases whose result changed. If the change made no difference,
                   each would be as likely to get better as worse, like a coin toss. 14 better and 2
                   worse is very unlikely from a fair coin (p = 0.004); 3 better and 4 worse is not.
  Wilson range     A pass rate measured on 50 cases is an estimate. The range is where the true rate
                   most likely lies (95%), so 75% on 56 cases reads as "likely 62% to 85%".

No library needed: both are a few lines of arithmetic.
"""

from math import comb, sqrt

LIKELY_REAL = 0.05        # below this p-value a difference is reported as unlikely to be chance


def sign_test_p(better: int, worse: int) -> float:
    """Two-sided p-value: the chance of a split at least this uneven if better and worse were equally likely."""
    changed = better + worse
    if changed == 0:
        return 1.0
    fewer = min(better, worse)
    one_side = sum(comb(changed, k) for k in range(fewer + 1)) / 2 ** changed
    return min(1.0, 2 * one_side)


def wilson_range(passed: int, total: int, z: float = 1.96) -> tuple:
    """The 95% range for a pass rate of passed / total (as fractions); (None, None) when total is 0."""
    if total == 0:
        return None, None
    rate = passed / total
    centre = (rate + z * z / (2 * total)) / (1 + z * z / total)
    spread = z * sqrt(rate * (1 - rate) / total + z * z / (4 * total * total)) / (1 + z * z / total)
    return max(0.0, centre - spread), min(1.0, centre + spread)


def verdict(better: int, worse: int, p_value: float) -> str:
    if better + worse == 0:
        return "no case changed"
    if p_value < LIKELY_REAL:
        return "unlikely to be chance"
    return "could be chance"
