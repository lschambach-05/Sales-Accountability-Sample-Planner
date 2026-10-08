# Rite Bite Sales Planner

A replacement for the **Accountable Sales Planning Tool** Excel workbook, built on Microsoft 365. It's for 6 sales reps and 2 managers.

- **Reps** set one season goal (all programs combined) with their retention and conversion rates. The plan works backward to the **calls and contacts needed, plus a 10% cushion**.
- **Each selling day**, reps log their calls, contacts and bookings in about 20 seconds on their phone, and see their progress against target.
- **Each rep sees only their own data.** SharePoint enforces this, not just the app.
- **Managers** (2) see a team view: units vs goal, sales calls vs target, groups booked vs needed, and each rep's last activity date.
- **Every Friday** an email reminds any rep who logged nothing that week. **Every Monday** the managers get a digest of last week's activity.
- **A new year or season** is one new row in a list. Nothing is rebuilt.

No new software to buy or host. It uses SharePoint Lists, Power Apps and Power Automate, which come with your Microsoft 365 licenses. (Confirm your plan in the M365 admin center; Power BI is the only optional piece that may need an extra license.)

## How it fits together

```
           Reps (phone)                           Managers
               │                                      │
      Rite Bite Sales Planner (Power App) ───── Team screen
               │
   ┌───────────┴─────────────── SharePoint site "Sales Planner" ─────────────────┐
   │  Seasons            Reps (roster)       Program Plans       Daily Activity   │
   │  managers edit,     managers only       plan + actuals,     one row per      │
   │  reps read                              rep sees own rows   selling day, own │
   └───────────────────────────────────────────────────────────────────────────────┘
               │
   Power Automate: Friday reminder to reps  ·  Monday activity digest to managers
```

## Build order

| Step | Guide | Rough time |
|---|---|---|
| 1 | [Set up the site and lists](docs/01-setup.md) (runs `provisioning/Deploy-SalesPlanner.ps1`) | 30–60 min |
| 2 | [Data model and formulas](docs/02-data-model.md) (reference: how the workbook maps over) | read only |
| 3 | [Build the Power App](docs/03-power-app.md) | ½–1 day |
| 4 | [Weekly emails](docs/04-friday-reminder-flow.md) | 1 hour |
| 5 | [Yearly MFP pull](docs/05-mfp-yearly-pull.md) (prior-year and retention numbers, via Claude in Chrome) | under 1 hour (estimate) |

Times are estimates, not measurements.

## What changed from the workbook

- Weekly entry instead of daily (20 entries per season instead of 100)
- One activity number, **sales calls**, with one target and one close rate
- One goal definition everywhere (Sales Goal Units). Projected units show whether the activity plan covers the goal
- Fixes 4 workbook bugs (Fall retained units, Dashboard sales-days tile, two conflicting goals, broken Metrics tab). Details in [docs/02-data-model.md](docs/02-data-model.md)

## Every season (managers, 5 minutes)

1. **Seasons** list → **+ New**: name (for example "2028 Spring"), start date (Jan 1 for Spring, Jul 1 for Fall), weeks (the number of Fridays in the season, usually 26), sales days goal, and retention rule (leave the default unless you've decided to change it).
2. Untick **Current Season** on the old season and tick it on the new one.
3. Tell reps to open **My Plan** in the app and fill in their plan for the season (one plan, all programs combined).
4. After the season: enter actuals from the yearly MFP pull. Managers review the **Plan vs Actual** view in the Program Plans list.

## Rep changes

- **New rep:** add them to the *Sales Planner Reps* group on the site and to the **Reps** list (name + MFP code), then share the app with them. Or re-run the setup script with their email added to `-RepEmails`.
- **Rep leaves:** untick **Active** in the Reps list and remove them from the group. Their history stays.
- **Territory move:** history stays with the rep who entered it. Reassigning accounts in MFP doesn't change anything here.

## Status

- **SharePoint setup:** run on the live site (ritebitefundraising.sharepoint.com/sites/SalesPlanner) on October 6, 2026, then re-run the same day for the backward-from-goal plan, the Daily Activity list and the In-Person / Gatekeeper labels. A test row checked out on the live site. On October 8, in-person calls and gatekeeper contacts were combined into **Sales Calls** (columns renamed on the live site).
- **Power App:** Home, Log a Day and My Plan are built and checked live (October 8, 2026). My Plan is one total plan per rep per season, with Unit Goal as the main input and one Sales Call Close %. Home checked: 25,000 goal, 9% close → 440 sales calls. Still to build: Team screen. Season Results is optional.
- **MFP starting numbers:** `tools/build_plan_baseline.py` + `tools/Import-RepBaselines.ps1` load each rep's prior-year units and groups, unit and group retention (same season, year over year) and average units per group into a new **Rep Baselines** list, and My Plan pre-fills from it ([docs/05](docs/05-mfp-yearly-pull.md#plan-starting-numbers-for-each-rep-pre-filled-in-my-plan)). Written October 8, 2026; not yet run on the live site.
- **Reminder flows:** not built yet. Their steps haven't been tested in the tenant, so plan for a short round of fixes.
