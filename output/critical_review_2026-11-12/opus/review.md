# Critical review: anatomy of RTM, Seizure submission

Reviewer: opus sub-agent. Date: 2026-11-12.

## Scope and method

Documents reviewed as authoritative (read-only OOXML extraction, no Word or LibreOffice):

- `anatomy_of_RTM_Seizure.docx`, SHA-256 `6119f8107c62b4de9f48c852894f795cbcbee88bfc9804ef68da64bd63b40ce0`, saved 2026-11-12 23:07
- `anatomy_of_RTM_Seizure_Supplement.docx`, SHA-256 `cd7195edc9e75b6a171a6b4ca9eb4f57fa02d597b90ffa4bc8a19617f0699110`, saved 2026-11-12 22:09

Code and results traced: `rtm_anatomy/rtm123.py` (working copy, uncommitted), `scripts/rtm123/*`, `scripts/build_seizure_figures.py`, `outputs/rtm123_type3_1m/*.csv`, `run_manifest.json`, all nine per-patient flag caches in `outputs/rtm123_type3_1m/patient_condition_flags/`, and the original cohort in `outputs/rtm123_1m` (read through memmap, never written).

What I did:

1. Extracted body text, the one main table, three supplementary tables, 11 Zotero citation fields plus the bibliography field, the footnote and both embedded figures. No OMML equations are present in either document. No tracked changes or comments.
2. Cross-checked every number in the abstract, Results, Table 1 and Tables S1 to S3 against the saved CSVs (245 checks).
3. Recomputed summary counts directly from the per-patient flag arrays.
4. Replayed 50,000 random patients through the five detector conditions and 3,000 through the transient condition with the current code, comparing per-patient flags with the saved caches.
5. Ran targeted independent analyses on the saved flags and on true daily counts: true-count eligibility of detector-selected participants, an alternative measured-scale reference for false-alarm conditions, fixed-enrollment true-only counts, the distribution of percentage changes, and transient-state rate ratios.
6. Ran the 23 existing unit tests (temporary directories only, `-B` so no bytecode was written).
7. Checked cited trial eligibility criteria and the RTM definition in reference [1] against primary sources.

I formed the findings below before reading any earlier review. Afterwards I skimmed `output/revision_2026-11-12/astra_review.md` only for overlap. It already noted, qualitatively, that flooring can push corrected counts above the reference and that no true-count eligibility filter is applied. Findings R1 and R2 below quantify those two design choices for the first time as far as I can tell. I did not read the parallel `astra` or `sol` folders under this review directory.

## Bottom line

The arithmetic is clean. Every reported number matches the saved outputs, the paired partitions are exact, and the per-patient results reproduce exactly from the current code and cohort. The problems are interpretive and sit in the false-alarm conditions, which supply the paper's most striking numbers (Type 3 41.6%, 59.4% of measured RTM). Most of that Type 3 comes from people whose true counts never met the entry rule in the selected window, and a further slice comes from comparing floored counts with an unfloored reference. Neither fact is wrong in itself, since the paper does say it applies no true-count eligibility filter and that flooring can bias corrected counts. But a reader of the abstract will take "Type 3 affected 41.6% of eligible participants" to mean that measurement error created RTM among genuinely eligible trial participants, and the data do not support that reading. I would fix R1 to R3 before submission. R4 matters for the data-availability statement. The rest are smaller.

## Findings, ranked by severity

### R1. At the false-alarm settings, most Type 3 cases are participants whose true counts fail the entry rule

