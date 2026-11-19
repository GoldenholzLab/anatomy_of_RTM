# Independent scientific and computational review

Reviewed on November 12, 2026, in `/Users/dgoldenh/Documents/GitHub/anatomy_of_RTM`.

The current saved Seizure manuscript and supplement are numerically consistent with the saved revised analysis. I found no confirmed error in their headline numerical results, denominators, paired Type 3 classification, strict RTM arithmetic, or fixed-enrollment accounting. The conclusions stay within the scope of a descriptive simulation and explicitly avoid claims about randomized treatment contrasts or power.

There are three confirmed reporting or reproducibility gaps and one scientific robustness concern. None requires discarding the reported primary analysis. The robustness concern is already acknowledged in the manuscript, but its numerical size deserves attention.

## Scope, independence, and source identity

The authoritative documents were:

| Saved file | SHA-256 |
| --- | --- |
| `anatomy_of_RTM_Seizure.docx` | `6119f8107c62b4de9f48c852894f795cbcbee88bfc9804ef68da64bd63b40ce0` |
| `anatomy_of_RTM_Seizure_Supplement.docx` | `cd7195edc9e75b6a171a6b4ca9eb4f57fa02d597b90ffa4bc8a19617f0699110` |

I extracted body text, tables, field instructions, headers, footers, footnotes, and math elements using ZIP/lxml. Visible cached field results were analyzed as manuscript text. Zotero instruction JSON was retained separately and was not counted as prose or bibliography text. The main body contains 11 Zotero citation fields and one Zotero bibliography field. Neither document contains native OMML equations. The explicit RTM inequality is in the embedded Figure 1 raster, which I inspected. There are no tracked insertions or deletions in either document body.

I read the current analysis code, result CSVs, manifests, notebook, and patient arrays. I did not read the earlier JCE/revised manuscripts, prior review reports, or prior reviewers' evidence. README statements about earlier reviews were not used as verification. No agents or delegates were started.

I did not open Word or a local PDF, edit a DOCX, refresh Zotero, invoke LibreOffice, or run the million-person simulation. All new evidence is in this `sol` directory. The 23 existing tests ran with a separate Matplotlib cache and temporary fixture directories. The two authoritative documents, all snapshotted scripts/tests, the notebook, and saved revised CSV/JSON outputs remained byte-identical. The retained raw cohort hashes also match the run manifest.

The fresh calculations used Python 3.13.2 and NumPy 2.2.5. The saved production manifest records Python 3.12.14 and NumPy 2.5.4. The sampled raw-history and generation replay agreed across these environments, but that does not establish agreement for every possible random draw or reproduce the historical environment.

## Ranked concerns

| ID | Severity | Status | Concern |
| --- | --- | --- | --- |
| SOL-01 | Moderate | Confirmed reproducibility gap | The exact simulator dependency is an untracked external file; historical cohort-generation provenance is missing. |
| SOL-02 | Moderate | Plausible interpretation risk, with confirmed sensitivity | Flooring changes the expected measured reference. The primary Type 3 prevalence depends materially on the chosen reference. This limitation is already disclosed. |
| SOL-03 | Low to moderate | Confirmed reporting gap | The Methods promise direction-stratified transient-state results, but those results and stratum denominators are absent from the submitted documents. |
| SOL-04 | Low | Confirmed reporting gap | Median confidence intervals are computed and described in Methods but are absent from the main and supplementary tables. |

### SOL-01. Exact simulator source is not yet an obtainable, immutable dependency

**Location.** Methods 2.1, "We generated 1,000,000 synthetic patients with CHOCOLATES"; Methods 2.4, "source and output hashes, and reproduction instructions accompany the revised analysis files"; Data and code availability, "pending public release."

**Code and saved evidence.** `rtm_anatomy/rtm123.py:84-105` loads the external sibling file `CHOCOLATE/realSim_turbo.py`; lines 163-178 call its wrapper and rate sampler. The run manifest records the source hash at `outputs/rtm123_type3_1m/run_manifest.json:141-144`, but its historical `cohort_generation_fingerprint` is null at line 19. `git -C /Users/dgoldenh/Documents/GitHub/CHOCOLATE status --short -- realSim_turbo.py` returns `?? realSim_turbo.py`; `git ls-files` does not list it. The simulator source is outside this analysis repository. README lines 15-24 explain the dependency and record versions but do not provide an immutable retrieval target. The exact source hash is `b038553df164160290b427e577ba53cb6b983db38f00a281f9a773a91a1d6b99`.

