"""Telling a real difference between two runs from chance: the sign test and the Wilson range."""

import pytest

from aiquality.reporting.noise import sign_test_p, verdict, wilson_range


@pytest.mark.parametrize("better, worse, expected", [(14, 2, 0.0042), (6, 5, 1.0), (3, 4, 1.0), (5, 0, 0.0625),
                                                     (10, 0, 0.002)])
def test_sign_test_p_values(better, worse, expected):
    assert sign_test_p(better, worse) == pytest.approx(expected, abs=0.0005)


def test_no_change_is_not_a_result():
    assert sign_test_p(0, 0) == 1.0 and verdict(0, 0, 1.0) == "no case changed"


def test_verdicts_in_plain_words():
    assert verdict(14, 2, sign_test_p(14, 2)) == "unlikely to be chance"
    assert verdict(6, 5, sign_test_p(6, 5)) == "could be chance"


def test_the_wilson_range_brackets_the_rate_and_stays_in_bounds():
    low, high = wilson_range(42, 56)
    assert low < 42 / 56 < high and 0.6 < low < 0.65 and 0.83 < high < 0.86
    assert wilson_range(10, 10)[1] == 1.0 and wilson_range(0, 10)[0] == 0.0
    assert wilson_range(0, 0) == (None, None)


def test_a_few_cases_give_a_wide_range():
    small, large = wilson_range(3, 4), wilson_range(75, 100)
    assert (small[1] - small[0]) > (large[1] - large[0])