- Status: confirmed (saved flags plus true daily counts; subsample estimate for the same-window figures).
- Where: Abstract Results, "Type 3 affected 7.7% of eligible participants. At one false alarm/day, corresponding values were 69.9% and 41.6%; Type 3 represented 59.4% of measured RTM cases." Results 3.4, "Type 3 affected 41.6% of eligible participants". Methods 2.4, "without an additional true-count eligibility filter". Table 1 and Table S2.
- Code: `rtm_anatomy/rtm123.py:780-792` selects on detector counts, then `paired_rtm_at_window` (lines 371-412) classifies true counts in that window with no eligibility check on true counts.
- Evidence (my scripts `opus_same_window_true_eligibility.py`, `opus_flag_analysis.py`):

  | Condition | Selected who meet entry rule on true counts, same window | Share of Type 3 from those who do not | Type 3 among same-window true-eligible |
  |---|---|---|---|
  | Sensitivity 70% | 100.0% | 0% | 7.6% |
  | FAR 1/month | 75.9% | 60.6% | 4.0% |
  | FAR 1/week | 60.8% | 75.9% | 8.2% |
  | FAR 1/day | 39.7% | 85.1% | 15.5% |

  Random subsample of 100,000 potential participants (seed 5); FAR 1/day has 98,530 selected, so sampling error is about 0.2 percentage points. Full-cohort figures using the looser "eligible on true counts in any window" test: 34.2% of FAR 1/day selected participants never qualify on true counts in any window, and they supply 52.1% of Type 3 cases. Among FAR 1/day Type 3 cases, 67.0% have a true baseline at or below the true reference, so true RTM is impossible for them whatever happens in the test period; 23.6% have zero true seizures in the baseline window; the median true reference is 1.56 per month.
- Why it matters: in the false-alarm conditions, Type 3 mostly counts false enrollment, not measurement altering the course of truly eligible patients. Among people who would have qualified on true counts, Type 3 at one false alarm/day is 15.5%, not 41.6%. The abstract's word "eligible" means detector-eligible, which is easy to misread. The sensitivity conditions are not affected, because binomial thinning can only lower counts, so anyone who qualifies on measured counts also qualifies on true counts.
- Minimal fix: compute the same-window true-eligibility split on the full cohort from the saved `first_start` arrays (no simulation rerun is needed; my subsample script does it in seconds per 100,000). Report it in Results 3.4 and add two columns to Table S2: Type 3 among same-window true-eligible participants, and the share of Type 3 from participants failing the rule on true counts. In the abstract, say "detector-selected participants", and add one clause such as "most measurement-only cases at this setting were participants whose true counts did not meet entry criteria".
- Not established: full-cohort values for the same-window split (subsample only).

### R2. In the false-alarm conditions the measured-scale reference does not match the floored corrected counts

- Status: confirmed inconsistency; effect size quantified on a 50,000-patient replay.
- Where: Methods 2.4, "Corrected measured counts were compared with this reference multiplied by sensitivity". Limitations 4.4, "Monthly flooring can raise expected corrected counts above the sensitivity-scaled true reference." Discussion 4.2, "Paired classifications require a stated truth model and compatible reference scales."
- Code: `rtm_anatomy/rtm123.py:386` sets the measured reference to `sensitivity * true_total / months`. Lines 699-701 subtract the expected monthly alarm count and floor at zero. For sensitivity conditions s times R equals the expected measured monthly count given the true history, so the scales match exactly. For false-alarm conditions the expected corrected count given the true history is E[max(x + N - c, 0)], which exceeds R whenever months have few true seizures. The code uses R.
- Evidence: in the saved full-cohort output, the mean measured test rate minus the reference among selected participants is +1.09 per month at FAR 1/day (reference mean 6.89, so about 16%), +0.17 at 1/week, +0.03 at 1/month, and about 0 for the sensitivity and perfect-detector conditions. My replay (`opus_reference_replay.py`) reclassified measured RTM in the same selected windows against the matched reference (the 36-month mean of the exact expected corrected count per month, computed from Poisson and binomial probabilities):

  | Condition (50,000 subsample) | Measured RTM, code | Measured RTM, matched ref | Type 3, code | Type 3, matched ref | True-only, code to matched |
  |---|---|---|---|---|---|
  | FAR 1/day | 69.6% | 63.4% | 41.2% | 37.0% | 5.7% to 7.8% |
  | FAR 1/week | 64.0% | 63.2% | 20.6% | 20.2% | 4.6% to 5.0% |
  | FAR 1/month | 56.3% | 56.2% | 7.7% | 7.7% | 3.7% to 3.7% |
  | Sensitivity 70% | 58.9% | 58.9% | 8.0% | 8.0% | 4.8% to 4.8% |

  Using the observed corrected 36-month measured mean as the reference gives similar results (FAR 1/day: 64.2% measured RTM, 37.3% Type 3). The subsample's code-reference values (69.6%, 41.2%) agree with the full-cohort 69.9% and 41.6% within sampling error.
