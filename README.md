# Rite Bite Sales Planner

A replacement for the **Accountable Sales Planning Tool** Excel workbook, built on Microsoft 365. It's for 6 sales reps and 2 managers.

- **Reps** plan their season once, check in every Friday (about a minute, on their phone), and see their own scorecard.
- **Each rep sees only their own data.** SharePoint enforces this, not just the app.
- **Managers** (2) see a team view: attainment, direct and indirect activity vs pace, and missed check-ins.
- **Every Friday** an automatic email goes to reps who haven't checked in. **Every Monday** the managers get the list of who's still missing.
- **A new year or season** is one new row in a list. Nothing is rebuilt.

No new software to buy or host. It uses SharePoint Lists, Power Apps and Power Automate, which come with your Microsoft 365 licenses. (Confirm your plan in the M365 admin center; Power BI is the only optional piece that may need an extra license.)

## How it fits together

```
           Reps (phone)                           Managers
               │                                      │
      Rite Bite Sales Planner (Power App) ───── Team screen
               │
   ┌───────────┴─────────────── SharePoint site "Sales Planner" ─────────────────┐
   │  Seasons            Reps (roster)       Program Plans       Weekly Check-ins │
   │  managers edit,     managers only       plan + actuals,     Friday numbers,  │
   │  reps read                              rep sees own rows   rep sees own rows│
   └───────────────────────────────────────────────────────────────────────────────┘
               │
   Power Automate: Friday reminder to reps  ·  Monday "missing" list to managers
```

## Build order

| Step | Guide | Rough time |
|---|---|---|
| 1 | [Set up the site and lists](docs/01-setup.md) (runs `provisioning/Deploy-SalesPlanner.ps1`) | 30–60 min |
| 2 | [Data model and formulas](docs/02-data-model.md) (reference: how the workbook maps over) | read only |
| 3 | [Build the Power App](docs/03-power-app.md) | ½–1 day |
| 4 | [Friday reminder flows](docs/04-friday-reminder-flow.md) | 1 hour |
| 5 | [Yearly MFP pull](docs/05-mfp-yearly-pull.md) (prior-year and retention numbers, via Claude in Chrome) | under 1 hour (estimate) |

Times are estimates, not measurements.

## What changed from the workbook

- Weekly entry instead of daily (20 entries per season instead of 100)
- Direct calls and indirect contacts tracked separately in season, to match the plan
- One goal definition everywhere (Sales Goal Units). Projected units show whether the activity plan covers the goal
- Fixes 4 workbook bugs (Fall retained units, Dashboard sales-days tile, two conflicting goals, broken Metrics tab). Details in [docs/02-data-model.md](docs/02-data-model.md)

## Every season (managers, 5 minutes)

1. **Seasons** list → **+ New**: name (for example "2028 Spring"), start Monday, weeks (20), sales days goal, and retention rule (leave the default unless you've decided to change it).
2. Untick **Current Season** on the old season and tick it on the new one.
3. Tell reps to open **My Plan** in the app and add one row per program they're selling.
4. After the season: reps fill in **Season Results**. Managers review the **Plan vs Actual** view in the Program Plans list.

## Rep changes

- **New rep:** add them to the *Sales Planner Reps* group on the site and to the **Reps** list (name + MFP code), then share the app with them. Or re-run the setup script with their email added to `-RepEmails`.
- **Rep leaves:** untick **Active** in the Reps list and remove them from the group. Their history stays.
- **Territory move:** history stays with the rep who entered it. Reassigning accounts in MFP doesn't change anything here.

## Status

- **SharePoint setup:** run on the live site (ritebitefundraising.sharepoint.com/sites/SalesPlanner) on October 6, 2026. All four lists were created and the plan formulas checked against a test row.
- **Power App and reminder flows:** not built yet. Their formulas haven't been tested in the tenant, so plan for a short round of fixes when building them.
