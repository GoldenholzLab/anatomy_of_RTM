# Anatomy of regression to the mean

This repository simulates apparent seizure-frequency improvement under changes
to the seizure process, trial eligibility and detector performance. The revised
analysis defines Type 3 RTM as measured-count RTM absent on true counts in the
same detector-selected participant and trial window.

## Preserved cohort and revised analysis

`outputs/rtm123_1m` contains the original million-person cohort and original
analysis outputs. Keep this directory unchanged. The revised results are in
`outputs/rtm123_type3_1m`. Read the original daily histories, latent rates and
seeds as inputs; write reruns to a separate directory.

The analysis loads `realSim_turbo.py` from the sibling `CHOCOLATE` checkout by
default. Set `CHOCOLATE_REPO` to use another checkout. Run manifests record the
simulator source hash, input hashes and numerical environment. Matching the
repository name alone does not establish identical simulator code.

## Reproduce the revised analysis

Use Python with NumPy and Matplotlib installed. Run from the repository root.
The documented review used the bundled Python 3.12 runtime; exact versions and
source hashes are recorded in `outputs/rtm123_type3_1m/run_manifest.json`.

```bash
python3 -m unittest discover -s tests -p 'test_rtm123.py'
python3 scripts/rtm123/02_run_conditions.py --cohort-dir outputs/rtm123_1m --output-dir outputs/rtm123_type3_reproduction --workers 8 --chunk-size 512 --no-resume
python3 scripts/rtm123/03_make_tables.py --input-dir outputs/rtm123_type3_reproduction
python3 scripts/rtm123/04_make_figures.py --input-dir outputs/rtm123_type3_reproduction
python3 scripts/rtm123/05_make_explainer_figure.py --output-dir outputs/rtm123_type3_reproduction
python3 scripts/validate_paired_type3.py outputs/rtm123_type3_reproduction
python3 scripts/replay_paired_type3.py --cohort-dir outputs/rtm123_1m --output-dir outputs/rtm123_type3_reproduction --n 500
```

A resume accepts condition files only when their analysis source, cohort
contents, numerical environment and condition settings match. Measurement
conditions also require matching perfect-detector membership and baseline
windows. The validation script checks all saved classification partitions and
summary denominators, recomputes classifications from saved sufficient
statistics, and checks an independent rational-arithmetic sample.

The review record and additional raw-history replay checks are under
`output/revision_2026-11-12`. Revised working files have not yet been published
from this checkout.

## Generate a new small cohort

Use a new output directory when testing cohort generation.

```bash
python3 scripts/rtm123/01_generate_common_cohort.py --output-dir outputs/rtm123_smoke_new --n-patients 1000
python3 scripts/rtm123/02_run_conditions.py --cohort-dir outputs/rtm123_smoke_new --output-dir outputs/rtm123_smoke_results --workers 2
python3 scripts/rtm123/03_make_tables.py --input-dir outputs/rtm123_smoke_results
python3 scripts/rtm123/04_make_figures.py --input-dir outputs/rtm123_smoke_results
```

## Manuscript source

`anatomy_of_RTM_JCE.docx` is preserved. The scientific working version is
`anatomy_of_RTM_revised.docx`, built by `scripts/revise_anatomy_manuscript.py`
from the reviewed analysis in `outputs/rtm123_type3_1m`. The builder edits OOXML
and preserves live Zotero fields. Microsoft Word is required for final visual
verification, pagination, citation refresh and saves. Journal submission
formatting is a separate stage.

## Seizure submission files

After the independent Astra review, `scripts/prepare_seizure_submission.py`
packages the reviewed working manuscript as `anatomy_of_RTM_Seizure.docx`,
with separate Highlights and Supplement DOCX files. It preserves the live
Zotero fields. The delivered copies were refreshed with the Seizure citation
style, visually checked and saved in Microsoft Word. The main manuscript has
15 pages, Highlights has one page, and the Supplement has three pages. The
main PDF was exported from Word and checked in Apple Preview. The official
author guide was checked on November 12, 2026.

`scripts/build_seizure_figures.py` prepares the journal figure typography from
the reviewed CSV results. `scripts/finalize_word_layout.py` applies the final
OOXML layout adjustments. Rebuilding a DOCX requires another Word review,
Zotero refresh and native save. Do not overwrite the delivered copies merely
to regenerate figures. Final hashes and table checks are recorded in
`output/revision_2026-11-12/final_submission_audit.json`.

The current paper notebook is a snapshot of the reviewed saved results. Its
code cells are explicitly unexecuted and can reload those results. Rebuild it
with `python3 scripts/build_rtm123_notebook.py`. The original notebook and its
builder are archived under `output/revision_2026-11-12/archive`. Standalone
vector figures use the `anatomy_of_RTM_Seizure_Figure` filenames. The updated
graphical abstract is under `output/seizure_graphical_abstract`. The separate
`anatomy_of_RTM_Seizure_Reporting_Guideline_Explanation.txt` explains why the
clinical reporting checklists do not fit this descriptive simulation.
