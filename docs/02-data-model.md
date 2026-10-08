# 2. Data model and formulas

This page shows how the old **Accountable Sales Planning Tool** workbook maps onto the new lists, so the math stays recognizable.

**One kind of activity: Sales Calls** (Lynwood, October 2026). An earlier version split in-person calls from gatekeeper contacts. They're now combined, with one target and one close rate. The gatekeeper columns are still in the lists but unused (saved as 0, and plans put 100% of new groups on sales calls). Internal column names still start with `Direct…` / `Indirect…`.

## Big changes from the workbook

| Workbook | New system | Why |
|---|---|---|
| One file per rep | One site; each rep sees only their own rows | Managers get a team view without opening 6 files |
| Separate Fall / Spring tabs, "2027" typed into 100+ formulas | **Season** is a dropdown that pulls from the Seasons list | A new year is one new row; nothing is rebuilt |
| Daily call entry on a 100-row sheet | **Daily activity log**, one quick entry per selling day | Logged while it's fresh; sales days are counted automatically (any day with activity) |
| One "in-person calls" number | **Sales calls** and **new groups** logged per selling day | Activity is tracked against the plan's sales-call target |
| Rep typed in a calls goal, and the sheet showed what it would produce | Rep sets the **goal and conversion rates**; the plan works **backward** to the calls needed, **plus 10%** | Reps see exactly how much activity the goal takes, with a cushion |
| Post-season actuals on the Goals tab | Same row as the plan, in **Program Plans** | Plan vs actual sit side by side |

### Workbook bugs that go away

1. **Fall Retained Units** were typed in as 0 on Fall Goals but calculated on Spring Goals. Now they're always calculated.
2. The Dashboard **Sales Days** tile compared the season name with the wrong cell (`'Fall Goals'!H5`), so it always showed Spring. Seasons are now looked up by ID.
3. **Two different goals:** the Dashboard used *Sales Goal Units* while the Annual Summary used *Projected Total Units*. Now there is one goal (**Sales Goal Units**), and the calls and contacts needed are worked out from it.
4. The hidden **Metrics** tab was all `#REF!` errors. It's gone.

### Retention: one definition everywhere

**For planning (from 2027 Spring on): a group is retained if it ran, any program, in the same season the year before** (Spring to Spring, Fall to Fall). Lynwood, October 2026. Set **Retention Rule** on these seasons to "Any program, same season last year".

Example, planning **2027 Spring**: of the rep's Spring 2025 groups, the ones they ran again in Spring 2026 are retained. That gives two rates, both filled in from MFP by `tools/build_plan_baseline.py`:

- **Unit Retention %** = Spring 2026 units from those returning groups ÷ the rep's Spring 2025 units. The plan math uses this one.
- **Group Retention %** = returning groups ÷ the rep's Spring 2025 groups. For reference.

**Each group's whole history is credited to the rep who owns it now** (Lynwood, October 2026), after the rollups and placed groups in `tools/mfp_rules.py`. So the groups moved from BPR to KJS count as KJS's in both years, and as retained for KJS if they ran both years. "Owns it now" is the group's current owning user in MFP if the pull includes it, otherwise the owner of its most recent fundraiser in the pull.

The earlier rule (2026 Spring and before, and the October 2026 baseline workbook) was "any program, either season last year". Each season records which rule its numbers were counted under (**Retention Rule** in the Seasons list). If you tighten the rule later (for example "Same program, same season last year"), set it on the new seasons. The Plan vs Actual view then shows which seasons aren't directly comparable.

| Column | Meaning |
|---|---|
| **Prior Year Units / Prior Year Groups** | That rep's units and number of groups in the **same season** last year (2027 Spring uses Spring 2026). This is the planning baseline. |
| **Retained Units** | Units this season from groups that ran last year (per the Retention Rule) |
| **Retained Groups** | Number of this season's groups that ran last year (per the Retention Rule) |
| **Unit Retention %** | Retained Units ÷ Prior Year Units. This is the plan's *Retention %* and the actual result |
| **Group Retention %** | Retained Groups ÷ Prior Year Groups |

**Read program-level retention with care.** Groups can switch programs and seasons and still count as retained, so a single program's retention % can go **over 100%**. For example, Wooden Spoon picks up schools that ran Butter Braid last year. That's expected. The rep's **total across all programs** is the cleanest retention number.