- Why it matters: about 6 percentage points of the headline measured RTM and about 4 points of Type 3 at one false alarm/day come from the reference choice, not from the measurement process. The paper's own Discussion asks for compatible reference scales. The disclosure in 4.4 states the direction of the bias but not that it moves a headline number.
- Minimal fix: either define the measured reference as the expected corrected count given the true history (the exact analogue of s times R) and rerun the classification step only, or keep the current definition and add the matched-reference values as a sensitivity row in Table S2 with one sentence in Results 3.4 and Limitations. The conclusions survive either way.
- Not established: full-cohort values under the matched reference.

### R3. Type 3 prevalence mixes selection-driven RTM with plain outcome misclassification, and the abstract reports it without the offsetting true-only group

- Status: confirmed; partly disclosed.
- Where: Abstract Results, "At 70% sensitivity, observed RTM was 59.0% and Type 3 affected 7.7% of eligible participants." Introduction, "We distinguish three operational forms of RTM". Table S3 has Type 3 but no true-only or net column.
- Evidence: under fixed enrollment, where nobody is selected on measured counts, measurement still produces measured-only and true-only flips, and true-only dominates (`opus_extra_checks.py`; fixed true RTM equals perfect-detector RTM in the same window, which I verified per patient):

  | Fixed enrollment | Type 3 (measured only) | True only | Net, pp |
  |---|---|---|---|
  | Sensitivity 90% | 3.3% | 4.3% | -0.9 |
  | Sensitivity 80% | 4.5% | 6.8% | -2.3 |
  | Sensitivity 70% | 5.4% | 9.1% | -3.7 |
  | FAR 1/month | 3.7% | 5.8% | -2.1 |
  | FAR 1/week | 6.1% | 12.3% | -6.3 |
  | FAR 1/day | 9.4% | 21.6% | -12.2 |

  Under condition-specific enrollment at 70% sensitivity, Type 3 is 7.7%, true-only 4.8%, net 2.9 points (Table S2 and saved CSV).
- Why it matters: noisy counts flip the RTM rule in both directions even with no selection on noise. So Type 3 prevalence is a discordance rate, and only part of it reflects regression of selected measurement noise. Calling it a "form of RTM" and reporting 7.7% alone in the abstract invites readers to treat it as RTM added by the detector. The Discussion does say measurement can remove RTM classifications and that Type 3 is not the net difference. That caveat never reaches the abstract or Table S3, though.
- Minimal fix: add "True only %" and "Net pp" columns to Table S3. In the abstract, pair the 7.7% with the 4.8% true-only figure or the 2.9-point net difference. Consider describing Type 3 in the abstract as "measured-only RTM classification".

### R4. The analysis cannot be reproduced from public sources as described

- Status: confirmed for the simulator module and code state; disclosed in part ("Public release of the revised files remains pending").
- Where: Methods 2.1, "CHOCOLATES, an open-source simulator"; Data and code availability.
- Evidence:
  - `rtm_anatomy/rtm123.py:100` loads `realSim_turbo.py` from the CHOCOLATE checkout. In the local checkout that file is untracked (`git status`: `?? realSim_turbo.py`) and absent from `origin/main`. The public GitHub page for GoldenholzLab/CHOCOLATE, fetched 2026-11-12, lists `realSim.py` but not `realSim_turbo.py`. The turbo file differs from `realSim.py`: it threads a seeded generator through every call and draws gamma rates in float32. So the public `realSim.py` cannot regenerate the cohort.
  - The revised analysis code is uncommitted. The public anatomy_of_RTM repository shows 3 commits and lacks the paired Type 3 code. `run_manifest.json` records `git_sha` 1a4955e, which does not contain the code that produced the outputs. The recorded `analysis_source_sha256` (fd926604...) does match the working file, so provenance is intact locally.
  - `outputs/` is gitignored, so the 2.16 GB cohort is not public. `cohort_metadata.json` has no generation fingerprint. The original manifest shows the cohort was generated with Python 3.13.2 (Anaconda) and does not record the NumPy version or simulator hash. The `realSim_turbo.py` modification time (2026-01-09) predates cohort generation (2026-05-31), which suggests, without proving, that the same simulator source was used.
  - Minor hygiene: the public repository contains a Word lock file `~$m123_v2.docx`.
