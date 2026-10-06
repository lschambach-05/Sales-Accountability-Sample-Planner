# 2. Data model and formulas

This page shows how the old **Accountable Sales Planning Tool** workbook maps onto the new lists, so the math stays recognizable.

## Big changes from the workbook

| Workbook | New system | Why |
|---|---|---|
| One file per rep | One site; each rep sees only their own rows | Managers get a team view without opening 6 files |
| Separate Fall / Spring tabs, "2027" typed into 100+ formulas | **Season** is a dropdown that pulls from the Seasons list | A new year is one new row; nothing is rebuilt |
| Daily call entry (100 cells per season) | **Weekly** check-in | Daily detail was only used to count sales days, so reps now enter sales days directly |
| One "in-person calls" number | **Direct calls** and **indirect contacts** logged separately, plus new groups booked by each | In-season results can be compared with the plan's direct/indirect goals |
| Post-season actuals on the Goals tab | Same row as the plan, in **Program Plans** | Plan vs actual sit side by side |

### Workbook bugs that go away

1. **Fall Retained Units** were typed in as 0 on Fall Goals but calculated on Spring Goals. Now they're always calculated.
2. The Dashboard **Sales Days** tile compared the season name with the wrong cell (`'Fall Goals'!H5`), so it always showed Spring. Seasons are now looked up by ID.
3. **Two different goals:** the Dashboard used *Sales Goal Units* while the Annual Summary used *Projected Total Units*. Now **Sales Goal Units is the target** everywhere. Projected Units is shown as "Plan – % of Goal Covered", a check on whether the activity plan adds up to the goal.
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
| Season Start (Monday) | Date | Week 1 starts here |
| Weeks | Number | Default 20. Used for pace (goal × week ÷ weeks) |
| Sales Days Goal | Number | The workbook had this per rep. It's now one target per season. If you want it per rep again, it can move to the Reps list |
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

**Pre-season inputs** (the yellow cells):

| Column | Workbook row |
|---|---|
| Season, Program | row 4–5 |
| Sales Goal Units | row 6 |
| Prior Year Units | row 7 (same season last year) |
| Prior Year Groups | new: number of groups last year |
| Retention % | row 8 |
| Direct Calls Goal | row 10 |
| Direct Close % | row 11 |
| Indirect Contacts Goal | row 12 |
| Indirect Close % | row 13 |
| Avg Units per New Group | row 14 |

**Calculated:**

| Column | Formula | Workbook row |
|---|---|---|
| Plan – Retained Units | Prior × Retention % | 9 |
| Plan – Direct New Groups | Direct Calls Goal × Direct Close % | 15 |
| Plan – Indirect New Groups | Indirect Contacts Goal × Indirect Close % | 16 |
| Plan – New Groups | Direct + Indirect new groups | 17 |
| Plan – New Units | New Groups × Avg Units per New Group | 18 |
| Plan – Projected Total Units | Retained + New Units | 19 |
| Plan – % of Goal Covered | Projected ÷ Sales Goal Units | 20 |

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

## Weekly Check-ins (one row per rep × week)

| Column | Notes |
|---|---|
| Season | Lookup to Seasons |
| Week Ending (Friday) | |
| Direct Calls | In-person direct sales calls this week |
| Indirect Contacts | Indirect contacts this week |
| Sales Days | Days this week with at least one sales call (0–5) |
| New Groups Booked – Direct / Indirect | Optional, but makes the in-season close rate visible |
| MFP Units Season-to-Date | Cumulative number from the MFP dashboard (same as the old "Weekly Sales Results" yellow column) |
| Notes | Wins, blockers |

**In-season scorecard math** (done in the app):

- Current week = weeks since Season Start + 1 (never more than Weeks)
- Pace for any goal = goal × current week ÷ Weeks (same straight-line pace as the workbook)
- Units to date = MFP Units Season-to-Date from the most recent check-in
- Calls / contacts / sales days = sums of the season's check-ins
- Direct calls goal = sum of Direct Calls Goal across the rep's program rows (same as workbook cell G10)