**Counting retained groups needs group-by-group matching** between this season and last year in MFP. That's only reliable if MFP has a stable group/organization ID (names get typed differently). Check this before trusting the first retention numbers.

The old workbook's actuals section divided retained units by **this** season's total units. That isn't comparable with the plan, so it's been replaced by the definitions above.

---

## Seasons (managers maintain)

| Column | Type | Notes |
|---|---|---|
| Season | Text | For example "2027 Fall". Shown in every dropdown |
| Season Start | Date | **Jan 1** for Spring, **Jul 1** for Fall (the same split as the MFP numbers) |
| Weeks | Number | Number of Fridays in the season, usually 26, sometimes 27. Used to show how far through the season you are, and to tell the weekly emails when the season has ended |
| Sales Days Goal | Number | Target number of selling days per rep for the season. Also used to show calls needed per selling day. The workbook had this per rep; if you want that again, it can move to the Program Plans or Reps list |
| Current Season | Yes/No | The app opens on this season |
| Retention Rule | Choice | Which rule counted this season's retained groups (default: any program, either season last year) |

## Reps (managers only)

| Column | Type |
|---|---|
| Rep Name | Text |
| Rep | Person (their M365 account) |
| MFP Owning User Code | Text (BLS, KJS, …) |
| Active | Yes/No. Untick when someone leaves; their history stays |

## Program Plans (one row per rep × season)

Each rep has **one plan per season for all programs combined**, saved with Program = **All Programs** (Lynwood, October 2026). The Program column and its other choices are kept in case you want a per-program split later.

The rep is whoever **created** the row ("Created By"). That's also what item-level security uses.

**How the plan works: backward from the goal.** The rep (or manager) sets the goal and the conversion rates, and the list works out how many calls and contacts the goal takes, then adds a **10% cushion** as the target.

```
Sales Goal Units            = Unit Goal      (or, if Unit Goal is blank, Prior Year Units × (1 + Growth %))
− Retained Units            = Prior Year Units × Retention %
= New Units Needed          (never below 0)
÷ Avg Units per Group       = New Groups Needed
÷ Sales Call Close %       = Sales Calls Needed
Target = Needed × 1.10, rounded up
```