**Why it matters.** A repository name and a source hash identify a dependency but do not supply its bytes. A clean checkout cannot be assumed to contain this particular wrapper or its generator behavior. This matters for new-cohort generation and the Type 1 replacement segments. The original cohort has retained hashes and seeds, but the exact historical generator source/environment was not recorded when it was created. A current replay is supporting evidence, not historical provenance.

**Minimal corrective action.** Before public release, archive or vendor the exact simulator file, its license, and an installable environment specification, with an immutable identifier. Describe it as the exact implementation used here. Preserve the null historical fingerprint as unknown; do not backfill a claim of original provenance. Retain the raw cohort or provide a clearly labeled regeneration check and its limits.

**Verification performed.** I checked the external file's Git status and hash, compared it with the local `realSim.py`, verified analysis and cohort hashes against the run manifest, and freshly regenerated 600 sampled original histories and latent rates. Every sampled history and rate matched. Fresh Type 1 segment and condition replay also matched. Evidence is in `preservation_and_provenance.json`, `independent_array_audit.json`, and `raw_replay_current_numpy.json`.

**What remains unestablished.** I did not test a clean public installation or verify what any future release will contain. I cannot recover the missing historical generator fingerprint. The manuscript honestly says release is pending, so this is a release/reproducibility gap, not a false claim that the revised files are already public.

### SOL-02. Quantify the disclosed flooring/reference dependence

**Location.** Methods 2.3, "negative corrected counts were set to zero"; Methods 2.4, "Corrected measured counts were compared with this reference multiplied by sensitivity"; Results 3.4 and abstract, Type 3 at one false alarm/day; Discussion 4.4, "Monthly flooring can raise expected corrected counts above the sensitivity-scaled true reference."

**Code and saved evidence.** `rtm_anatomy/rtm123.py:684-704` thins counts, adds independent Poisson alarms, subtracts the expected monthly alarm count, and floors each month at zero. Lines 384-403 use the sensitivity-scaled finite true-count mean for the measured RTM reference. The primary comparison is implemented as described. At full sensitivity and one alarm/day, a month with true count `t` has corrected count `max(t + P - 30, 0)`, where `P` is Poisson with mean 30. Its conditional expectation generally exceeds `t`. Thus the truth-derived reference is deliberately not the expected monthly value of the floored measured process.

**Why it matters.** The operational Type 3 label includes effects of measurement noise, correction, and the chosen reference scale. It should not be interpreted as an estimate invariant to reasonable measurement-reference conventions. This is distinct from whether the classifier is coded correctly, which it is.

**Targeted independent calculation.** I replayed one-alarm/day measurement for a new random sample of 12,000 retained participants, using seed 633791. All saved first-window and primary classifications matched. There were 11,845 selected participants. Holding those people, windows, measured baseline/test values, and true-count RTM labels fixed gave:

| Measured-count reference | Measured RTM % | Type 3 % |
| --- | --- | --- |
| Primary finite true-count reference | 69.59 | 41.00 |
| Average conditional expectation of the floored measured counts over the retained true monthly path | 63.09 | 36.82 |
| Realized floored measured full-history mean | 63.84 | 37.14 |

The conditional-expectation reference changed 770 measured RTM labels. Its mean upward shift from the true reference was 1.08 events/month among selected participants. I verified its Poisson expectation formula against direct probability summation at eight true-count values. These are exploratory sampled sensitivities, not replacement full-cohort estimates. The alternative references change the estimand and do not establish that the manuscript's chosen definition is invalid.

An additional check retained the primary reference but removed the test-month floor. Selection is unaffected by removing the monthly floor because eligibility already requires each baseline month to be at least 3. In this sample measured RTM was 65.96%, Type 3 was 38.85%, and MPC was 55.85%, versus 45.95% for the primary floored MPC. Negative corrected values make this an algebraic sensitivity rather than a recommended clinical endpoint.

**Minimal corrective action.** Add a small, explicitly labeled sensitivity analysis or explain near the headline numerical result that the percentage is conditional on the correction and reference convention. Preserve the primary analysis. The conclusion already avoids transporting the number to other designs, so no claim of a general detector effect needs to be retracted.

