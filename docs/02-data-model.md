# 2. Data model and formulas

This page shows how the old **Accountable Sales Planning Tool** workbook maps onto the new lists, so the math stays recognizable.

## Big changes from the workbook

| Workbook | New system | Why |
|---|---|---|
| One file per rep | One site; each rep sees only their own rows | Managers get a team view without opening 6 files |
| Separate Fall / Spring tabs, "2027" typed into 100+ formulas | **Season** is a dropdown that pulls from the Seasons list | A new year is one new row; nothing is rebuilt |
| Daily call entry on a 100-row sheet | **Daily activity log**, one quick entry per selling day | Logged while it's fresh; sales days are counted automatically (any day with activity) |
| One "in-person calls" number | **Direct calls** and **indirect contacts** logged separately, plus new groups booked by each | Activity is tracked against the plan's direct and indirect targets |
| Rep typed in a calls goal, and the sheet showed what it would produce | Rep sets the **goal and conversion rates**; the plan works **backward** to the calls needed, **plus 10%** | Reps see exactly how much activity the goal takes, with a cushion |
| Post-season actuals on the Goals tab | Same row as the plan, in **Program Plans** | Plan vs actual sit side by side |

### Workbook bugs that go away

1. **Fall Retained Units** were typed in as 0 on Fall Goals but calculated on Spring Goals. Now they're always calculated.
2. The Dashboard **Sales Days** tile compared the season name with the wrong cell (`'Fall Goals'!H5`), so it always showed Spring. Seasons are now looked up by ID.
3. **Two different goals:** the Dashboard used *Sales Goal Units* while the Annual Summary used *Projected Total Units*. Now there is one goal (**Sales Goal Units**), and the calls and contacts needed are worked out from it.
4. The hidden **Metrics** tab was all `#REF!` errors. It's gone.

### Retention: one definition everywhere

**A group is retained if it ran any program, in either season, the previous year.** Its units count toward the program it's running *this* season.

Example: a school ran Butter Braid in Spring 2025 and runs Wooden Spoon in Fall 2026. It's a retained group, and its units are retained units on the rep's **Wooden Spoon** row for 2026 Fall.

Each season records which rule its numbers were counted under (**Retention Rule** in the Seasons list). The default is "Any program, either season last year". If you tighten the rule later (for example "Same program, same season last year"), set it on the new seasons. The Plan vs Actual view then shows which seasons aren't directly comparable.

| Column | Meaning |
|---|---|
| **Prior Year Units / Prior Year Groups** | That rep's units and number of groups for this program in the **same season** last year (2026 Fall uses 2025 Fall). This is the planning baseline. |
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

## Program Plans (one row per rep × season × program)

The rep is whoever **created** the row ("Created By"). That's also what item-level security uses.

**How the plan works: backward from the goal.** The rep (or manager) sets the goal and the conversion rates, and the list works out how many calls and contacts the goal takes, then adds a **10% cushion** as the target.

```
Sales Goal Units            = Prior Year Units × (1 + Growth Goal %)      (or the Goal Units Override, if filled in)
− Retained Units            = Prior Year Units × Retention %
= New Units Needed          (never below 0)
÷ Avg Units per New Group   = New Groups Needed
× % of New Groups from Direct          → direct groups   ÷ Direct Close %   = Direct Calls Needed
× (1 − % of New Groups from Direct)    → indirect groups ÷ Indirect Close % = Indirect Contacts Needed
Target = Needed × 1.10, rounded up
```

