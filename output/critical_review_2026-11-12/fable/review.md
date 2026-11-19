# Independent scientific and computational review (Fable)

Reviewed on 2026-11-12. Files as saved on disk, unchanged during the review:

| File | SHA-256 (first 12) |
|---|---|
| `anatomy_of_RTM_Seizure.docx` | `6119f8107c62` |
| `anatomy_of_RTM_Seizure_Supplement.docx` | `cd7195edc9e7` |
| `anatomy_of_RTM_Seizure_Highlights.docx` | `f959a38e5388` |
| `rtm_anatomy/rtm123.py` | `fd9266049bb1` (matches `run_manifest.json`) |

I edited nothing outside `output/critical_review_2026-11-12/fable`. I read the DOCX files through `zipfile` and `lxml` only. No LibreOffice, no Word automation, no subagents.

## Verdict

I found no numerical error. Every number in the main text, Table 1 and Tables S1 to S3 matches the saved per-patient arrays, and my own re-implementation reproduces those arrays from the raw daily histories. The code does what the Methods say.

The problems are in what the numbers mean and how the paper sits next to the group's other work. Four need attention before submission.

1. The manuscript does not cite two closely related works by the same authors that are indexed in PubMed, and an earlier public preprint of this same paper defines Type 3 differently. One companion reports 38.2% RTM and 14.7% MPC for perfect detection where this manuscript reports 53.8% and 26.7%.
2. That gap comes from the rolling first-eligible window, which the manuscript discloses but does not quantify. Half of enrolled participants qualify at the first screen and show 38.3% RTM and 14.6% MPC. The rest show 69.8% and 40.0%.
3. The RTM indicator reads 25.8% in the same people when the window is not selected at all. The manuscript gives no such comparator.
4. The simulator file that generated the cohort is not in the public simulator repository.

## How I checked

All scripts and outputs are in `/Users/dgoldenh/Documents/GitHub/anatomy_of_RTM/output/critical_review_2026-11-12/fable`.

| Check | Script | Output |
|---|---|---|
| OOXML text, tables, fields, OMML, media | `fable_extract_docx.py` | `extract/` |
| Recompute all summaries from saved arrays | `fable_check_saved_arrays.py` | `fable_saved_array_check.json` |
| 209 table cells and text numbers against recomputed values, word counts | `fable_check_docx_numbers.py` | `fable_docx_number_check.json` |
| Independent replay of detector, selection and RTM rule for 100,000 people in 8 conditions, plus reference sensitivity analyses | `fable_replay.py` | `fable_replay_results.json` |
| Cohort regeneration and transient-condition replay for 1,500 people, cycle activity | `fable_type1_and_cohort_replay.py` | `fable_type1_cohort_replay.json` |
| No-selection comparators on all 1,000,000 histories | `fable_comparators.py` | `fable_comparator_results.json` |
| First-screen versus later-window split, transient stratum profile | `fable_single_screen_and_type1.py` | `fable_single_screen_and_type1.json` |

My scripts import nothing from `rtm_anatomy`. The replay shares only the documented detector seed recipe. I ran the 23 existing unit tests with bytecode writing disabled, and all passed. I did not rerun the million-person simulation.

Neither DOCX contains OMML equations, tracked changes or comments. Citations are live Zotero fields, and the cached citation text agrees with the field instructions. The embedded figures are byte-identical to `outputs/rtm123_type3_1m/rtm123_explainer.png` and `output/seizure_figures/Figure_2.png`. Text extracted from the Word-exported PDF contains the same numbers as the DOCX.

I formed the findings below before opening any earlier review. Afterwards I read `output/revision_2026-11-12/revision_protocol.md`, the audit and packaging JSON files, summaries of four evidence files, and the first 80 lines of `astra_review.md`. I reused two facts from them. Earlier sample regenerations of 500 and 1,000 cohort rows passed, and the authors refer internally to a separate "RTM3" manuscript. I did not open the `astra`, `opus` or `sol` folders under `critical_review_2026-11-12`.

