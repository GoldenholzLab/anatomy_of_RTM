"""Cross-check every number in Table 1, Tables S1-S3 and the prose against saved CSVs.

Read-only. Usage: python3 -I opus_check_numbers.py <repo_root> <out_json>
"""
import csv
import json
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
out = Path(sys.argv[2])
res_dir = root / "outputs/rtm123_type3_1m"
rows = {r["condition"]: r for r in csv.DictReader(open(res_dir / "condition_summary.csv"))}
ov = list(csv.DictReader(open(res_dir / "type1_overlap_summary.csv")))
order = ["baseline_perfect", "type1_transient_msf", "type2_threshold_8", "type3_sensitivity_90",
         "type3_sensitivity_80", "type3_sensitivity_70", "type3_far_1_per_month",
         "type3_far_1_per_week", "type3_far_1_per_day"]

opus = root / "output/critical_review_2026-11-12/opus"
body = (opus / "opus_anatomy_of_RTM_Seizure_body.txt").read_text()
supp = (opus / "opus_anatomy_of_RTM_Seizure_Supplement_body.txt").read_text()


def table_rows(text, idx):
    m = re.search(r"=== TABLE %d ===\n(.*?)\n=== END TABLE %d ===" % (idx, idx), text, re.S)
    lines = m.group(1).split("\n")
    return [[c.strip() for c in ln.split("||")] for ln in lines]


def f1(x):
    return "%.1f" % x


def fint(x):
    return "{:,}".format(int(x))


checks = []


def chk(where, doc_val, calc_val):
    checks.append({"where": where, "doc": doc_val, "calc": calc_val, "ok": doc_val == calc_val})


# Table 1
t1 = table_rows(body, 1)
for cond, r in zip(order, t1[1:]):
    s = rows[cond]
    n = int(s["n_eligible"])
    chk(f"T1 {cond} n", r[1], fint(n))
    chk(f"T1 {cond} measured", r[2], f1(100 * float(s["fraction_RTM"])))
    chk(f"T1 {cond} true", r[3], f1(100 * float(s["fraction_true_RTM"])))
    chk(f"T1 {cond} type3", r[4], f1(100 * float(s["fraction_type3"])))
    chk(f"T1 {cond} MPC", r[5], f1(float(s["MPC"])))

# S1
s1 = table_rows(supp, 1)
for cond, r in zip(order, s1[1:]):
    s = rows[cond]
    chk(f"S1 {cond} label", r[0], s["label"])
    for col, key in zip(r[1:], ["n_eligible", "both_count", "type3_count", "true_only_count", "neither_count"]):
        chk(f"S1 {cond} {key}", col, fint(s[key]))
    tot = sum(int(s[k]) for k in ["both_count", "type3_count", "true_only_count", "neither_count"])
    chk(f"S1 {cond} partition sums", tot, int(s["n_eligible"]))
    chk(f"S1 {cond} measured=both+type3", int(s["both_count"]) + int(s["type3_count"]), int(s["rtm_count"]))
    chk(f"S1 {cond} true=both+trueonly", int(s["both_count"]) + int(s["true_only_count"]), int(s["true_rtm_count"]))

# S2
s2 = table_rows(supp, 2)
for cond, r in zip(order, s2[1:]):
    s = rows[cond]
    chk(f"S2 {cond} type3%", r[1], f1(100 * float(s["fraction_type3"])))
    chk(f"S2 {cond} CI", r[2], f1(100 * float(s["fraction_type3_ci_lo"])) + " to " + f1(100 * float(s["fraction_type3_ci_hi"])))
    chk(f"S2 {cond} share", r[3], f1(100 * float(s["type3_share_measured_RTM"])))
    chk(f"S2 {cond} net", r[4], f1(float(s["net_measurement_difference_pp"])))
    net_from_tables = 100 * (float(s["fraction_RTM"]) - float(s["fraction_true_RTM"]))
    chk(f"S2 {cond} net==measured-true", round(net_from_tables, 9), round(float(s["net_measurement_difference_pp"]), 9))

# S3
s3 = table_rows(supp, 3)
fixed_order = ["baseline_perfect", "type3_sensitivity_90", "type3_sensitivity_80", "type3_sensitivity_70",
               "type3_far_1_per_month", "type3_far_1_per_week", "type3_far_1_per_day"]
for cond, r in zip(fixed_order, s3[1:]):
    s = rows[cond]
    chk(f"S3 {cond} n", r[1], fint(s["n_fixed"]))
    chk(f"S3 {cond} RTM", r[2], f1(100 * float(s["fixed_fraction_RTM"])))
    chk(f"S3 {cond} type3", r[3], f1(100 * float(s["fixed_fraction_type3"])))
    chk(f"S3 {cond} zeroB", r[4], fint(s["fixed_n_zero_baseline"]))
    chk(f"S3 {cond} MPC n", r[5], fint(s["fixed_n_mpc"]))
    chk(f"S3 {cond} MPC", r[6], f1(float(s["fixed_MPC"])))