- Why it matters: Seizure readers and reviewers following the stated URLs would get a simulator that cannot run this code, and an analysis repository without the revised method.
- Minimal fix: commit and tag `realSim_turbo.py` in CHOCOLATE, commit and tag the analysis code, record the cohort-generation environment (or deposit the cohort with its SHA-256), and archive both with a DOI before submission or at acceptance. Update the availability statement to cite the tag or DOI. Remove the lock file from the public repository.

### R5. Median percentage change sits on a lattice point for three conditions

- Status: confirmed.
- Where: Table 1 MPC column (Sensitivity 80% 33.3, Sensitivity 70% 33.3, FAR 1/month 33.3) and Figure 2D; Methods 2.4, "approximate order-statistic intervals describe the median".
- Evidence: percentage change is 100(1 - 2T/3B) on integer totals, so 33.33% occurs whenever the 3-month test total equals the 2-month baseline total. That single value holds 5.4%, 5.6% and 4.8% of selected participants in those three conditions, and the median falls inside the tie. The saved order-statistic intervals are degenerate (33.33 to 33.33 for both sensitivity settings). Mean percentage change keeps rising where the median is flat: 17.0% at 80% and 19.1% at 70% sensitivity. No median interval appears in the manuscript or supplement, although Methods says intervals describe the median. (Mean percentage change is not a recommended replacement endpoint here; I quote it only to show the plateau is an artifact.)
- Why it matters: the flat 33.3 run in Table 1 and Figure 2D looks like a plateau in apparent improvement. It is a discreteness artifact.
- Minimal fix: add a Table 1 footnote noting that MPC is computed on discrete count ratios and that identical values can reflect a shared tie, or report a mid-distribution (interpolated) median. Either report the median intervals or drop the sentence promising them.

### R6. Transient-state results omit promised strata and hide how large the rate changes are

- Status: confirmed; partly disclosed.
- Where: Methods 2.3, "We stratified results by overlap with baseline or test and by the direction of the sampled rate change." Results 3.2 reports only the baseline-only and neither strata. Introduction and Figure 1 describe Type 1 as "return after a temporary state worsening".
- Code: `build_type1_diary` (`rtm123.py:709-743`) draws a new rate from the population distribution, independent of the patient's own rate; `type1_overlap_rows` (lines 947-1004) writes all strata to `type1_overlap_summary.csv`.
- Evidence: direction strata exist only in the CSV. Baseline-only overlap: higher-rate replacements 122,992 (RTM 98.9%, MPC 93.3%), lower-rate 7,297 (RTM 30.6%, MPC -5.6%). Test-only overlap (55,876; RTM 39.6%, MPC 40.0%) and baseline-and-test overlap (23,659; RTM 68.7%, MPC 38.5%) are unreported; test-only higher-rate replacements have MPC -8.3%. The replacement-to-original rate ratio has median 1.00 and 5th to 95th percentiles 0.07 to 14.4; 15.5% of patients get a change above 10-fold or below 0.1-fold. In the baseline-only stratum, 77.8% of participants would not qualify under the reference condition, their median latent rate is 1.43 per month, and the median ratio is 6.5. 72% of transient-condition participants (546,355) had no overlap at all.
- Why it matters: the 95.1% and 92.6% baseline-only figures mostly describe low-rate patients made eligible by a roughly sixfold temporary rate. Limitations do say the replacement "was not a data-derived illness model", but readers cannot judge the size of the perturbation, and the Methods promise of direction strata is unmet.
- Minimal fix: add a supplementary table of overlap by direction from the existing CSV, state the rate-ratio distribution in Methods 2.3, and describe the Type 1 condition as a temporary rate change (higher or lower) rather than worsening, or report the worsening subset as the Type 1 estimate.

