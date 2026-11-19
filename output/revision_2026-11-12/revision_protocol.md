# Scientific revision protocol

This revision adds a paired Type 3 classification to the retained Anatomy
simulation. It was developed after the original analysis and was not
preregistered. It does not revise the RTM3 manuscript or appendix.

## Population and selection

The input is the original set of 1,000,000 synthetic 36-month histories in
`outputs/rtm123_1m`, with 30 days per month. All conditions reuse those histories
and patient seeds. A condition may change the diary, measured counts or entry
threshold. Selection then uses the first eligible two-month baseline among
starts 0 through 31, followed by three test months.

The primary baseline rule requires a mean of at least 4 events/month, at least
3 in each baseline month, and no event-free interval longer than 25 days. The
threshold condition changes only the mean-frequency threshold to 8/month.
The primary RTM and median-percentage-change denominators exclude people who
never qualify. Eligibility yield retains all 1,000,000 potential participants.

The transient-state condition replaces one randomly located two-month segment
with a newly simulated segment. Its mean rate may be higher or lower. Cycle
parameters and cluster status are also sampled anew. This intervention changes
the simulated seizure process and does not isolate mean rate alone. The
condition-specific true history, including the replacement, supplies its
reference. Overlap summaries distinguish baseline, test, both, or neither and
the direction of the sampled rate change.

## Detector and correction

Sensitivity conditions use independent binomial detections at 90%, 80% and 70%
without false alarms. False-alarm conditions use full sensitivity and
independent Poisson alarms at 1/30, 1/7 or 1 per day. Detector seeds depend on
condition name and patient seed. Draws are reproducible within condition, but
are not nested across detector settings.

For monthly eligibility and outcomes, subtract the known expected 30-day
alarm count from each observed monthly total, retain fractional expectations,
and floor each corrected month at zero. For the event-free-interval check,
subtract the rounded expected daily alarm count from each recorded day and
floor at zero. These two corrections are distinct. Flooring can shift the
expected monthly corrected count above the sensitivity-scaled true mean.

## Paired classifications

For each condition-selected person, let B and T be the two-month baseline and
three-month test means. Let R be the mean true count over the full 36-month
condition-specific diary, including baseline and test. At sensitivity s,
measured counts use reference sR and true counts use R.

The rule is B > reference and |T - reference| < |B - reference|. Exact ties
fail. Integer cross-products with rational sensitivity and alarm factors
implement the strict comparisons without floating-point tie errors.

Both classifications use the same person and selected trial window. Do not
require that the true counts separately pass eligibility. Partition all
selected people into RTM on both scales, measured only, true only or neither.
Type 3 is measured only. Its prevalence divides by all selected people; its
share of measured RTM divides by measured RTM cases. The measured-minus-true
prevalence difference equals measured-only prevalence minus true-only
prevalence. It is a separate quantity.

This paired definition follows the narrower RTM3 concept. The Anatomy design
retains rolling first-eligible windows and an internal finite-history
reference. RTM3 uses a fixed trial window and a separate reference history, so
its numerical estimates are not interchangeable with these results.

## Fixed enrollment and uncertainty

The measurement sensitivity comparison retains both perfect-detector
membership and each person's baseline start. RTM uses all these participants.
Median percentage change is median[100 × (1 - T/B)] and excludes zero measured
baselines because their ratio is undefined. Report those exclusions separately.

Wilson intervals for proportions and approximate order-statistic intervals
for medians describe Monte Carlo precision under this assumed simulation.
They do not quantify model uncertainty. There is no active treatment, drug
comparison, power estimate or causal decomposition into RTM subtypes.

## Reproduction and review

Use the commands in the repository README with the original cohort as input
and a separate output directory. Run manifests identify analysis source,
cohort file contents, simulator source, numerical environment and baseline
selection dependencies. The scientific DOCX manifest binds the document to
its input tables and figure files. Any later Microsoft Word save changes the
DOCX hash and requires a new final-document record.

The independent review record is `astra_review.md` in this directory.
Patient-level validation and raw-history replay are separate checks. Neither
substitutes for Microsoft Word visual verification, Zotero refresh or final
submission review.