**Verification performed.** New code in `correction_sensitivity.py`, results in `correction_sensitivity.json`. The script uses independent selection and classification calculations and exact integer comparisons for rational-reference cases. It does not call the production detector or classifier.

**What remains unestablished.** These checks do not show which reference is most useful clinically, quantify full model uncertainty, or estimate effects on randomized contrasts. The source limitation is already adequately disclosed in Methods 2.3 and Discussion 4.4. The added concern is its demonstrated numerical size, not an undisclosed computational error.

### SOL-03. Deliver the transient-state direction strata that Methods describe

**Location.** Introduction, "Type 1 describes return after a temporary state worsening"; Methods 2.3, "We stratified results by overlap with baseline or test and by the direction of the sampled rate change"; Results 3.2 reports only pooled baseline-only and neither-overlap results. Supplementary Tables S1-S3 contain no overlap/direction table.

**Code and saved evidence.** `rtm_anatomy/rtm123.py:709-743` replaces a random two-month interval using a newly sampled rate and process parameters. Lines 926-1002 classify overlap and rate direction. The saved `outputs/rtm123_type3_1m/type1_overlap_summary.csv` contains the missing strata. `scripts/prepare_seizure_submission.py:215-231` builds only paired-classification, prevalence, and fixed-enrollment supplementary tables.

**Why it matters.** This condition includes both higher and lower sampled rates and intervals outside the trial. Its pooled 58.3% observed RTM is not a Type 1 case prevalence. Among 756,179 selected participants, 546,355, or 72.25%, had replacement intervals overlapping neither baseline nor test. Among the 130,289 baseline-only overlaps, 122,992, or 94.40%, had higher sampled rates. The omitted direction results are informative:

| Baseline-only replacement | Selected n | Observed RTM % | MPC % |
| --- | --- | --- | --- |
| Higher sampled rate | 122,992 | 98.93 | 93.33 |
| Lower sampled rate | 7,297 | 30.64 | -5.56 |

The text already discloses mixed rate directions, resampled cycles/cluster status, and changing enrollment. Those disclosures prevent a strong causal misreading, but readers cannot assess the promised stratification from the submission documents alone. The three named forms are also operationally asymmetric. Types 1 and 2 are perturbation scenarios here; Type 3 has an individual paired classifier. No individual Type 1 or Type 2 flags are saved.

**Minimal corrective action.** Add an overlap-by-direction table to the supplement, including selected denominators. Identify 58.3% as overall observed RTM under a transient-process perturbation. Explicitly distinguish a perturbation scenario from a measured Type 1 prevalence. No new simulation is needed.

**Verification performed.** I independently reconstructed overlap masks and sampled-rate direction from all million Type 1 patient records and the retained latent rates. All 12 eligible overlap/direction strata matched the saved CSV. I also inspected the complete extracted main/supplement text and all tables.

**What remains unestablished.** The analysis does not identify what fraction of individual RTM cases was caused by temporary worsening. It does not claim an additive causal decomposition. This is a reporting and terminology concern, not an error in the saved 58.3%, 95.1%, or 92.6% values.

### SOL-04. Median intervals are not included in the submitted tables

**Location.** Methods 2.4, "approximate order-statistic intervals describe the median"; Table 1 contains only MPC point estimates; Table S3 also contains only MPC point estimates. Table S2 gives Type 3 Wilson intervals, not median intervals.

**Code and saved evidence.** `rtm_anatomy/rtm123.py:428-440` computes the approximate order-statistic intervals; lines 849-892 save them. They are present as `MPC_ci_lo`, `MPC_ci_hi`, `fixed_MPC_ci_lo`, and `fixed_MPC_ci_hi` in `condition_summary.csv`. `scripts/prepare_seizure_submission.py:217-231` omits them from the supplementary DOCX.

**Why it matters.** The submitted documents describe an uncertainty analysis without showing its median results. The omission is not always negligible at the displayed precision. For FAR 1/month, the primary MPC interval is 31.97% to 33.33%. For FAR 1/day, the fixed-enrollment interval is 17.39% to 17.95%. Discrete seizure counts explain some wide or degenerate median intervals even at this sample size.

**Minimal corrective action.** Add the already computed median intervals to a supplementary table, including intervals for fixed enrollment and its positive-baseline denominator. Retain the statement that they quantify Monte Carlo precision only.

