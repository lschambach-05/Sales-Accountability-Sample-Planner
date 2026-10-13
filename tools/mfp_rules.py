"""Shared rules for turning the MFP pull CSV into rep numbers (Lynwood, October 2026).

Used by build_rep_baseline.py and build_plan_baseline.py. Update these when reps or programs change.
"""
import csv

CURRENT = ['BPR', 'JK', 'JMK', 'KJP', 'KJS', 'RB']
ROLLUP = {'BLS': 'KJS', 'LBS': 'KJP', 'LMD': 'JMK'}
PROGRAMS = {'Braided Pastry': 'Butter Braid Pastry', 'Combo': 'Combo', 'Wooden Spoon': 'Wooden Spoon CD',
            'Joyful Traditions': 'Joyful Tradition', 'Bella Napoli': 'Bella Napoli', 'Croissant Crown': 'Croissant Crowns',
            # Batavia Music Buffs is one group that runs all products; MFP names its program by year.
            # It is not a planner program, so its units count under Combo (Lynwood, Oct 2026).
            'Batavia Music Buffs 2023': 'Combo', 'Batavia Music Buffs 2025': 'Combo'}
PROG_ORDER = ['Butter Braid Pastry', 'Combo', 'Wooden Spoon CD', 'Joyful Tradition', 'Bella Napoli', 'Croissant Crowns',
              'Other (review)']
# Duplicate MFP group records for the same organization: {duplicate Group ID: Group ID to keep}.
GROUP_MERGES = {'199961': '84951'}   # St. Paul's Lutheran School (JK) - confirmed same school, Oct 2026
# Groups whose last owner is no longer a rep: {Group ID: current rep}. Filled in from the location match.
OWNER_OVERRIDES = {   # from MFP group locations.csv (Oct 2026): most groups in same city, else same county
    '163565': 'KJP',  # Troop 1024, Pound WI - city
    '191059': 'KJS',  # Trail Life IL 2237, Rockford IL - city
    '191570': 'BPR',  # Lake County Lightning 12u, Hawthorn Woods IL - city
    '191969': 'BPR',  # Scouts BSA Troop 815, Chicago IL - city
    '192955': 'KJP',  # New Holstein HS Band/Choir, New Holstein WI - Calumet County
    '193455': 'KJP',  # Boy Scout Troop 1044, De Pere WI - Brown County
    '202009': 'KJP',  # Troop 601, Oshkosh WI - city
}

def rep_of(code):
    code = ROLLUP.get(code, code)
    return code if code in CURRENT else 'Unassigned'

def units(r): return float(r['Units'] or 0)

def load(*paths):
    """Read one or more pull CSVs and fold duplicate group records together (GROUP_MERGES). When the same
    fundraiser is in more than one file, the later file wins."""
    by_id = {}
    for path in paths:
        for r in csv.DictReader(open(path, newline='', encoding='utf-8-sig')):
            by_id[r['Fundraiser ID']] = r
    rows = list(by_id.values())
    for r in rows:
        r['Original Group ID'] = r['Group ID']
        r['Group ID'] = GROUP_MERGES.get(r['Group ID'], r['Group ID'])
    return rows

def split_counted(rows):
    """Closed fundraisers, plus Open ones that were invoiced (units sold), count.
    Canceled fundraisers and fundraisers with no units are left out."""
    counted, excluded = [], []
    for r in rows:
        if r['Status'] == 'Canceled':
            excluded.append((r, 'Canceled')); continue
        if units(r) <= 0:
            excluded.append((r, 'Open/closed with no units sold' if r['Status'] == 'Open' else 'Closed with no units')); continue
        counted.append(r)
    return counted, excluded

def current_owners(rows, counted):
    """Group ID -> the rep who owns the group now (Lynwood, October 2026: a group's whole history goes to its
    current rep). Uses the pull's "Group Owner" column (MFP's current owner on the group record) when it names a
    current rep; otherwise the placed groups in OWNER_OVERRIDES; otherwise the owner of the group's most recent
    fundraiser, after the rollups. Returns (owners, description of the source used)."""
    latest = {}
    for r in counted or rows:
        key = (r['Delivery Date'] or r['Start Date'], r['Fundraiser ID'])
        if r['Group ID'] not in latest or key > latest[r['Group ID']][0]:
            latest[r['Group ID']] = (key, r['Owning User'])
    for r in rows:                     # groups with only canceled/unsold fundraisers still need an owner
        latest.setdefault(r['Group ID'], ((r['Delivery Date'] or r['Start Date'], r['Fundraiser ID']), r['Owning User']))
    group_owner = {r['Group ID']: r['Group Owner'] for r in rows if (r.get('Group Owner') or '').strip()}
    def owner(g, last):
        if g in group_owner and rep_of(group_owner[g]) != 'Unassigned':
            return rep_of(group_owner[g])
        return OWNER_OVERRIDES.get(g) or rep_of(last)
    source = "the pull's Group Owner column" if group_owner else 'the most recent fundraiser in the pull'
    return {g: owner(g, v[1]) for g, v in latest.items()}, source

def seasons_before(season, n=2):
    """The n seasons just before an MFP season name: seasons_before('Spring 2027') -> ['Fall 2026', 'Spring 2026']."""
    half, year = season.split(); year = int(year); out = []
    for _ in range(n):
        half, year = ('Fall', year - 1) if half == 'Spring' else ('Spring', year)
        out.append(f'{half} {year}')
    return out
