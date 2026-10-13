"""Weekly MFP numbers for each rep's scorecard: season-to-date units and new groups booked.

Usage: python tools/build_rep_progress.py <weekly MFP pull .csv> "<planner season>" <as-of date YYYY-MM-DD> <output .csv>
  e.g. python tools/build_rep_progress.py "MFP progress 2027-03-08.csv" "2027 Spring" 2027-03-08 "Rep Progress 2027 Spring.csv"

Rules (Lynwood, October 2026):
  MFP Units to Date  = units on the rep's fundraisers delivered in the current season (canceled left out).
  MFP New Groups     = groups booked for the current season (not canceled) that did NOT run in the same season
                       last year: never ran, or lapsed. The same "new" the plan's New Groups Needed counts.
  MFP New Groups 12 Mo = new groups (same rule, each against its own season a year earlier) whose fundraiser was
                       booked ("Booked On") in the 12 months up to the as-of date. Divided by the sales calls reps
                       logged in the same 12 months, this is the close rate on Home and Team.
  Each group counts for the rep who owns it now (mfp_rules.current_owners). A booking counts once per group per
  season. An Open fundraiser with nothing sold more than 30 days after its delivery date is treated as dead.

The pull must cover deliveries from the start of the same season two years back to the end of the current season
(for 2027 Spring: January 1, 2025 to June 30, 2027), and include each fundraiser's "Booked On" date.
The output CSV is what tools/Import-RepProgress.ps1 loads into the Rep Baselines list.
"""
import sys, csv, collections, datetime as dt
from mfp_rules import units, load, split_counted, current_owners

SRC, TARGET, ASOF, OUT = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
asof = dt.date.fromisoformat(ASOF)
year, half = TARGET.split()                          # planner "2027 Spring" -> MFP "Spring 2027"
season = f'{half} {year}'

def d(s):
    return dt.date.fromisoformat(s[:10]) if s else None

def last_year(s):                                    # "Spring 2027" -> "Spring 2026"
    h, y = s.split(); return f'{h} {int(y) - 1}'

rows = load(SRC)
counted, _ = split_counted(rows)                     # closed or invoiced: these "ran"
owner, source = current_owners(rows, counted)

ran = collections.defaultdict(set)                   # season -> groups that ran
for r in counted:
    ran[r['Season']].add(r['Group ID'])

def is_booking(r):
    """A live booking: not canceled, and not an unsold Open fundraiser well past its delivery date."""
    if r['Status'] == 'Canceled':
        return False
    delivered = d(r['Delivery Date'])
    if r['Status'] == 'Open' and units(r) <= 0 and delivered and (asof - delivered).days > 30:
        return False
    return True

bookings = [r for r in rows if is_booking(r)]
missing_booked_on = sum(1 for r in bookings if not r.get('Booked On'))
seasons_needed = {season, last_year(season)}
if not seasons_needed <= set(ran) | {r['Season'] for r in bookings}:
    sys.exit(f'The pull is missing {sorted(seasons_needed - set(ran))}. See the date window in this script\'s notes.')

units_to_date = collections.Counter()
new_season = collections.defaultdict(set)
new_12mo = collections.defaultdict(set)
for r in bookings:
    g, rep, s = r['Group ID'], owner[r['Group ID']], r['Season']
    if s == season:
        units_to_date[rep] += units(r)
    is_new = g not in ran[last_year(s)]
    if s == season and is_new:
        new_season[rep].add(g)
    booked = d(r.get('Booked On', ''))
    if is_new and booked and 0 <= (asof - booked).days <= 365:
        new_12mo[rep].add((g, s))

reps = sorted((set(units_to_date) | set(new_season) | set(new_12mo)) - {'Unassigned'})
out = [{'Season': TARGET, 'Rep Code': rep, 'MFP Units to Date': round(units_to_date[rep]),
        'MFP New Groups': len(new_season[rep]), 'MFP New Groups 12 Mo': len(new_12mo[rep]), 'As Of': ASOF}
       for rep in reps]
with open(OUT, 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)

print(f'{TARGET} as of {ASOF}; groups credited to current owner from {source}')
print(f"{'Rep':5}{'Units':>9}{'New grps':>10}{'New 12 mo':>11}")
for r in out:
    print(f"{r['Rep Code']:5}{r['MFP Units to Date']:>9,}{r['MFP New Groups']:>10}{r['MFP New Groups 12 Mo']:>11}")
print(f"Season units, all reps: {sum(units_to_date[r] for r in reps):,.0f} "
      f"(left out, groups whose owner isn't a current rep: {units_to_date['Unassigned']:,.0f})")
if missing_booked_on:
    print(f'WARNING: {missing_booked_on} bookings have no Booked On date; they are left out of the 12-month count.')