**Verification performed.** I independently sorted every selected condition's saved percentage changes and recomputed the production order-statistic bounds. All primary median bounds matched. Fixed-enrollment point estimates and denominators also matched. I checked every DOCX table for interval columns.

**What remains unestablished.** I did not evaluate alternative exact median interval conventions or claim nominal exact coverage for the approximate method. No point estimate is wrong because of this omission.

## Quantitative results that pass

All nine rows below were independently recalculated from full saved patient arrays and compared with Table 1. All four result tables, Table 1 and Tables S1-S3, passed the numerical checks. Every numerical cell in S1-S3 matched the corresponding calculation or saved summary, including displayed rounding.

| Condition | Eligible n | Measured RTM % | True RTM % | Type 3 % | MPC % |
| --- | --- | --- | --- | --- | --- |
| Perfect detector | 649,098 | 53.8 | 53.8 | 0.0 | 26.7 |
| Transient process replacement | 756,179 | 58.3 | 58.3 | 0.0 | 36.8 |
| Entry threshold 8/month | 404,268 | 57.9 | 57.9 | 0.0 | 29.4 |
| Sensitivity 90% | 621,144 | 55.4 | 54.5 | 3.9 | 28.5 |
| Sensitivity 80% | 589,758 | 57.1 | 55.3 | 5.9 | 33.3 |
| Sensitivity 70% | 551,890 | 59.0 | 56.1 | 7.7 | 33.3 |
| FAR 1/month | 695,712 | 56.5 | 52.3 | 7.8 | 33.3 |
| FAR 1/week | 769,320 | 64.2 | 48.1 | 20.8 | 39.7 |
| FAR 1/day | 985,321 | 69.9 | 34.1 | 41.6 | 46.0 |

The principal computational checks passed as follows:

- Eligibility yield uses the million-person potential cohort. RTM and primary MPC use condition-selected participants. Each condition has exactly the stated first-window range, month 0 through month 31, followed by a two-month baseline and three-month test. The scanner uses observed/corrected monthly values and the documented daily event-free rule, not future test outcomes. All first-window histogram counts match the saved CSV.
- The RTM rule is `B > R` and `abs(T - R) < B - R`, where B and T are monthly average counts in baseline and test and R is the defined reference. Independent integer cross-products reproduce every saved selected measured and true label. Exact ties fail. The seven-day alarm correction retains the rational monthly expectation of 30/7.
- The four paired groups are exclusive and sum to selected n for all nine conditions. Type 3 is measured RTM with no true-count RTM at the same window. There is no extra true-count eligibility filter. At perfect detection, every measured/true label agrees and Type 3 is exactly zero.
- At FAR 1/day, the paired counts are both 279,589; measured only 409,581; true only 55,966; neither 240,185. Measured RTM is 689,170/985,321 = 69.9437%. Type 3 prevalence is 409,581/985,321 = 41.5683%. Its share of measured RTM is 409,581/689,170 = 59.4311%. The net difference is 100 times 353,615/985,321 = 35.8883 percentage points. The main text distinguishes all these quantities correctly.
- All primary measured baselines are positive. Fixed measurement conditions retain exactly the perfect-detector 649,098 participants and their original baseline windows, even if imperfect measurement would fail eligibility. At sensitivity 70%, there are 8 zero measured baselines and 649,090 finite percentage changes. At FAR 1/day, there are 17,608 zero baselines and 631,490 finite percentage changes. Those exclusions apply only to MPC. Fixed RTM and Type 3 retain the full fixed denominator, as stated.
- Every selected true-count reference, baseline, and test statistic in the eight conditions without replacement matches the raw original daily cohort. Full-array fixed Type 3 labels also agree with the true RTM classifications reconstructed at the retained perfect-detector windows. The 600-person raw replay checks measured and true calculations, fixed windows, and Type 1 histories directly.
- Wilson intervals match an independently written Wilson calculation for all conditions. The zero-Type-3 intervals round to 0.0% to 0.0%; their tiny positive mathematical upper bounds are accurately explained in S2. This is not evidence of unexplained measurement disagreement under perfect detection.
- All primary medians and approximate median bounds match the saved percentage changes. Identical 33.3% medians across several conditions are consistent with discrete count ratios; they are not a copy/paste error.

## Figures, mathematical semantics, and notebook

