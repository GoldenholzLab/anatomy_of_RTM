from pathlib import Path
import tempfile
import unittest

import numpy as np

from rtm_anatomy.rtm123 import (
    BASELINE_MONTHS,
    DAYS_PER_MONTH,
    apply_detector,
    build_type1_diary,
    find_first_eligible_window,
    generate_common_cohort,
    make_figures,
    monthly_from_daily,
    percent_change,
    rtm_occurs,
    rtm_from_totals,
    paired_rtm_at_window,
    run_all_conditions,
    type1_overlap_label,
)


def daily_from_monthly(monthly_counts):
    daily = np.zeros(len(monthly_counts) * DAYS_PER_MONTH, dtype=np.int16)
    event_days = [0, 10, 20, 29, 5, 15, 25, 28, 2, 12]
    for month, count in enumerate(monthly_counts):
        start = month * DAYS_PER_MONTH
        for event_index in range(int(count)):
            daily[start + event_days[event_index % len(event_days)]] += 1
    return daily


class RTM123Tests(unittest.TestCase):
    def test_first_eligible_window_uses_first_passing_baseline(self):
        monthly = np.zeros(36, dtype=np.int32)
        monthly[3:5] = [4, 4]
        monthly[8:10] = [8, 8]
        daily = daily_from_monthly(monthly)
        self.assertEqual(find_first_eligible_window(monthly, daily, threshold=4), 3)

    def test_no_eligible_when_seizure_free_run_is_too_long(self):
        monthly = np.zeros(36, dtype=np.int32)
        monthly[0:2] = [4, 4]
        daily = np.zeros(36 * DAYS_PER_MONTH, dtype=np.int16)
        daily[0:4] = 1
        daily[30:34] = 1
        self.assertEqual(find_first_eligible_window(monthly, daily, threshold=4), -1)

    def test_rtm_formula(self):
        self.assertTrue(rtm_occurs(baseline_mean=6.0, test_mean=4.5, reference_mean=4.0))
        self.assertFalse(rtm_occurs(baseline_mean=3.0, test_mean=4.0, reference_mean=4.0))
        self.assertFalse(rtm_occurs(baseline_mean=6.0, test_mean=9.0, reference_mean=4.0))

    def test_percent_change(self):
        self.assertAlmostEqual(percent_change(5.0, 3.0), 40.0)
        self.assertTrue(np.isnan(percent_change(0.0, 3.0)))

    def test_exact_ties_are_not_rtm_on_either_scale(self):
        self.assertFalse(rtm_from_totals(28, 18, 60, 6))
        self.assertTrue(rtm_from_totals(28, 19, 60, 6))
        self.assertFalse(rtm_from_totals(36, 30, 120, 6, sensitivity=0.7))

    def test_type3_keeps_detector_selected_person_with_zero_true_baseline(self):
        true = np.zeros(6, dtype=np.int64)
        measured = np.array([4, 4, 0, 0, 0, 0])
        paired = paired_rtm_at_window(measured, true, 0, 1.0, 1.0, 30)
        self.assertTrue(paired["rtm"])
        self.assertFalse(paired["true_rtm"])
        self.assertTrue(paired["type3_rtm"])
        self.assertEqual(paired["true_baseline"], 0)

    def test_measurement_can_remove_true_rtm(self):
        true = np.array([14, 14, 9, 9, 9, 5])
        measured = np.array([10, 10, 14, 14, 14, 0])
        paired = paired_rtm_at_window(measured, true, 0, 1.0, 1.0, 30)
        self.assertFalse(paired["rtm"])
        self.assertTrue(paired["true_rtm"])
        self.assertTrue(paired["true_only_rtm"])
        self.assertFalse(paired["type3_rtm"])

    def test_perfect_detector_has_no_measurement_only_classification(self):
        rng = np.random.default_rng(451)
        for _ in range(300):
            true = rng.poisson(5, size=36)
            paired = paired_rtm_at_window(true, true, 10, 1.0, 0.0, 30)
            self.assertEqual(paired["rtm"], paired["true_rtm"])
            self.assertFalse(paired["type3_rtm"])

    def test_integer_rtm_agrees_with_independent_fraction_oracle(self):
        from fractions import Fraction
        rng = np.random.default_rng(905)
        for sensitivity in (0.7, 0.8, 0.9, 1.0):
            for q in (1, 7):
                for _ in range(250):
                    b, t, total = (int(x) for x in rng.integers(0, 1000, size=3))
                    baseline, test = Fraction(b, 2*q), Fraction(t, 3*q)
                    reference = Fraction(total, 36) * Fraction(str(sensitivity))
                    expected = baseline > reference and abs(test-reference) < abs(baseline-reference)
                    self.assertEqual(rtm_from_totals(b, t, total, 36, sensitivity, q), expected)

    def test_weekly_alarm_correction_retains_fractional_expectation(self):
        true = np.zeros(180, dtype=np.int16)
        _, raw = apply_detector(true, far_per_day=1/7, correct_far=False, rng=np.random.default_rng(72))
        _, corrected = apply_detector(true, far_per_day=1/7, rng=np.random.default_rng(72))
        np.testing.assert_allclose(corrected, np.maximum(raw - 30/7, 0), rtol=0, atol=1e-12)

    def test_type1_shock_replaces_exactly_two_months(self):
        original = np.ones(36 * DAYS_PER_MONTH, dtype=np.int16)
        modified, shock_start, shock_msf = build_type1_diary(
            original,
            original_msf=4.0,
            seed=123,
            shock_start_month=5,
            shock_msf=10.0,
        )
        self.assertEqual(shock_start, 5)
        self.assertEqual(shock_msf, 10.0)
        day_start = 5 * DAYS_PER_MONTH
        day_stop = day_start + BASELINE_MONTHS * DAYS_PER_MONTH
        np.testing.assert_array_equal(modified[:day_start], original[:day_start])
        np.testing.assert_array_equal(modified[day_stop:], original[day_stop:])
        self.assertEqual(modified[day_start:day_stop].size, 60)

    def test_type1_overlap_labels(self):
        self.assertEqual(type1_overlap_label(2, -1), "not_eligible")
        self.assertEqual(type1_overlap_label(4, 4), "baseline")
        self.assertEqual(type1_overlap_label(5, 4), "baseline_and_test")
        self.assertEqual(type1_overlap_label(6, 4), "test")
        self.assertEqual(type1_overlap_label(20, 4), "neither")

    def test_detector_transforms_are_reproducible_and_monthly(self):
        true_daily = np.zeros(60, dtype=np.int16)
        true_daily[[0, 10, 20, 30, 40, 50]] = 1
        daily, monthly = apply_detector(
            true_daily,
            sensitivity=1.0,
            far_per_day=0.0,
            rng=np.random.default_rng(1),
        )
        np.testing.assert_array_equal(daily, true_daily)
        np.testing.assert_array_equal(monthly, [3, 3])
        daily_zero, monthly_zero = apply_detector(
            true_daily,
            sensitivity=0.0,
            far_per_day=0.0,
            rng=np.random.default_rng(1),
        )
        self.assertEqual(int(np.sum(daily_zero)), 0)
        self.assertEqual(int(np.sum(monthly_zero)), 0)

    def test_smoke_run_writes_expected_outputs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "rtm123_smoke"
            generate_common_cohort(
                output_dir,
                n_patients=12,
                months=6,
                chunk_size=4,
                workers=1,
                resume=False,
                progress=None,
            )
            run_all_conditions(output_dir, output_dir, chunk_size=4, resume=False, progress=None)
            figures = make_figures(output_dir)
            self.assertTrue((output_dir / "condition_summary.csv").exists())
            self.assertTrue((output_dir / "type1_overlap_summary.csv").exists())
            self.assertTrue((output_dir / "first_eligible_windows.csv").exists())
            self.assertTrue(figures["png"].exists())
            self.assertEqual(monthly_from_daily(np.zeros(60, dtype=np.int16)).shape[0], 2)


if __name__ == "__main__":
    unittest.main()