## Findings ranked by severity

### F1. Related work by the same authors is uncited, and the same condition carries different numbers across papers

Status. Confirmed omission. The editorial consequence is a plausible risk.

Where. Introduction, "Previous seizure-trial simulations quantified eligibility-related RTM." Section 4.2, "Reduced observed RTM alone does not demonstrate greater trial efficiency." Section 4.3, "Direct numerical comparison with a fixed-baseline study or a study using a separate long-term diary would mix designs." Section 2.1, "the paired classification analysis was added during manuscript revision".

Evidence. According to PubMed, three records by this author group bear on the manuscript.

- "Counterintuitive: reducing regression-to-the-mean worsens efficiency in simulated clinical trials", Seizure 2026;142:168-174, [doi:10.1016/j.seizure.2026.09.002](https://doi.org/10.1016/j.seizure.2026.09.002). Its abstract says a software re-review reversed the lab's earlier conclusion that excluding baseline from eligibility improves efficiency. That earlier conclusion is in reference [1], [doi:10.1111/epi.17730](https://doi.org/10.1111/epi.17730).
- "Device sensitivity and false alarms can reshape regression-to-the-mean in simulated epilepsy trials", medRxiv, posted 2026-08-02, [doi:10.64898/2026.07.30.26359361](https://doi.org/10.64898/2026.07.30.26359361). Its abstract reports RTM 38.2% and MPC 14.7% for perfect detection, and 53.2% and 31.3% at one false alarm per day with expected-alarm correction.
- "The anatomy of regression-to-the-mean in simulated epilepsy trials", medRxiv, posted 2026-07-31, [doi:10.64898/2026.07.27.26359051](https://doi.org/10.64898/2026.07.27.26359051). Same title and authors as this manuscript. Its abstract treats reduced sensitivity and false alarms as "RTM type 3" at the condition level and says each "increased RTM and apparent response".

The first-screen subset of this manuscript's own cohort gives 38.3% and 14.6% for perfect detection and 53.8% and 31.2% at one false alarm per day (`fable_single_screen_and_type1.json`). Those values sit within 0.6 points of the companion preprint's abstract. The two papers use different reference definitions, so I read the match as strong corroboration that the design explains the gap. It is not an exact reproduction.

Why it matters. A reader of both papers sees "perfect detection" produce 38.2% RTM in one and 53.8% in the other, with the same simulator and entry rule. Section 4.3 alludes to the other design without naming it. The public preprint with this title states a conclusion the revised manuscript explicitly rejects in Section 4.1. Section 4.2 restates the main finding of the group's published Seizure paper with no citation, in the same journal.

Minimal fix. Cite the Seizure 2026 paper at the Introduction sentence and at the Section 4.2 sentence. Cite the companion preprint at the Section 4.3 sentence and state the single-baseline values next to the rolling values. Say in Methods or a footnote that an earlier preprint version used a condition-level description of Type 3. Disclose both preprints in the cover letter.

Verification. PubMed metadata and abstracts for PMIDs 42715842, 42619957, 42619962 and 37505116.

Not established. I could not read the preprint full texts because PMC returned a browser check. I have not seen the cover letter. I do not know whether the companion is under review elsewhere.

### F2. The rolling first-eligible window accounts for about half of the headline RTM excess and MPC

Status. Confirmed by computation. Whether the text needs to change is a judgment about interpretation, so I class it as a plausible risk. The design itself is disclosed.

Where. Abstract, "53.8% met observed RTM and median seizure-frequency reduction was 26.7%". Section 2.2, "We used the first eligible window." Section 4.3 mentions the "rolling selection design" once.

Evidence. Code at `rtm_anatomy/rtm123.py:314-329` scans start months 0 to 31 and returns the first that passes. From the saved arrays:

| Condition | Enrolled at first screen | RTM, first screen | RTM, later window | MPC, first screen | MPC, later window |
|---|---|---|---|---|---|
| Perfect detector | 50.9% | 38.3% | 69.8% | 14.6% | 40.0% |
| Entry threshold 8 | 46.1% | 42.1% | 71.5% | 19.6% | 36.8% |
| Sensitivity 70% | 42.3% | 42.4% | 71.1% | 20.0% | 40.7% |
| FAR 1/week | 41.1% | 43.0% | 79.1% | 19.9% | 50.8% |
| FAR 1/day | 35.8% | 53.8% | 78.9% | 31.2% | 53.3% |

Type 3 at one false alarm per day is 27.0% among first-screen enrollees and 49.7% among later ones.

Why it matters. Scanning up to 32 overlapping windows equals unlimited monthly rescreening for almost three years. A trial with one prospective baseline resembles the first-screen column. Against the no-selection level in F3 (25.8%), a single screen adds 12.5 points of RTM and rescreening adds another 15.5. MPC rises from 14.6% to 26.7%. The between-condition differences in the Abstract (53.8% to 58 or 59%) are smaller than the first-screen versus later gap of about 30 points. Part of each difference is a shift in that mix. Holding the perfect-detector mix fixed, sensitivity 70% gives 56.5%, so about half of the reported rise to 59.0% is the mix shift.

Minimal fix. Add one sentence to Section 3.1 with the first-screen and later-window values, and a supplementary table with the split for all nine conditions. Name the rescreening interpretation in Section 4.4.

Verification. `fable_single_screen_and_type1.py`. The subsets recombine to the reported totals.

Not established. Whether reference [1] used the same rolling design.

### F3. The RTM indicator has a no-selection level near 26% that the manuscript never states

Status. Confirmed by computation. Interpretation risk.

Where. Section 2.4, "Observed RTM required a baseline rate above the reference and a test rate strictly closer to it". All RTM percentages in the Abstract, Table 1 and Figure 2B.

Evidence. For the 649,098 perfect-detector enrollees I drew a window start uniformly from months 0 to 31 without looking at their counts. RTM by the manuscript's rule was 25.8%. The baseline was above the reference in 45.4%, and 56.9% of those had a closer test mean. For all 1,000,000 people the figure was 24.6%. Median percentage change at random windows was 0.0%. At the selected windows, 74.0% had a baseline above the reference and 72.7% of those met the rule (`fable_comparator_results.json`). According to PubMed, the abstract of reference [1] reports RTM fractions of 23% to 25% when baseline is excluded from eligibility ([doi:10.1111/epi.17730](https://doi.org/10.1111/epi.17730)), which agrees.

Why it matters. A test mean of three months is closer to a person's long-run mean than a baseline mean of two months more than half the time by variance alone. Readers will take "53.8% met observed RTM" as the share affected by selection, when about 28 points is the excess over an unselected window. The same applies to "True RTM 34.1%" at one false alarm per day, which compares with 24.7% for those people at a random window. MPC does not have this problem because its no-selection value is zero.

Minimal fix. Report the random-window value in Section 2.4 or 3.1 and in a table note.

Verification. `fable_comparators.py`, which first reproduces the saved perfect-detector flags from raw counts.

### F4. The simulator file that produced the cohort is not publicly available, and the public project repository holds the earlier analysis

Status. Confirmed locally and against the public GitHub pages on 2026-11-12.

Where. Section 2.1, "CHOCOLATES, an open-source simulator". Data and code availability, "the simulator repository is https://github.com/GoldenholzLab/CHOCOLATES".

Evidence. `rtm_anatomy/rtm123.py:100` loads `realSim_turbo.py` from the sibling checkout. `git -C ../CHOCOLATE status` lists that file as untracked, and it has no commit history. The public repository page lists eight root files and `realSim_turbo.py` is not among them. The URL in the manuscript resolves to a repository named `GoldenholzLab/CHOCOLATE`. The turbo file routes every draw through a seeded `numpy` Generator, casts rates to single precision and replaces the per-sample cluster loop with array operations. The published `realSim.py` uses the global `numpy.random` state, so it cannot regenerate these histories from the stored seeds. The public `anatomy_of_RTM` repository has three commits and matches local `origin/main`, which predates the paired analysis. Seven tracked files are modified and the revised scripts are untracked. The run manifest records `git_sha` 1a4955e, which does not contain the code that ran. The manifest's `analysis_source_sha256` does pin `rtm123.py` correctly.

Why it matters. The manuscript says revised code is pending release, which is accurate. It does not say the generating simulator differs from the public one. A reader following the cited URL cannot rebuild the cohort.

Minimal fix. Commit `realSim_turbo.py` to the simulator repository, or include it in the project release, and say so. Use the canonical repository URL. Release the revised analysis before submission or give reviewers a private link.

Verification. The current simulator file regenerated 1,500 of 1,500 sampled histories and latent rates exactly from stored seeds, using a different sample from the earlier checks. My replay under Python 3.13 and numpy 2.2.5 matched arrays produced under Python 3.12 and numpy 2.5.4, so the results do not depend on that environment difference.

Not established. Whether the file exists on another branch or in a private repository. Full-cohort regeneration, which I did not run. The cohort metadata from May has no generation fingerprint, so sample agreement supports the provenance without proving it. The authors already note this.

### F5. At high false-alarm rates, Type 3 is mostly the enrollment of people who fail the entry rule on true counts

Status. Confirmed by computation in a 100,000-person replay. The design choice is disclosed. The consequence is not reported.

Where. Section 2.4, "without an additional true-count eligibility filter". Abstract and Section 3.4, "Type 3 affected 41.6% of eligible participants".

Evidence.

| Condition | Selected people who pass the entry rule on true counts in the same window | Type 3 in true-eligible, % of selected | Type 3 in true-ineligible, % of selected |
|---|---|---|---|
| Sensitivity 90, 80, 70% | 100% | 3.9, 5.8, 7.9 | 0 |
| FAR 1/month | 76.1% | 3.1 | 4.8 |
| FAR 1/week | 61.0% | 5.2 | 15.9 |
| FAR 1/day | 39.7% | 6.1 | 35.3 |

In the full arrays, 67.0% of Type 3 cases at one false alarm per day have a true baseline at or below their true reference. With monthly alarm noise of about 5.5 counts against an entry threshold of 4, noise alone qualifies people, and 98.5% of the population enrolls. At that rate the 25-day rule is close to inert, because a day counts as an event day whenever two or more alarms fall on it.

Why it matters. "Measurement-only RTM" reads as distorted trajectories in properly enrolled people. At one false alarm per day, 85% of it is enrollment on noise. The manuscript's sentence that detector errors changed enrollment is correct but does not convey the proportion.

Minimal fix. Add a column to Table S1 with the share of selected participants meeting true-count eligibility, and one sentence in Section 3.4.

Verification. `fable_replay.py`. The replay reproduced `first_start`, both classifications and all saved statistics for 100,000 people in eight conditions with zero differences.

### F6. Sensitivity conditions apply the entry threshold to unscaled detected counts, and the Methods do not say so

Status. Confirmed methods gap.

Where. Section 2.3, "Measurement conditions separately reduced sensitivity to 90%, 80% or 70% without false alarms". The correction sentences that follow cover false alarms only.

Evidence. `rtm_anatomy/rtm123.py:684-706`. False-alarm counts lose their expected value before eligibility. Thinned counts are not divided by sensitivity. Only the reference is scaled (`rtm123.py:363-368`). The effective true-count threshold becomes 4.4, 5.0 and 5.7 events per month. Eligibility falls from 64.9% to 55.2%, and true-count RTM in the selected people rises from 53.8% to 56.1%, the same direction as the threshold-8 condition.

Why it matters. Part of the sensitivity effect on observed RTM is a threshold change, which the manuscript files under selection. The two measurement families are handled asymmetrically, and a reader cannot tell. The Methods also omit that detections are independent binomial draws per seizure, which the revision protocol states.

Minimal fix. One sentence in Section 2.3. Optionally add a run with the threshold scaled by sensitivity.

Verification. Code reading and the replay.

### F7. The transient condition is a symmetric redraw, but the Introduction and Figure 1 call it worsening, and promised strata are missing

Status. Confirmed. Partly disclosed in Section 2.3.

Where. Introduction, "Type 1 describes return after a temporary state worsening." Figure 1, "temporary state worsening". Section 2.3, "We stratified results by overlap with baseline or test and by the direction of the sampled rate change."

Evidence. `rtm_anatomy/rtm123.py:722-738` draws the replacement rate from the between-person distribution. It is lower than the person's own rate in 50.1% of people. A quarter of draws exceed three times the own rate and a quarter fall below one third. The 5th to 95th percentile ratio runs from 0.07 to 14.4. In the baseline-only stratum with 95.1% RTM and 92.6% MPC, 77.8% of participants never qualify without the transient. `type1_overlap_summary.csv` holds five overlap strata and their direction splits. The manuscript reports two strata and no direction result. The omitted test-only stratum has RTM 39.6%.

Why it matters. The 58.3% figure is a mixture set by an arbitrary magnitude distribution. The 95.1% figure describes people enrolled only because of a very large transient. Both facts are consistent with the text but invisible in it.

Minimal fix. Use "temporary rate change" in the Introduction and Figure 1, or add a note that selection favors upward changes. Put the full overlap table in the supplement. Report the 77.8%.

Verification. `fable_type1_and_cohort_replay.py` replayed 1,500 people with zero differences. `fable_single_screen_and_type1.py` profiled the stratum.

### F8. At one sample per day the simulator's cycle component is active in about 1% of people

Status. Confirmed property of the simulator. Plausible risk for interpretation.

Where. Section 2.1, "heterogeneous seizure rates, clustering, cycles". Section 4.4, "daily sampling cannot address within-day cycles".

Evidence. `CHOCOLATE/realSim_turbo.py:299` drops cycles faster than the Nyquist limit, which removes the 12-hour and 24-hour terms. Lines 311-312 give the weekly term zero amplitude and the 4-to-45-day term zero probability. Only the 90-to-450-day term remains, with probability 0.0116. In 100,000 draws, 1.17% had any active cycle. The published `realSim.py` has the same parameters.

Why it matters. Month-to-month variation in this cohort is close to independent overdispersed noise plus short clusters. A paper that separates a "state" mechanism from "natural variability" should say that slow within-person fluctuation is nearly absent from the reference population.

Minimal fix. One sentence in Section 4.4.

Verification. Code reading and direct simulation.

### F9. The Methods promise two items the documents do not contain

Status. Confirmed, minor.

Where. Section 2.4, "approximate order-statistic intervals describe the median" and "We report the generating process, condition transforms, selection algorithm, paired definitions, seeds and computational scale."

Evidence. No median interval appears in the main text or Tables S1 to S3. They exist in `condition_summary.csv`. The master seed 20260531 is not in either document. The MPC distribution has point masses. In the sensitivity 80%, sensitivity 70% and FAR 1/month conditions, 5.4%, 5.6% and 4.8% of participants have a percentage change of exactly 33.3%, the median sits on that mass, and the saved interval is degenerate. That explains why three conditions share an MPC of 33.3.

Minimal fix. Add the intervals to a supplementary table with a note on ties, or delete the clause. State the master seed or change "seeds" to refer to the analysis files.

### F10. Table S3 omits the true-only category, which exceeds Type 3 in every fixed-enrollment row

Status. Confirmed, minor. The primary analysis reports both directions. Table S3 does not.

Evidence. Recomputed against the perfect-detector classification of the same people and windows:

| Condition | Type 3 | True only | Net measured minus true |
|---|---|---|---|
| Sensitivity 90% | 3.3% | 4.3% | -0.9 pp |
| Sensitivity 80% | 4.5% | 6.8% | -2.3 pp |
| Sensitivity 70% | 5.4% | 9.1% | -3.7 pp |
| FAR 1/month | 3.7% | 5.8% | -2.1 pp |
| FAR 1/week | 6.1% | 12.3% | -6.3 pp |
| FAR 1/day | 9.4% | 21.6% | -12.2 pp |

Why it matters. With enrollment held fixed, measurement error removes more RTM classifications than it creates. That is the cleanest evidence in the dataset that the primary Type 3 excess comes through selection on measured counts. It supports the Discussion and deserves a column.

Minimal fix. Add true-only and net columns to Table S3.

### F11. Small wording and consistency items

Status. Confirmed, minor.

- Section 2.2 says windows were "beginning at month 0 and ending at month 31". Windows start at months 0 through 31. The last baseline covers months 31 and 32.
- Section 2.3 says daily counts for the 25-day rule "were reduced by the rounded expected daily alarm count". The rounded value is zero at 1/month and 1/week (`rtm123.py:702`), so the rule ran on uncorrected counts in those two conditions. Say so.
- Table 1 measured minus true RTM differs by 0.1 from the Table S2 net difference in four rows (sensitivity 90% and 80%, FAR 1/week and 1/day) because each value is rounded separately. Add a note.
- "Observed RTM" in the Abstract, Results and Figure 2 caption is "Measured RTM" in Table 1 and the Figure 2B title. Figure 1 says "RTM 1, 2, 3" where the text says "Type 1, 2, 3".
- Supplement row labels differ from Table 1 ("Baseline: perfect detector, 4/month", "Type 1: transient 2-month mSF change"). "mSF" is undefined, and "Baseline" also names the trial period.
- Figure 2 bar colors in panels A and D have no legend or caption text.
- Type 3 at FAR 1/day and fixed-enrollment RTM at FAR 1/day both print as 41.6%. Both are correct (41.57% and 41.60%). A reader may suspect a copy error, so consider two decimals in one place.

### F12. Items for the authors to verify

Status. Unverified.

- According to PubMed, the Seizure 2026 paper lists "Westover, M Brandon" with Stanford only. This manuscript lists "Brandon Westover" with Harvard Medical School and Stanford, and its own reference [8] gives "Westover MB".
- The AI declaration names OpenAI Codex only. This review used Claude. Update the statement if any text from it enters the manuscript.
- `docProps/app.xml` in all three DOCX files still carries the earlier title "Three sources of regression to the mean in clinical trials: a simulation study using epilepsy as a model", and the core keywords differ from the manuscript's keyword line. Correcting this needs Word's file properties dialog.

## Limitations the manuscript already discloses adequately

I tested the two that could move the headline result. Neither changes a conclusion.

| Disclosed limitation | What I measured (100,000-person replay) |
|---|---|
| Reference includes the trial window | Excluding the five trial months changes measured RTM by at most 0.5 points and Type 3 by at most 0.4 points in every condition |
| Monthly flooring raises corrected counts above the reference | Mean measured long-run rate 7.98 against reference 6.88 at FAR 1/day. Type 3 moves from 41.4% to 39.1% with unfloored test counts and to 37.4% with each person's measured 36-month mean as reference |

The following are also stated plainly and need no change. Type 3 is a paired classification and gives no additive decomposition. The analysis is within-arm with no treatment contrast or power estimate. The paired analysis was not prespecified. The transient is not data-derived. Detector performance is constant. Intervals reflect Monte Carlo precision only.

## Numerical claims that pass

All 209 table cells and text numbers I checked match values recomputed from the saved arrays, with zero mismatches (`fable_docx_number_check.json`).

| Claim | Document | Recomputed | Result |
|---|---|---|---|
| Eligible, perfect detector | 649,098 (64.9%) | 649,098 (64.910%) | Pass |
| RTM and MPC, perfect detector | 53.8%, 26.7% | 53.789%, 26.667% | Pass |
| Transient: eligible, RTM, MPC | 75.6%, 58.3%, 36.8% | 75.618%, 58.295%, 36.842% | Pass |
| Transient baseline-only stratum | 95.1%, 92.6% | 95.101%, 92.593% | Pass |
| Transient neither stratum | 51.0%, 25.9% | 50.985%, 25.926% | Pass |
| Threshold 8: eligible, RTM, MPC | 40.4%, 57.9%, 29.4% | 40.427%, 57.923%, 29.412% | Pass |
| Sensitivity 70%: eligible, RTM, MPC, Type 3 | 55.2%, 59.0%, 33.3%, 7.7% | 55.189%, 58.987%, 33.333%, 7.720% | Pass |
| FAR 1/day: eligible, RTM, MPC, Type 3, share | 98.5%, 69.9%, 46.0%, 41.6%, 59.4% | 98.532%, 69.944%, 46.032%, 41.568%, 59.431% | Pass |
| Measured-only and true-only counts, net | 409,581, 55,966, 35.9 pp | identical, 35.888 pp | Pass |
| Fixed enrollment RTM | 50.0%, 41.6% | 50.047%, 41.604% | Pass |
| Fixed enrollment MPC and n | 26.3%, 17.6%, 649,090, 631,490 | 26.316%, 17.647%, identical | Pass |
| Table 1, 45 cells | | | Pass |
| Table S1, 45 cells, rows sum to eligible n | | | Pass |
| Table S2, 45 values including Wilson limits | | | Pass |
| Table S3, 42 cells | | | Pass |
| Abstract 207 words, main text 1,809 words, 18 references all cited, Highlights 81 to 82 characters | | | Pass |

Other checks that passed:

- The strict RTM rule, the tie handling, the four-way partition and all denominators match Section 2.4. Float reclassification of every selected participant from saved statistics agreed with the saved flags in all nine conditions.
- Wilson limits recomputed independently agree to 12 decimals.
- The Figure 1 example bars satisfy the stated rule. The Type 3 column meets RTM on measured values (baseline 0.745, test 0.433, reference 0.50) and fails on true values, which equal the reference.
- Figure 2 is drawn from `condition_summary_with_deltas.csv` without transformation (`scripts/build_seizure_figures.py:34-77`).
- According to PubMed, references [1], [12], [13], [14] and [16] exist with the cited volume and pages. The asthma sentence in Section 4.1 matches the abstract of [16] ([doi:10.1056/NEJMoa1103319](https://doi.org/10.1056/NEJMoa1103319)). FEV1 rose 20% with albuterol and about 7% with each other arm, and reported improvement was 50%, 45% and 46% against 21% with no intervention. The other four DOIs are [1] [10.1111/epi.17730](https://doi.org/10.1111/epi.17730), [12] [10.1111/epi.17917](https://doi.org/10.1111/epi.17917), [13] [10.1212/WNL.0000000000009530](https://doi.org/10.1212/WNL.0000000000009530) and [14] [10.1016/S1474-4422(19)30399-0](https://doi.org/10.1016/S1474-4422(19)30399-0).
- The entry rule is a fair composite of the cited trials. The full text of [13] requires at least 3 seizures per month and no 21-day seizure-free period ([doi:10.1212/WNL.0000000000009530](https://doi.org/10.1212/WNL.0000000000009530)), so "reflected" is the right verb.

## What I could not establish

- The Methods of the two medRxiv preprints, beyond their PubMed abstracts.
- The entry criteria of reference [14]. Its abstract does not state them ([doi:10.1016/S1474-4422(19)30399-0](https://doi.org/10.1016/S1474-4422(19)30399-0)).
- Whether reference [12] describes the expected-alarm subtraction it is cited for. Its abstract does not say ([doi:10.1111/epi.17917](https://doi.org/10.1111/epi.17917)).
- References [2] to [11], [15], [17] and [18], which I did not look up.
- The journal's current word and format limits. I did not re-read the author guide.
- Native Word display, pagination and field rendering. I relied on OOXML and on text from the Word-exported PDF. If the parent needs a visual check of table and caption placement, that requires Word.
- Identity of the full cohort with a fresh regeneration.
