"""Weekly MFP numbers for each rep's scorecard: season-to-date units and new groups booked. All by delivery date.

Usage: python tools/build_rep_progress.py "<planner season>" <as-of date YYYY-MM-DD> <output .csv> <weekly MFP pull .csv> [more .csv ...]
  e.g. python tools/build_rep_progress.py "2027 Spring" 2027-03-08 "Rep Progress 2027 Spring.csv" "MFP progress 2027-03-08.csv"

Rules (Lynwood, October 2026):
  MFP Units to Date     = units on the rep's fundraisers delivered in the current season (canceled left out).
  MFP New Groups        = groups booked for the current season (by delivery date, not canceled) that did NOT run
                          in either of the two seasons before - for Spring 2027: not Fall 2026 and not Spring 2026.
                          The same "new" as the plan baseline (build_plan_baseline.py).
  MFP New Groups 12 Mo  = new groups (same rule, each against the year before its own season) in the current season
                          plus the season before - about a year of bookings. Divided by the sales calls reps logged in
                          the last 12 months, this is the close rate on Home and Team. The fundraiser's "Booked On" date
                          isn't used: groups often book a year ahead, so it doesn't show when the sale was won.
  Each group counts for the rep who owns it now (mfp_rules.current_owners), once per season. A fundraiser counts as
  run or booked unless it's Canceled, Closed with no units, or Open with nothing sold more than 30 days after its
  delivery date. So a group booked for a season that's still under way (Open, nothing invoiced yet) already counts as
  running that season, and isn't "new" next season.

The pull must cover deliveries from the start of the season three seasons back to the end of the current season
(for 2027 Spring: July 1, 2025 to June 30, 2027). The output CSV is what tools/Import-RepProgress.ps1 loads.
"""
import sys, collections, csv, datetime as dt
from mfp_rules import units, load, split_counted, current_owners, seasons_before

TARGET, ASOF, OUT, SRCS = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]
asof = dt.date.fromisoformat(ASOF)
year, half = TARGET.split()
season = f'{half} {year}'                            # MFP name, "Spring 2027"
last = seasons_before(season, 1)[0]                  # "Fall 2026"

rows = load(*SRCS)
counted, _ = split_counted(rows)
owner, source = current_owners(rows, counted)

def is_booking(r):
    if r['Status'] == 'Canceled':
        return False
    if units(r) <= 0:
        if r['Status'] == 'Closed':
            return False
        delivered = dt.date.fromisoformat(r['Delivery Date'][:10]) if r['Delivery Date'] else None
        if delivered and (asof - delivered).days > 30:
            return False
    return True

ran = collections.defaultdict(set)                   # season -> groups that ran or are booked to run
for r in rows:
    if is_booking(r):
        ran[r['Season']].add(r['Group ID'])

needed = seasons_before(season, 3)                   # history needed to judge "new" for this season and last
missing = [s for s in needed if s not in ran]
if missing:
    sys.exit(f'The pull has no fundraisers for {", ".join(missing)}. Widen the date window (see notes at the top).')

def is_new(g, s):
    return not any(g in ran[p] for p in seasons_before(s))

units_to_date = collections.Counter()
new_season = collections.defaultdict(set)
new_year = collections.defaultdict(set)
for r in rows:
    if not is_booking(r):
        continue
    g, rep, s = r['Group ID'], owner[r['Group ID']], r['Season']
    if s == season:
        units_to_date[rep] += units(r)
        if is_new(g, s):
            new_season[rep].add(g)
    if s in (season, last) and is_new(g, s):
        new_year[rep].add((g, s))

reps = sorted((set(units_to_date) | set(new_season) | set(new_year)) - {'Unassigned'})
out = [{'Season': TARGET, 'Rep Code': rep, 'MFP Units to Date': round(units_to_date[rep]),
        'MFP New Groups': len(new_season[rep]), 'MFP New Groups 12 Mo': len(new_year[rep]), 'As Of': ASOF}
       for rep in reps]
with open(OUT, 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)

print(f'{TARGET} as of {ASOF}; new = not run in the two seasons before; 12-month count = {last} + {season}; '
      f'groups credited to current owner from {source}')
print(f"{'Rep':5}{'Units':>9}{'New grps':>10}{'New 12 mo':>11}")
for r in out:
    print(f"{r['Rep Code']:5}{r['MFP Units to Date']:>9,}{r['MFP New Groups']:>10}{r['MFP New Groups 12 Mo']:>11}")
print(f"Season units, all reps: {sum(units_to_date[r] for r in reps):,.0f} "
      f"(left out, groups whose owner isn't a current rep: {units_to_date['Unassigned']:,.0f})")