Worked example (illustrative numbers, not anyone's real plan): prior 4,000 units, Unit Goal 5,000 (25% growth). Retention 75% → 3,000 retained, so 2,000 new units needed. Avg 250 units per new group → 8 new groups. At a 9% close rate → 89 sales calls needed, **target 98**.

**Pre-season inputs:**

| Column | Notes | Workbook row |
|---|---|---|
| Season, Program | | 4–5 |
| Prior Year Units | Same season last year, from the yearly MFP baseline | 7 |
| Prior Year Groups | Number of groups last year | new |
| Unit Goal | The main goal: units to sell this season. Internal name `GoalOverride` | (row 6) |
| Growth % (if no Unit Goal) | Optional fallback. Used only when Unit Goal is blank: goal = Prior Year Units × (1 + Growth %). Internal name `GrowthPct` | new |
| Unit Retention % | Share of last year's units expected back from returning groups (displayed as "Retention %" before October 2026) | 8 |
| Group Retention % | Share of last year's groups expected back. For reference; the math uses unit retention | new |
| Avg Units per Group | The rep's units ÷ groups in the same season last year, all their groups (displayed as "Avg Units per New Group" before October 2026) | 14 |
| Sales Call Close % | Share of sales calls that book a fundraiser (one blended rate; see the app guide for how to blend old in-person and gatekeeper rates) | 11/13 |
| % of New Groups from In-Person, Gatekeeper Close % | Unused. The app sets the first to 100% and hides both | |

**Calculated:**

| Column | Formula |
|---|---|
| Sales Goal Units | Unit Goal if filled in, otherwise Prior Year Units × (1 + Growth %) |
| Plan – Retained Units | Prior Year Units × Retention % |
| Plan – New Units Needed | Goal − Retained (never below 0) |
| Plan – New Groups Needed | New Units Needed ÷ Avg Units per Group |
| Sales Calls Needed | New Groups ÷ Sales Call Close %, rounded up (the formula still multiplies by the in-person share, which is 100%) |
| Sales Calls Target | Sales Calls Needed × 1.10, rounded up. **This is what the app tracks.** |
| Gatekeeper Contacts Needed / Target | Unused; 0 when the in-person share is 100% |

The cushion is a setting in the setup script (`-CallBuffer 0.10`). Changing it later means editing the two Target formulas in the list's column settings.

**Post-season inputs** (filled from the yearly MFP pull rather than typed by reps): Actual – Total Units, Total Groups, Retained Units (ran last year), Retained Groups (ran last year). These were workbook rows 22–24.

**Post-season calculated:**

| Column | Formula |
|---|---|
| Actual – Attainment % | Actual Total ÷ Sales Goal Units |
| Actual – Unit Retention % | Actual Retained Units ÷ Prior Year Units |
| Actual – Group Retention % | Actual Retained Groups ÷ Prior Year Groups |
| Actual – New Units | Total − Retained |
| Actual – New Groups | Total Groups − Retained Groups |
| Actual – Avg Units per New Group | New Units ÷ New Groups |
| Actual – Avg Units per Retained Group | Retained Units ÷ Retained Groups |

All divisions return 0 instead of an error when the bottom number is 0.

**Actual close rates are measured per rep over a full year, not per program or per season.** A call made in spring can book a group that runs in fall, so a one-season close rate would be too low in one season and too high in the next. The app counts all of a rep's calls and bookings from the Daily Activity log over the **last 12 months**, across both seasons. That's the realistic number to compare with the plan's close rates, and to use when setting next season's plan. Bookings are logged on the day they happen, and MFP decides which season the group's units count in.

**Percent columns:** in the list forms, type **50** for 50%. This was confirmed on the live site in October 2026: Retention 50 on 800 prior units gave 400 retained. SharePoint stores the value as a fraction (0.5), and that's what Power Apps and Power Automate read, which is why the Power App percent fields multiply and divide by 100 (see page 3).

## Rep Baselines (one row per rep × season, loaded from MFP)

Each rep's starting numbers for a season, worked out from the MFP pull by `tools/build_plan_baseline.py` and loaded by `tools/Import-RepBaselines.ps1`. My Plan pre-fills from it. Each row has its own permissions: managers Full Control, that rep Read, so a rep sees only their own row.

| Column | Notes |
|---|---|
| Season, Rep, Rep Code | The season being planned, and the rep (matched on MFP Owning User Code in the Reps list) |
| Prior Year Units, Prior Year Groups, Avg Units per Group | Same season last year |
| Unit Retention %, Group Retention % | Measured from the season two years back to last year (see Retention above) |
| Retention Measured From, Base Season Units / Groups, Retained Units / Groups | The working, so the percentages can be checked |

## Daily Activity (one row per rep × selling day)

| Column | Notes |
|---|---|
| Season | Lookup to Seasons |
| Activity Date | The day the activity happened |
| Sales Calls | Sales calls that day, in person or by phone |
| New Groups | New groups booked that day. Optional, but it shows the real close rate |
| Gatekeeper Contacts, New Groups Booked – Gatekeeper | Unused; the app saves 0 |
| MFP Units Season-to-Date | Optional. The running total from the MFP dashboard, entered whenever the rep checks it (at least weekly). The most recent entry counts. |
| Notes | Wins, blockers |
| Sales Day | Calculated: 1 if any sales calls were logged that day. Adds up to the sales days count |

Reps only log days they sell, so a week with no selling is simply a week with no rows.

**In-season scorecard math** (done in the app):

- Sales calls, new groups and sales days = sums of the season's rows
- Progress = done ÷ target (target = the +10% numbers, from the rep's plan for the season)
- Remaining = target − done; per selling day left = remaining ÷ (Sales Days Goal − sales days so far)
- Units to date = the most recent MFP Units Season-to-Date entry, compared with Sales Goal Units
- Close rate = new groups ÷ sales calls over the **last 12 months**, compared with the plan's close rate. A rate falling short of plan means more calls are needed than the target says
- Season elapsed % (today vs. Season Start and Weeks) is shown for reference only. Selling comes in bursts, so there is no week-by-week pace