### R7. The 25-day rule gets no alarm correction at one alarm per month or week

- Status: confirmed; described technically but easy to miss.
- Where: Methods 2.3, "For the 25-day rule only, daily recorded counts were reduced by the rounded expected daily alarm count and floored at zero."
- Code: `rtm123.py:702`, `daily_remover = int(np.round(far_per_day))`, which is 0 for 1/30 and 1/7 per day and 1 for 1 per day.
- Why it matters: at 1/month and 1/week, raw false alarms break up event-free runs, which makes the 25-day rule easier to pass. This feeds R1: 24% of FAR 1/month participants fail the entry rule on true counts in their selected window.
- Minimal fix: say explicitly that the rounded correction is zero at 1/month and 1/week, so alarms enter the 25-day check uncorrected at those settings.

### R8. The eligibility rule matches one cited trial, not all three

- Status: confirmed against primary sources.
- Where: Methods 2.2, "The reference eligibility rule reflected focal-epilepsy trials ... no baseline event-free interval longer than 25 days [1,13,14]".
- Evidence: the ClinicalTrials.gov record for NCT01866111 (ref [14], Krauss 2020) requires at least 8 partial seizures in the 8-week baseline, at least 3 in each 4-week segment and no seizure-free interval longer than 25 days, which matches the simulation. Ref [13] (Chung 2020, PMC full text) required at least 3 seizures per month and no consecutive 21-day seizure-free period. The simulation uses 30-day months where the trials use 4-week segments.
- Minimal fix: cite [14] for the specific rule, cite [13] for the general design, and note the 30-day month convention.

### R9. Labels drift between the main text, supplement and Figure 1

- Status: confirmed, minor.
- Evidence: Supplement row labels read "Type 1: transient 2-month mSF change" and "Type 2: eligibility threshold 8/month". "mSF" is never defined, and the "Type 1/Type 2" prefixes imply that all RTM in a condition belongs to that type, which the main text explicitly avoids (72% of transient-condition participants had no overlap, so most of their RTM is natural-variability RTM). Table 1 uses different labels ("Transient rate change", "Entry threshold 8/month"). Figure 1 headers say "RTM 1/2/3" while the text says "Type 1/2/3". The Figure 1 Type 3 panel draws one "ref" line for both scales; the caption does not mention that measured counts use a sensitivity-scaled reference.
- Minimal fix: use the Table 1 condition labels in Tables S1 to S3, define or drop "mSF", and align the Figure 1 headers and caption with the text.

### R10. Small wording and citation gaps

- Status: confirmed, minor.
- Methods 2.2, "rolling 2-month baseline windows beginning at month 0 and ending at month 31": the code (`rtm123.py:314-318`) uses start months 0 to 31, with the last baseline in months 31 and 32. Suggest "with start months 0 to 31".
- Introduction, "Previous seizure-trial simulations quantified eligibility-related RTM." has no citation. Reference [1] fits.

## Limitations already adequately disclosed

I do not count these as errors. The manuscript states each clearly enough.

- Synthetic diaries treated as truth, and CHOCOLATES calibration data may themselves contain reporting error (4.4).
- The internal 36-month reference includes the trial window, unlike the separate reference diary in related work (2.4, 4.3, 4.4).
- Detector performance is constant across people and time, alarms are Poisson and independent, and the expected-alarm correction is idealized (2.3, 4.4).
- No treatment arm, no randomized contrast, no power analysis (abstract, 2.4, 4.4).
- The paired analysis was added after the original analysis and was not preregistered (2.1, 2.4).
- Monte Carlo intervals do not capture model uncertainty (2.4).
- Detector seeds are condition-specific and not nested across settings (revision protocol; immaterial at this sample size).
- The fixed-enrollment comparison is not enrollment under the imperfect detector (2.2, Table S3 note).

## Checks that passed

