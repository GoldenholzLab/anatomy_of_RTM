# Scientific review and corrections

The revised analysis implements the requested paired Type 3 definition
correctly. The review found material defects in cache validity and several
manuscript claims, which have been corrected. A fresh run of all nine
conditions on the retained million-person cohort reproduced every
pre-review patient-level result. No scientific formula change was needed
within this review.

The corrected working manuscript is `anatomy_of_RTM_revised.docx`. It remains
pending Microsoft Word visual verification, citation refresh and final save
by the coordinator. Reopen the file from disk before that stage, because an
older version may still be open in Word.

## Findings and corrections

1. Cached measurement results could survive changes to patient seeds or
   perfect-detector enrollment. A scratch example accepted baseline enrollment
   created with a different monthly minimum, then retained zero fixed
   participants after baseline enrollment was rebuilt for 20 participants.
   The cache now identifies daily counts, seeds and latent rates by content
   hashes, records NumPy and analysis source, and pins the Type 1 simulator.
   Measurement conditions validate the complete baseline condition and
   eligibility policy before any cache hit, and bind its actual membership
   and baseline starts. Incomplete caches are rebuilt. New cohort generation
   records source provenance and rejects incompatible partial resumes.
   Simulator loading also suppresses bytecode writes into its source checkout.

2. A retained discussion paragraph said improvement arose from selection and
   measurement alone, omitting the transient intervention. It also cited the
   asthma experiment as evidence that objective outcomes can be dominated by
   RTM. The revised paragraph names the modeled sources of change and explains
   that the asthma comparison did not isolate RTM from other untreated
   changes. The citation remains live. See the
   [primary asthma study](https://pmc.ncbi.nlm.nih.gov/articles/PMC3154208/).

3. Methods now explain that the transient replacement resamples cycle
   parameters and cluster status as well as mean frequency. It changes the
   simulated seizure process, so its effects cannot be attributed to mean
   rate alone. Baseline-overlap results include both higher- and lower-rate
   replacements. The figure marker now says "temp rate" instead of "temp ref."

4. The manuscript now states that monthly flooring can raise expected
   corrected counts above the sensitivity-scaled true reference. The latter
   remains the specified comparison scale. Median intervals are described as
   approximate order-statistic intervals. Public release is identified as
   pending. README commands preserve the original output directory, and a
   revision protocol and input/output manifests now accompany the analysis.

## Scientific checks

The same detector-selected participant and trial window supply both RTM
classifications. No additional true-count eligibility filter removes
measurement-only cases. The four paired categories exhaust each selected
cohort. Type 3 prevalence uses all selected participants; its share of
measured RTM uses measured RTM cases. The measured-minus-true difference is
measured-only minus true-only prevalence, not Type 3 prevalence.

Corrected measured counts use sensitivity times the condition-specific
36-month true-count mean. True counts use the unscaled mean. The reference
includes the trial window. This differs from RTM3's separate reference
history, and Anatomy retains rolling first-eligible windows. Exact rational
comparisons reject ties. Monthly expected-alarm subtraction retains
fractions and precedes flooring; the rounded daily subtraction applies only
to the 25-day rule.

Fixed enrollment retains both perfect-detector membership and baseline
windows. Zero measured baselines remain in RTM denominators and are excluded
only from median percentage change. The central interpretation is supported
as a descriptive paired classification under this model. It does not
establish additive causal RTM components, effects on randomized treatment
contrasts, or trial power.

## Validation and rerun

- All 23 unit tests passed, including the new cache and fixed-window
  regressions.
- The full rerun used the original cohort, eight workers and chunks of 512,
  with resume disabled. It completed all 9,000,000 patient-condition
  evaluations. Analysis version is `paired-type3-v3`.
- All 22 saved patient-level arrays per condition exactly match the archived
  pre-review revision, including NaNs. All seven summary CSVs are
  byte-identical. The cache defects did not alter this run's reported results.
- Validation recomputed strict classifications for all 6,022,690 selected
  patient-condition observations, checked all paired partitions and summary
  denominators, and used an independent Fraction oracle for 18,000 cases.
  True-count references and baseline/test summaries also matched the raw
  daily histories in every condition without a transient replacement.
- Independent detector, selection and rational-classification replay found
  zero discrepancies for 500 participants across all nine conditions.
  Type 1 replay reused the production replacement generator; its downstream
  calculations were independent. A separate sample of 1,000 original
  participants regenerated exactly, including daily counts and latent rates.
- All 45 numeric cells in manuscript Table 1 match the result CSV. Narrative
  and abstract values remain consistent. At one false alarm/day, observed
  RTM is 69.9%, Type 3 prevalence is 41.6%, and Type 3 accounts for 59.4% of
  measured RTM cases.
- The DOCX retains all 12 field instructions and 36 field markers. Only
  `document.xml` and the two figure images differ from the original package;
  styles, numbering and relationships are unchanged. The source contains no
  comments, tracked changes, bookmarks or native equations. Both embedded
  images match the output PNGs. The corrected explainer was visually checked;
  the summary PNG is byte-identical to its inspected predecessor.
- Hash checks confirm that both RTM3 reference DOCX files, the original Anatomy
  source and its archive, and all 24 files in the original cohort/output
  directory are unchanged. Branch `main` and HEAD are unchanged. Nothing was
  committed, pushed or submitted. No Word automation or LibreOffice was used.

## Evidence and changed files

`astra_evidence/review_validation.json` records the array comparisons,
protected-file checks and DOCX audit. `outputs/rtm123_type3_1m/validation.json`
records the classification checks. `astra_evidence/raw_replay.json`,
`cohort_regeneration.json`, `unit_tests.log`, `full_rerun.log` and
`environment.json` provide the replay, tests and execution evidence.
`science_manifest.json` binds the working DOCX to its source, tables and
figures. `astra_evidence/before_review` preserves the incoming revision.

The review changed `rtm_anatomy/rtm123.py`, `tests/test_rtm123.py`,
`scripts/validate_paired_type3.py`, `scripts/revise_anatomy_manuscript.py`,
`scripts/rtm123/05_make_explainer_figure.py`, `README.md`, and the revised DOCX.
It added `scripts/replay_paired_type3.py`, `revision_protocol.md`, this record
and the audit evidence. Revised results, figures and manifests were
regenerated in `outputs/rtm123_type3_1m`.

Deterministic main-text metrics changed from 1,836 to 1,877 words, average
sentence length from 14.3 to 14.0 words, sentences over 30 words from 2.3% to
1.5%, estimated passive voice from 17.2% to 14.9%, and Flesch-Kincaid grade
from 13.8 to 13.5. Hedging density was 3.7 per 1,000 words after revision.
Three acronyms were detected; the only undefined candidate was the simulator
name CHOCOLATES. These automated signals are recorded in the before/after
metrics JSON files and do not establish scientific quality.

## Remaining limits and handoff

The original cohort metadata lacks a contemporaneous generator hash. The new
manifest states that absence explicitly and hashes the retained files.
Sampled regeneration agreement supports reproducibility but cannot recover
historical provenance or prove full-cohort regeneration.

The numerical estimates remain conditional on the synthetic model, rolling
selection, internal finite reference and correction rules. Small Monte Carlo
intervals do not address those model assumptions. The review found no
remaining material scientific inconsistency within the requested scope.

Word pagination, visual verification, Zotero refresh and final saves remain
with the coordinator. The current DOCX SHA-256 is
`0246b1ab00a97eb7cb0a54bb2ab273c0addd4447f0c783454d200bda6ea392e0`.
Record a new final-document hash after the Word save. Journal formatting,
highlights, supplementary DOCX preparation and public release were not
performed in this review.