I extracted and inspected both embedded raster figures. Figure 1 is 1500 by 1500 pixels and Figure 2 is 2250 by 1650 pixels. They are byte-identical to `outputs/rtm123_type3_1m/rtm123_explainer.png` and `output/seizure_figures/Figure_2.png`, respectively.

Figure 1's three examples satisfy their stated RTM semantics. In the Type 3 example, the true bars lie at the reference while the measured baseline is above it and measured test is closer. The displayed strict inequality agrees with the code. The examples are explicitly schematic and do not purport to show a causal partition or cohort-level rates.

Figure 2's panels correspond to the stated denominators and the saved summary values. Panel B compares measured and true RTM within each condition's same selected people and windows. Panel C shows measured-only and true-only prevalences rather than relabeling all imperfect-detector RTM as Type 3. Panel D uses the positive reduction convention. I found no misleading scale truncation or mismatch with the caption. `scripts/build_seizure_figures.py:23-35` loads the reviewed table; lines 59-77 map the relevant rates and medians to the plotted panels.

The current notebook is accurately described as an unexecuted snapshot. All code-cell execution counts are null; its code reloads saved files rather than reproducing the simulations. Its visible main and paired result tables agree with the saved revised outputs. Its assertion on an existing `validation.json` is not an independent rerun of validation. The README makes the snapshot's scope explicit, so this is not an additional finding.

Native Word pagination, field refresh behavior, final equation/display positioning, table splits, and legibility at final printed size were not verified. No concerns about those properties should be inferred from this read-only audit. The parent should use Microsoft Word for any required final display check.

## Scientific interpretation and limits already handled adequately

The manuscript reports an operational indicator of RTM in one realized window, not proof of a causal mechanism in each individual. Its internal reference includes the trial window. Those choices are explicit, and a two-month-versus-three-month rate comparison is implemented consistently.

As a targeted check of self-inclusion, I recomputed every saved selected label using a 31-month reference that excludes the selected baseline and test, while holding selection and windows fixed. Perfect-detector RTM changed from 53.79% to 53.40%; at FAR 1/day, Type 3 changed from 41.57% to 41.40%. These checks support numerical stability to this particular reference exclusion. They do not validate a separate independent diary, a latent expected rate, or another enrollment design. The full results are in `independent_array_audit.json`.

The fixed-enrollment comparison cannot separate membership changes from timing changes within the condition-selected result. The manuscript does not claim that it can. Holding both fixed is a useful descriptive comparison and illustrates why a single common potential cohort does not imply the same trial cohort.

The detector model is an idealized per-event Bernoulli thinning plus independent daily Poisson alarms, with constant performance, no missingness, and a known correction. The text discloses these assumptions and the difference between daily and monthly correction. In the 12,000-person FAR 1/day sample, using recorded events without daily subtraction changed no enrollment windows relative to the implemented daily correction. Using oracle true daily events for the 25-day rule reduced selected n from 11,845 to 9,227 and changed 5,134 window assignments. This is an illustration of the intended selection dependence, not evidence that the stated rule was implemented incorrectly or that oracle enrollment is a practical alternative.

Synthetic diaries are treated as truth despite calibration from imperfect clinical diaries. Temporary replacement also changes process parameters and may decrease the sampled rate. The manuscript says both. It does not claim a clinical illness model, event-level detector validation, independent additive causes, general disease prevalence, or improved randomized-trial efficiency. I do not recommend adding warnings that imply those claims were made.

The simulation is descriptive and synthetic. Absence of p-values, hypothesis tests, a randomized treatment effect, and clinical CONSORT/STROBE/STARD reporting is not an error in this design. Its stated uncertainty concerns Monte Carlo precision, not calibration uncertainty or uncertainty over real clinical populations. A larger simulated cohort would not resolve the model choices in SOL-02.

## Primary-source checks and their limits

Only public reference titles, DOI identifiers, and trial identifiers were searched. No manuscript text or files were uploaded externally.

