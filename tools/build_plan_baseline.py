"""Work out each rep's plan starting numbers for a season from MFP pull CSVs.

Usage: python tools/build_plan_baseline.py "<planner season>" <output .csv> <MFP pull .csv> [more pull .csv ...]
  e.g. python tools/build_plan_baseline.py "2027 Spring" "Plan Baseline 2027 Spring.csv" "MFP group sales 2024-2025.csv" "MFP group sales Spring 2025-2026.csv"

For "2027 Spring" (Lynwood, October 2026):
  Prior Year Units / Groups = the rep's Spring 2026 units and number of groups
  Avg Units per Group       = Spring 2026 units / Spring 2026 groups
  Unit Retention %          = Spring 2026 units from RETURNING groups / Spring 2025 units
  Group Retention %         = Spring 2026 returning groups / Spring 2025 groups
A group is RETURNING if it ran (any program) in either of the two seasons before - for Spring 2026 that is
Fall 2025 or Spring 2025 - and NEW if it ran in neither (the whole previous year). The weekly "MFP New Groups"
uses the same rule, so the plan's New Groups Needed and the groups booked are counted alike. Seasons are by
delivery date. Each group's history goes to the rep who owns it now (mfp_rules.current_owners).

The pulls must cover the same season two years back through last season (for 2027 Spring: Spring 2025, Fall 2025,
Spring 2026). Several pull files can be given; a fundraiser in more than one file is taken from the later file.
The output CSV is what tools/Import-RepBaselines.ps1 loads into the Rep Baselines list. Percentages are fractions.
"""
import sys, csv, collections
from mfp_rules import units, load, split_counted, current_owners, seasons_before

TARGET, OUT, SRCS = sys.argv[1], sys.argv[2], sys.argv[3:]
year, half = TARGET.split()                                          # planner "2027 Spring"
prior, base = f'{half} {int(year) - 1}', f'{half} {int(year) - 2}'   # MFP "Spring 2026", "Spring 2025"
lookback = seasons_before(prior)                                     # the year before the prior season

rows = load(*SRCS)
counted, _ = split_counted(rows)
present = {r['Season'] for r in counted}
missing = [s for s in [prior, base] + lookback if s not in present]
if missing:
    sys.exit(f'The pulls have no fundraisers for {", ".join(missing)}. Pull those seasons from MFP first.')

owner, source = current_owners(rows, counted)
ran = collections.defaultdict(set)
for r in counted:
    ran[r['Season']].add(r['Group ID'])
returning_set = ran[lookback[0]] | ran[lookback[1]]

by = collections.defaultdict(lambda: collections.defaultdict(float))   # (season, rep) -> group -> units
for r in counted:
    if r['Season'] in (prior, base):
        by[(r['Season'], owner[r['Group ID']])][r['Group ID']] += units(r)

reps = sorted({k[1] for k in by if k[1] != 'Unassigned'})
out = []
for code in reps:
    p, b = by[(prior, code)], by[(base, code)]
    kept = [g for g in p if g in returning_set]
    p_units, b_units = sum(p.values()), sum(b.values())
    kept_units = sum(p[g] for g in kept)
    out.append({
        'Season': TARGET, 'Rep Code': code,
        'Prior Year Units': round(p_units), 'Prior Year Groups': len(p),
        'Avg Units per Group': round(p_units / len(p), 1) if p else 0,
        'Unit Retention %': round(kept_units / b_units, 4) if b_units else 0,
        'Group Retention %': round(len(kept) / len(b), 4) if b else 0,
        'Base Season': base, 'Base Units': round(b_units), 'Base Groups': len(b),
        'Retained Units': round(kept_units), 'Retained Groups': len(kept),
    })

with open(OUT, 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(out[0]))
    w.writeheader(); w.writerows(out)

print(f'{TARGET}: prior season {prior}; returning = ran in {lookback[1]} or {lookback[0]}; '
      f'retention compared with {base}; groups credited to current owner from {source}')
print(f"{'Rep':5}{'Units':>9}{'Groups':>8}{'Avg':>8}{'Unit ret':>10}{'Group ret':>11}{'New grps':>10}")
for r in out:
    print(f"{r['Rep Code']:5}{r['Prior Year Units']:>9,}{r['Prior Year Groups']:>8}{r['Avg Units per Group']:>8}"
          f"{r['Unit Retention %']:>10.0%}{r['Group Retention %']:>11.0%}{r['Prior Year Groups'] - r['Retained Groups']:>10}")
left_out = sum(by[(prior, 'Unassigned')].values())
if left_out:
    print(f'{prior} units in groups whose current owner is not a current rep (left out): {left_out:,.0f}')
