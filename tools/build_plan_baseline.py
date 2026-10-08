"""Work out each rep's plan starting numbers for a season from the MFP pull CSV.

Usage: python tools/build_plan_baseline.py <MFP pull .csv> "<planner season>" <output .csv>
  e.g. python tools/build_plan_baseline.py "MFP group sales 2025-2026.csv" "2027 Spring" "Plan Baseline 2027 Spring.csv"

For "2027 Spring" (Lynwood, October 2026):
  Prior Year Units / Groups = the rep's Spring 2026 units and number of groups
  Avg Units per Group       = Spring 2026 units / Spring 2026 groups
  Unit Retention %          = Spring 2026 units from groups that also ran Spring 2025 / Spring 2025 units
  Group Retention %         = Spring 2025 groups that ran again in Spring 2026 / Spring 2025 groups
Same season only (Spring to Spring, Fall to Fall), any program. A fundraiser belongs to its MFP owning user,
after the rollups and placed groups in mfp_rules.py; a group counts as retained only if the same rep ran it
both years. The pull must cover both years (here 2025 and 2026).

The output CSV is what tools/Import-RepBaselines.ps1 loads into the Rep Baselines list. Percentages are
fractions (0.75 = 75%), the way SharePoint stores them.
"""
import sys, csv, collections
from mfp_rules import OWNER_OVERRIDES, rep_of, units, load, split_counted

SRC, TARGET, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
year, half = TARGET.split()                      # planner names seasons "2027 Spring"
prior, base = f'{half} {int(year) - 1}', f'{half} {int(year) - 2}'   # MFP names them "Spring 2026"

counted, _ = split_counted(load(SRC))
seasons_in_pull = {r['Season'] for r in counted}
for s in (prior, base):
    if s not in seasons_in_pull:
        sys.exit(f'The pull has no {s} fundraisers. Pull {int(year) - 2}-{int(year) - 1} from MFP first.')

def rep(r):
    return OWNER_OVERRIDES.get(r['Group ID']) or rep_of(r['Owning User'])

# units[(season, rep)][group] = units
by = collections.defaultdict(lambda: collections.defaultdict(float))
for r in counted:
    if r['Season'] in (prior, base):
        by[(r['Season'], rep(r))][r['Group ID']] += units(r)

reps = sorted({k[1] for k in by if k[1] != 'Unassigned'})
rows = []
for code in reps:
    p, b = by[(prior, code)], by[(base, code)]
    kept = [g for g in b if g in p]
    p_units, b_units = sum(p.values()), sum(b.values())
    kept_units = sum(p[g] for g in kept)
    rows.append({
        'Season': TARGET, 'Rep Code': code,
        'Prior Year Units': round(p_units), 'Prior Year Groups': len(p),
        'Avg Units per Group': round(p_units / len(p), 1) if p else 0,
        'Unit Retention %': round(kept_units / b_units, 4) if b_units else 0,
        'Group Retention %': round(len(kept) / len(b), 4) if b else 0,
        'Base Season': base, 'Base Units': round(b_units), 'Base Groups': len(b),
        'Retained Units': round(kept_units), 'Retained Groups': len(kept),
    })

with open(OUT, 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader(); w.writerows(rows)

print(f'{TARGET}: prior season {prior}, retention measured {base} -> {prior}')
print(f"{'Rep':5}{'Units':>9}{'Groups':>8}{'Avg':>8}{'Unit ret':>10}{'Group ret':>11}")
for r in rows:
    print(f"{r['Rep Code']:5}{r['Prior Year Units']:>9,}{r['Prior Year Groups']:>8}{r['Avg Units per Group']:>8}"
          f"{r['Unit Retention %']:>10.0%}{r['Group Retention %']:>11.0%}")
left_out = sum(by[(prior, 'Unassigned')].values())
if left_out:
    print(f'{prior} units owned by former reps and not placed (left out): {left_out:,.0f}')