- The original RTM paper explicitly studies eligibility-related RTM and randomized trial efficiency, whereas the current paper limits itself to within-arm descriptive outcomes. Its eligibility/reference design differs, so the current manuscript correctly warns against direct numerical comparison. [Goldenholz et al., Epilepsia 2023, PubMed](https://pubmed.ncbi.nlm.nih.gov/37505116/).
- The trial registry for the cited dose-response cenobamate trial specifies at least eight qualifying seizures in eight weeks, at least three in each four-week segment, and no seizure-free interval greater than 25 days. This supports a trial-inspired rule. The current simulation explicitly uses 30-day months and rolling re-entry opportunities, so it is not an exact clinical-protocol reproduction. [EU Clinical Trials Register, YKP3089C017](https://www.clinicaltrialsregister.eu/ctr-search/trial/2013-001858-10/PL).
- The other cited cenobamate trial uses at least three qualifying seizures/month and no consecutive 21-day seizure-free interval. The two cited trials therefore should not be represented as sharing every threshold. The current wording, "reflected focal-epilepsy trials," is broad enough; I found no claim of identical rules. [Chung et al., Neurology 2020](https://www.neurology.org/doi/10.1212/WNL.0000000000009530).
- The cited wearable simulation uses a correction for average expected false alarms and explicitly discusses how detector performance changes trial eligibility. It supports the motivation for joint measurement/enrollment analysis; it does not validate the present Type 3 definition or its numerical prevalence. [Goldenholz et al., Epilepsia 2024](https://pmc.ncbi.nlm.nih.gov/articles/PMC11018505/).

The published CHOCOLATES full-text landing page and the older RTM PMC full text were blocked by an automated-access interstitial during open attempts. I did not treat that as a scientific finding. The indexed simulator abstract and the actual local source were accessible, but I did not establish that this exact `realSim_turbo.py` implementation reproduces all original empirical calibration results. I did not exhaustively audit every clinical or contextual-placebo citation, current author disclosures, or journal submission rules.

## Evidence and reproducible review commands

The new full-array audit does not call the production classifier. It checks every selected measured/true label, summary counts/rates/primary median intervals, fixed denominators, raw true-count sufficient statistics, first-window histograms, all four DOCX result tables, and retained input hashes. The new correction sensitivity implements its own detector replay and selection calculations.

The fresh 600-person replay reused the existing `scripts/replay_paired_type3.py`, with a new sample seed and a reviewer-specific evidence destination. That script independently implements detector noise, selection, and rational RTM, but reuses the production Type 1 replacement generator and original generation wrapper. This is fresh evidence using an existing verification implementation, not a reused prior review result or a fully independent simulator validation.

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B output/critical_review_2026-11-12/sol/independent_array_audit.py
PYTHONDONTWRITEBYTECODE=1 python3 -B scripts/replay_paired_type3.py --cohort-dir outputs/rtm123_1m --output-dir outputs/rtm123_type3_1m --evidence output/critical_review_2026-11-12/sol/raw_replay_current_numpy.json --n 600 --seed 927133
PYTHONDONTWRITEBYTECODE=1 python3 -B output/critical_review_2026-11-12/sol/correction_sensitivity.py
PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/Users/dgoldenh/Documents/GitHub/anatomy_of_RTM/output/critical_review_2026-11-12/sol/mpl-cache python3 -B -m unittest discover -s tests -p test_rtm123.py -v
```

These commands write only reviewer artifacts or temporary test fixtures. Do not run `scripts/validate_paired_type3.py` directly against the authoritative output directory for this review; its current implementation overwrites `validation.json`.

Review evidence:

- `input_snapshot.json` and `preservation_and_provenance.json`: source pins, external dependency status, and unchanged-file checks.
- `anatomy_of_RTM_Seizure_extracted.txt` and `anatomy_of_RTM_Seizure_Supplement_extracted.txt`: current body text and all tables with stable body-element identifiers.
- `*_all_text_parts.json` and `*_fields_equations.json`: visible text separated from field instructions, plus OMML/tracked-change checks.
- `independent_array_audit.py`, `.json`, and `.log`: new full-array/table/hash calculations and reference-exclusion sensitivity.
- `raw_replay_current_numpy.json` and `.log`: 600 participants across nine conditions, plus 600 original history regenerations, all with zero differences.
- `correction_sensitivity.py`, `.json`, and `.log`: separate 12,000-person correction/reference/daily-rule sensitivity.
- `unittest.log`: 23 tests passed.
- `pat_prose_metrics.json`: PAT deterministic prose metrics. These are descriptive and were not used as evidence of a scientific fault. Acronym heuristics and alternate word-tokenization counts are not manuscript defects.

The parent can address SOL-01, SOL-03, and SOL-04 without changing the primary simulation. SOL-02 warrants a decision about how much robustness evidence to show. The existing primary calculations and their conditional interpretation pass this review.
