# anatomy_of_RTM
The anatomy of regression to the mean (RTM) for epilepsy

## RTM type 1/2/3 one-cohort simulation

This repository contains a local, script-based pipeline for the one-cohort RTM
type 1/2/3 analysis. It reads CHOCOLATES from the sibling checkout at
`/Users/dgoldenh/Documents/GitHub/CHOCOLATE` by default, but all generated
code and outputs live in this repository.

Smoke run:

```bash
python3 -m pytest tests/test_rtm123.py
python3 scripts/rtm123/01_generate_common_cohort.py --output-dir outputs/rtm123_smoke --n-patients 1000
python3 scripts/rtm123/02_run_conditions.py --cohort-dir outputs/rtm123_smoke --output-dir outputs/rtm123_smoke
python3 scripts/rtm123/03_make_tables.py --input-dir outputs/rtm123_smoke
python3 scripts/rtm123/04_make_figures.py --input-dir outputs/rtm123_smoke
python3 scripts/build_rtm123_notebook.py --output-dir outputs/rtm123_smoke --notebook notebooks/for_the_paper.ipynb
```

Full 1,000,000-patient run:

```bash
python3 scripts/rtm123/01_generate_common_cohort.py --output-dir outputs/rtm123_1m --n-patients 1000000 --workers auto --chunk-size 512
python3 scripts/rtm123/02_run_conditions.py --cohort-dir outputs/rtm123_1m --output-dir outputs/rtm123_1m --chunk-size 512
python3 scripts/rtm123/03_make_tables.py --input-dir outputs/rtm123_1m
python3 scripts/rtm123/04_make_figures.py --input-dir outputs/rtm123_1m
python3 scripts/build_rtm123_notebook.py --output-dir outputs/rtm123_1m --notebook notebooks/for_the_paper.ipynb
```