# Prose numbers
P = lambda c, k: 100 * float(rows[c][k])
prose = [
    ("abstract elig 64.9", "64.9", f1(P("baseline_perfect", "fraction_eligible"))),
    ("abstract RTM 53.8", "53.8", f1(P("baseline_perfect", "fraction_RTM"))),
    ("abstract MPC 26.7", "26.7", f1(float(rows["baseline_perfect"]["MPC"]))),
    ("abstract transient 58.3", "58.3", f1(P("type1_transient_msf", "fraction_RTM"))),
    ("abstract threshold 57.9", "57.9", f1(P("type2_threshold_8", "fraction_RTM"))),
    ("abstract 70% RTM 59.0", "59.0", f1(P("type3_sensitivity_70", "fraction_RTM"))),
    ("abstract 70% type3 7.7", "7.7", f1(P("type3_sensitivity_70", "fraction_type3"))),
    ("abstract FAR1d RTM 69.9", "69.9", f1(P("type3_far_1_per_day", "fraction_RTM"))),
    ("abstract FAR1d type3 41.6", "41.6", f1(P("type3_far_1_per_day", "fraction_type3"))),
    ("abstract FAR1d share 59.4", "59.4", f1(P("type3_far_1_per_day", "type3_share_measured_RTM"))),
    ("3.1 649,098", "649,098", fint(rows["baseline_perfect"]["n_eligible"])),
    ("3.2 elig 75.6", "75.6", f1(P("type1_transient_msf", "fraction_eligible"))),
    ("3.2 MPC 36.8", "36.8", f1(float(rows["type1_transient_msf"]["MPC"]))),
    ("3.3 elig 40.4", "40.4", f1(P("type2_threshold_8", "fraction_eligible"))),
    ("3.3 MPC 29.4", "29.4", f1(float(rows["type2_threshold_8"]["MPC"]))),
    ("3.4 70% elig 55.2", "55.2", f1(P("type3_sensitivity_70", "fraction_eligible"))),
    ("3.4 70% MPC 33.3", "33.3", f1(float(rows["type3_sensitivity_70"]["MPC"]))),
    ("3.4 FAR1d elig 98.5", "98.5", f1(P("type3_far_1_per_day", "fraction_eligible"))),
    ("3.4 FAR1d MPC 46.0", "46.0", f1(float(rows["type3_far_1_per_day"]["MPC"]))),
    ("3.4 409,581", "409,581", fint(rows["type3_far_1_per_day"]["type3_count"])),
    ("3.4 55,966", "55,966", fint(rows["type3_far_1_per_day"]["true_only_count"])),
    ("3.4 net 35.9", "35.9", f1(float(rows["type3_far_1_per_day"]["net_measurement_difference_pp"]))),
    ("3.4 fixed 70% RTM 50.0", "50.0", f1(P("type3_sensitivity_70", "fixed_fraction_RTM"))),
    ("3.4 fixed FAR1d RTM 41.6", "41.6", f1(P("type3_far_1_per_day", "fixed_fraction_RTM"))),
    ("3.4 fixed 70% MPC 26.3", "26.3", f1(float(rows["type3_sensitivity_70"]["fixed_MPC"]))),
    ("3.4 fixed FAR1d MPC 17.6", "17.6", f1(float(rows["type3_far_1_per_day"]["fixed_MPC"]))),
    ("3.4 649,090", "649,090", fint(rows["type3_sensitivity_70"]["fixed_n_mpc"])),
    ("3.4 631,490", "631,490", fint(rows["type3_far_1_per_day"]["fixed_n_mpc"])),
]
ovd = {(r["overlap"], r["shock_msf_relation"]): r for r in ov}
prose += [
    ("3.2 baseline-only RTM 95.1", "95.1", f1(100 * float(ovd[("baseline", "all")]["fraction_RTM"]))),
    ("3.2 baseline-only MPC 92.6", "92.6", f1(float(ovd[("baseline", "all")]["MPC"]))),
    ("3.2 neither RTM 51.0", "51.0", f1(100 * float(ovd[("neither", "all")]["fraction_RTM"]))),
    ("3.2 neither MPC 25.9", "25.9", f1(float(ovd[("neither", "all")]["MPC"]))),
]
for where, d, c in prose:
    chk(where, d, c)
    if d not in body:
        checks.append({"where": where + " (string present in body?)", "doc": d, "calc": "absent", "ok": False})

bad = [c for c in checks if not c["ok"]]
out.write_text(json.dumps({"n_checks": len(checks), "n_fail": len(bad), "failures": bad, "checks": checks}, indent=1))
print("checks", len(checks), "failures", len(bad))
for b in bad:
    print(b)
