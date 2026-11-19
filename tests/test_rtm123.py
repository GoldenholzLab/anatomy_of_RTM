from pathlib import Path
from dataclasses import replace
import json
import os
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from rtm_anatomy.rtm123 import (
    BASELINE_MONTHS,
    DAYS_PER_MONTH,
    apply_detector,
    default_condition_specs,
    evaluate_patient,
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
    run_condition,
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
    def make_cache_cohort(self, directory, n=20):
        directory.mkdir()
        daily = np.stack([daily_from_monthly([4] * 6) for _ in range(n)])
        daily.tofile(directory / "daily_counts.int16.memmap")
        np.save(directory / "latent_msf.npy", np.full(n, 4, dtype=np.float32))
        np.save(directory / "patient_seeds.npy", np.arange(1, n + 1, dtype=np.int64))
        (directory / "cohort_metadata.json").write_text(json.dumps({
            "n_patients": n, "days": 180, "months": 6, "days_per_month": 30,
            "completed_patients": n, "master_seed": 20260531,
        }))

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

    def test_fixed_enrollment_retains_baseline_window_and_zero_baseline(self):
        daily = daily_from_monthly([4] * 6)
        spec = default_condition_specs()[3]
        result = evaluate_patient(daily, 4, 20, spec, 6, 30, 3, 25, fixed_first_start=0)
        self.assertEqual(result["first_start"], 1)
        self.assertEqual(result["fixed_first_start"], 0)
        self.assertEqual(result["baseline"], 4)
        self.assertEqual(result["fixed_baseline"], 3.5)
        self.assertTrue(result["rtm"])
        self.assertFalse(result["fixed_rtm"])
        zero = evaluate_patient(daily, 4, 20, replace(spec, sensitivity=0),
                                6, 30, 3, 25, fixed_first_start=0)
        self.assertFalse(zero["eligible"])
        self.assertTrue(zero["fixed_eligible"])
        self.assertEqual(zero["fixed_baseline"], 0)
        self.assertTrue(np.isnan(zero["fixed_pc"]))

    def test_measurement_cache_rejects_wrong_baseline_policy_and_spec(self):
        with tempfile.TemporaryDirectory() as tmp:
            cohort, output = Path(tmp) / "cohort", Path(tmp) / "out"
            self.make_cache_cohort(cohort)
            baseline, measured = default_condition_specs()[0], default_condition_specs()[3]
            run_condition(cohort, output, baseline, monthly_min=5, progress=None)
            with self.assertRaisesRegex(ValueError, "Perfect-detector enrollment cache"):
                run_condition(cohort, output, measured, monthly_min=3, progress=None)
            run_condition(cohort, output, replace(baseline, threshold=8), progress=None)
            with self.assertRaisesRegex(ValueError, "Perfect-detector enrollment cache"):
                run_condition(cohort, output, measured, progress=None)

    def test_measurement_cache_checks_baseline_dependency_before_cache_hit(self):
        with tempfile.TemporaryDirectory() as tmp:
            cohort, output = Path(tmp) / "cohort", Path(tmp) / "out"
            self.make_cache_cohort(cohort)
            baseline, measured = default_condition_specs()[0], default_condition_specs()[3]
            run_condition(cohort, output, baseline, progress=None)
            first = run_condition(cohort, output, measured, progress=None)[0]
            self.assertEqual(first["n_fixed"], 20)
            run_condition(cohort, output, baseline, monthly_min=5, progress=None)
            with self.assertRaisesRegex(ValueError, "Perfect-detector enrollment cache"):
                run_condition(cohort, output, measured, progress=None)

    def test_measurement_cache_binds_actual_baseline_windows(self):
        import rtm_anatomy.rtm123 as module
        with tempfile.TemporaryDirectory() as tmp:
            cohort, output = Path(tmp) / "cohort", Path(tmp) / "out"
            self.make_cache_cohort(cohort)
            baseline, measured = default_condition_specs()[0], default_condition_specs()[3]
            run_condition(cohort, output, baseline, progress=None)
            run_condition(cohort, output, measured, progress=None)
            path = output / "patient_condition_flags/baseline_perfect.npz"
            with np.load(path) as loaded:
                changed = {key: loaded[key] for key in loaded.files}
            changed["first_start"][:] = 1
            np.savez_compressed(path, **changed)
            with patch.object(module, "_evaluate_condition_chunk", wraps=module._evaluate_condition_chunk) as evaluate:
                run_condition(cohort, output, measured, progress=None)
                self.assertGreater(evaluate.call_count, 0)
            with np.load(output / "patient_condition_flags" / f"{measured.name}.npz") as loaded:
                np.testing.assert_array_equal(loaded["fixed_first_start"], 1)

    def test_cache_binds_cohort_contents_including_seeds_and_latent_rates(self):
        with tempfile.TemporaryDirectory() as tmp:
            cohort, output = Path(tmp) / "cohort", Path(tmp) / "out"
            self.make_cache_cohort(cohort)
            baseline, measured = default_condition_specs()[0], default_condition_specs()[3]
            run_condition(cohort, output, baseline, progress=None)
            run_condition(cohort, output, measured, progress=None)
            flags = output / "patient_condition_flags" / f"{measured.name}.npz"
            with np.load(flags) as loaded:
                original = loaded["baseline"]
            seeds_path = cohort / "patient_seeds.npy"
            old_stat = seeds_path.stat()
            np.save(seeds_path, np.arange(101, 121, dtype=np.int64))
            os.utime(seeds_path, ns=(old_stat.st_atime_ns, old_stat.st_mtime_ns))
            with self.assertRaisesRegex(ValueError, "Perfect-detector enrollment cache"):
                run_condition(cohort, output, measured, progress=None)
            run_condition(cohort, output, baseline, progress=None)
            run_condition(cohort, output, measured, progress=None)
            with np.load(flags) as loaded:
                self.assertFalse(np.array_equal(original, loaded["baseline"], equal_nan=True))
            latent_path = cohort / "latent_msf.npy"
            np.save(latent_path, np.full(20, 5, dtype=np.float32))
            with self.assertRaisesRegex(ValueError, "Perfect-detector enrollment cache"):
                run_condition(cohort, output, measured, progress=None)
            run_condition(cohort, output, baseline, progress=None)
            daily_path = cohort / "daily_counts.int16.memmap"
            old_stat = daily_path.stat()
            daily = np.memmap(daily_path, dtype=np.int16, mode="r+", shape=(20, 180))
            daily[0, 0] += 1
            daily.flush()
            del daily
            os.utime(daily_path, ns=(old_stat.st_atime_ns, old_stat.st_mtime_ns))
            with self.assertRaisesRegex(ValueError, "Perfect-detector enrollment cache"):
                run_condition(cohort, output, measured, progress=None)

    def test_corrupt_or_incomplete_cache_is_recomputed(self):
        with tempfile.TemporaryDirectory() as tmp:
            cohort, output = Path(tmp) / "cohort", Path(tmp) / "out"
            self.make_cache_cohort(cohort)
            spec = default_condition_specs()[0]
            expected = run_condition(cohort, output, spec, progress=None)[0]
            flags = output / "patient_condition_flags" / f"{spec.name}.npz"
            flags.write_bytes(b"incomplete cache")
            rebuilt = run_condition(cohort, output, spec, progress=None)[0]
            self.assertEqual(rebuilt["n_eligible"], expected["n_eligible"])
            with np.load(flags) as loaded:
                incomplete = {key: loaded[key] for key in loaded.files if key != "fixed_first_start"}
            np.savez_compressed(flags, **incomplete)
            run_condition(cohort, output, spec, progress=None)
            with np.load(flags) as loaded:
                self.assertIn("fixed_first_start", loaded.files)

    def test_type1_cache_binds_simulator_provenance(self):
        import rtm_anatomy.rtm123 as module
        with tempfile.TemporaryDirectory() as tmp:
            cohort, output = Path(tmp) / "cohort", Path(tmp) / "out"
            self.make_cache_cohort(cohort, n=2)
            spec = default_condition_specs()[1]
            with patch.object(module, "simulator_fingerprint", return_value={"source_sha256": "one"}):
                run_condition(cohort, output, spec, progress=None)
                with patch.object(module, "_evaluate_condition_chunk", wraps=module._evaluate_condition_chunk) as evaluate:
                    run_condition(cohort, output, spec, progress=None)
                    evaluate.assert_not_called()
            with patch.object(module, "simulator_fingerprint", return_value={"source_sha256": "two"}):
                with patch.object(module, "_evaluate_condition_chunk", wraps=module._evaluate_condition_chunk) as evaluate:
                    run_condition(cohort, output, spec, progress=None)
                    self.assertGreater(evaluate.call_count, 0)

    def test_generation_resume_rejects_changed_seed_or_unpinned_partial_cohort(self):
        with tempfile.TemporaryDirectory() as tmp:
            cohort = Path(tmp) / "cohort"
            self.make_cache_cohort(cohort)
            with self.assertRaisesRegex(ValueError, "master_seed"):
                generate_common_cohort(cohort, n_patients=20, months=6, master_seed=99, progress=None)
            path = cohort / "cohort_metadata.json"
            metadata = json.loads(path.read_text())
            metadata["completed_patients"] = 10
            path.write_text(json.dumps(metadata))
            with self.assertRaisesRegex(ValueError, "simulator provenance"):
                generate_common_cohort(cohort, n_patients=20, months=6, progress=None)

    def test_simulator_import_does_not_write_bytecode_to_read_only_source(self):
        import rtm_anatomy.rtm123 as module
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)
            (source / "realSim_turbo.py").write_text("value = 12\n")
            with patch.object(module, "_CHOCOLATE_MODULE", None), \
                    patch.object(module, "_CHOCOLATE_SOURCE", None), \
                    patch.object(module, "chocolate_repo_path", return_value=source):
                self.assertEqual(module.load_chocolate_module().value, 12)
                self.assertFalse((source / "__pycache__").exists())

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