- All 245 numeric checks matched: every cell of Table 1 and Tables S1 to S3, and every number in the abstract and Results, including 95.1%, 92.6%, 51.0% and 25.9% from the transient overlap CSV (`opus_number_checks.json`, 0 failures).
- Paired partitions are exact in every row: both + measured-only + true-only + neither = selected n; measured RTM = both + Type 3; true RTM = both + true-only; net difference = Type 3 minus true-only = measured RTM % minus true RTM %.
- Counts recomputed directly from the per-patient flag arrays match the CSV for all nine conditions.
- Replay with the current code reproduced every per-patient flag in a 50,000-patient subsample across five detector conditions and a 3,000-patient subsample of the transient condition (0 mismatches; simulator hash b038553d... matches the manifest).
- The current `rtm_anatomy/rtm123.py` hash equals `analysis_source_sha256` in `run_manifest.json` and in every flag cache.
- The integer RTM comparison in `rtm_from_totals` (`rtm123.py:349-368`) is algebraically equivalent to "B above reference and |T - reference| < B - reference" with strict inequalities; the alarm corrections are exact rationals (30/7 at one per week).
- The Wilson interval code is correct; zero-count rows show 0.0 to 0.0 with an accurate note.
- Fixed enrollment uses exactly the perfect-detector participants and baseline windows in all six measurement conditions.
- Embedded figures are byte-identical to `outputs/rtm123_type3_1m/rtm123_explainer.png` and `output/seizure_figures/Figure_2.png`. `anatomy_of_RTM_Seizure_Figure_1.pdf` is identical to the saved explainer PDF. `scripts/build_seizure_figures.py` plots straight from the reviewed CSV; the bar heights in Figure 2 agree with Table 1.
- The RTM definition in the code matches reference [1] (baseline above the typical rate, test closer to it, above or below). Metadata for references [1], [13] and [14] are correct.
- The abstract count (207 words) is correct; the main text is 1,758 words excluding headings, consistent with the stated 1,809 if headings are counted.
- All 23 unit tests pass. Zotero fields are live (11 citation fields and one bibliography field). Highlights are consistent with the manuscript.

## What I could not establish

- Full-cohort values for R1 and R2. I report subsample estimates with sampling error near 0.2 percentage points. Both can be computed without rerunning the simulation.
- Native Word rendering, pagination and Zotero display. I used read-only OOXML only and did not open Word.
- Whether `realSim_turbo.py` will be pushed before submission, and which NumPy version generated the cohort.
- Journal-specific limits for Seizure (word, reference and figure counts) were not rechecked.

## Evidence files (all in this folder)

- `opus_extract_docx.py`, `opus_anatomy_of_RTM_Seizure*_body.txt`, `*_fields.txt`, `*_extra.txt`: read-only extraction.
- `opus_media/`: embedded figure PNGs.
- `opus_check_numbers.py`, `opus_number_checks.json`: document-to-CSV checks.
- `opus_flag_analysis.py`, `opus_flag_analysis.json`: recomputation from flags, MPC ties, floor bias, any-window true eligibility. (Its Type 1 ratio block did not run because of a path bug; `opus_extra_checks.py` covers that.)
- `opus_reference_replay.py`, `opus_reference_replay_50k.json`: exact replay and alternative references (R2).
- `opus_same_window_true_eligibility.py`, `opus_same_window_true_eligibility.json`: R1.
- `opus_extra_checks.py`, `opus_extra_checks.json`: fixed-enrollment true-only (R3) and transient rate ratios (R6).
- `opus_type1_replay.py`, `opus_type1_replay.json`: transient-condition replay.

## External sources checked

- Krauss GL et al. Lancet Neurol 2020, via PubMed: https://doi.org/10.1016/S1474-4422(19)30399-0. Eligibility from ClinicalTrials.gov NCT01866111: https://clinicaltrials.gov/study/NCT01866111
- Chung SS et al. Neurology 2020, via PubMed Central PMC7357293: https://doi.org/10.1212/WNL.0000000000009530
- Goldenholz DM, Goldenholz EB, Kaptchuk TJ. Epilepsia 2023, via PubMed Central PMC10592227 (RTM definition): https://doi.org/10.1111/epi.17730
- GoldenholzLab/CHOCOLATE public repository listing: https://github.com/GoldenholzLab/CHOCOLATE
- GoldenholzLab/anatomy_of_RTM public repository listing: https://github.com/GoldenholzLab/anatomy_of_RTM