Worked example (illustrative numbers, not anyone's real plan): prior 4,000 units, growth 25% → goal 5,000. Retention 75% → 3,000 retained, so 2,000 new units needed. Avg 250 units per new group → 8 new groups. 60% from direct at a 20% close rate → 24 direct calls needed, **target 27**. 40% from indirect at 5% → 64 indirect contacts needed, **target 71**.

**Pre-season inputs:**

| Column | Notes | Workbook row |
|---|---|---|
| Season, Program | | 4–5 |
| Prior Year Units | Same season last year, from the yearly MFP baseline | 7 |
| Prior Year Groups | Number of groups last year | new |
| Growth Goal % | How much to grow on last year's units | new |
| Goal Units Override | Optional. A set unit goal instead of growth %, for example a program the rep didn't sell last year | (row 6) |
| Retention % | Share of last year's units expected back from returning groups | 8 |
| Avg Units per New Group | | 14 |
| % of New Groups from Direct | How the new groups are expected to split between direct and indirect | new |
| Direct Close % | Share of direct calls that book a fundraiser | 11 |
| Indirect Close % | Share of indirect contacts that book a fundraiser | 13 |

**Calculated:**

| Column | Formula |
|---|---|
| Sales Goal Units | Override if filled in, otherwise Prior Year Units × (1 + Growth Goal %) |
| Plan – Retained Units | Prior Year Units × Retention % |
| Plan – New Units Needed | Goal − Retained (never below 0) |
| Plan – New Groups Needed | New Units Needed ÷ Avg Units per New Group |
| Direct Calls Needed | New Groups × direct share ÷ Direct Close %, rounded up |
| Direct Calls Target | Direct Calls Needed × 1.10, rounded up. **This is what the app tracks.** |
| Indirect Contacts Needed | New Groups × indirect share ÷ Indirect Close %, rounded up |
| Indirect Contacts Target | Indirect Contacts Needed × 1.10, rounded up. **This is what the app tracks.** |

The cushion is a setting in the setup script (`-CallBuffer 0.10`). Changing it later means editing the two Target formulas in the list's column settings.

**Post-season inputs:** Actual – Total Units, Retained Units (ran last year), Retained Groups (ran last year), Direct Calls, Direct Bookings, Indirect Contacts, Indirect Bookings (workbook rows 22–24, 28–29, 31–32).

**Post-season calculated:**

| Column | Formula |
|---|---|
| Actual – Attainment % | Actual Total ÷ Sales Goal Units |
| Actual – Unit Retention % | Actual Retained Units ÷ Prior Year Units |
| Actual – Group Retention % | Actual Retained Groups ÷ Prior Year Groups |
| Actual – New Units | Total − Retained |
| Actual – New Groups | Direct + Indirect bookings |
| Actual – Direct / Indirect Close % | Bookings ÷ calls (or contacts) |
| Actual – Avg Units per New Group | New Units ÷ New Groups |
| Actual – Avg Units per Retained Group | Retained Units ÷ Retained Groups |

All divisions return 0 instead of an error when the bottom number is 0.

**Percent columns:** in the list forms, type **50** for 50%. This was confirmed on the live site in October 2026: Retention 50 on 800 prior units gave 400 retained. SharePoint stores the value as a fraction (0.5), and that's what Power Apps and Power Automate read, which is why the Power App percent fields multiply and divide by 100 (see page 3).

## Daily Activity (one row per rep × selling day)

| Column | Notes |
|---|---|
| Season | Lookup to Seasons |
| Activity Date | The day the activity happened |
| Direct Calls | Direct sales calls that day |
| Indirect Contacts | Indirect contacts that day |
| New Groups Booked – Direct / Indirect | Optional, but it shows the real close rate during the season |
| MFP Units Season-to-Date | Optional. The running total from the MFP dashboard, entered whenever the rep checks it (at least weekly). The most recent entry counts. |
| Notes | Wins, blockers |
| Sales Day | Calculated: 1 if any calls or contacts were logged that day. Adds up to the sales days count |

Reps only log days they sell, so a week with no selling is simply a week with no rows.

**In-season scorecard math** (done in the app):

- Direct calls, indirect contacts, bookings and sales days = sums of the season's rows
- Progress = done ÷ target (target = the +10% numbers, summed across the rep's program rows)
- Remaining = target − done; per selling day left = remaining ÷ (Sales Days Goal − sales days so far)
- Units to date = the most recent MFP Units Season-to-Date entry, compared with Sales Goal Units
- Close rate so far = bookings ÷ calls (or contacts), compared with the plan's close rates. A rate falling short of plan means more calls are needed than the target says
- Season elapsed % (today vs. Season Start and Weeks) is shown for reference only. Selling comes in bursts, so there is no week-by-week pace
