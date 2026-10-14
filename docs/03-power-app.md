# 3. Build the Power App ("Rite Bite Sales Planner")

Reps could use the SharePoint lists directly, but a small phone app makes logging a selling day about a 20-second job. It also shows each rep how much activity their goal takes and how far along they are.

**Time:** roughly half a day for someone who has built a Power App before, longer for a first app (rough estimate).
**License:** "Power Apps for Microsoft 365" is included in M365 Business and Enterprise plans and covers apps that use SharePoint lists. Confirm against your own plan in the M365 admin center.

> **Honesty note:** the formulas below are written carefully but couldn't be tested inside your tenant. Power Apps underlines anything it doesn't accept in red, and the fix is usually a column display name that's slightly different. If something won't take, copy the red error message and send it over.

**One kind of activity: Sales Calls** (Lynwood, October 2026). The plan and the log used to split in-person calls from gatekeeper contacts; they're now combined into **Sales Calls**, with one target and one close rate. The old gatekeeper columns are still in the lists but unused: the app saves them as 0, and plans put 100% of new groups on sales calls. The app's variable names (`varDirectTarget`, `txtDirect` and so on) still say "direct"; they're only names.

---

## Screens

| Screen | Who | What it does |
|---|---|---|
| **scrHome** – My Scorecard | Everyone | Season picker; units vs goal; sales calls and sales days vs target; new groups booked vs needed; close rate over the last 12 months |
| **scrLog** – Log a Day | Everyone | One quick form per selling day. Re-opening the same date edits that day instead of duplicating it |
| **scrPlan** – My Plan | Everyone | One plan per season (all programs): goal, retention and conversion rates. Shows the sales calls needed |
| **scrResults** – Season Results | Everyone | Post-season actuals (optional; can be entered in SharePoint instead) |
| **scrTeam** – Team | Managers only | One row per rep: units, targets, progress, last activity |

## 0. Create the app and connect data

1. Go to **make.powerapps.com → + Create → Blank app → Blank canvas app**. Choose **Phone** format and name it *Rite Bite Sales Planner*.
2. **Data → Add data → SharePoint →** your Sales Planner site → tick **Seasons**, **Reps**, **Program Plans**, **Daily Activity**.
3. **Settings → General → Data row limit**: set it to **2000**.

## 1. App.OnStart

Select **App** in the tree view and set **OnStart**:

```powerfx
// The people who see the Team screen. SharePoint permissions are the real
// security: a rep who somehow opened the Team screen would still only see their own rows.
Set(varManagers, ["lynwood@ritebitefundraising.com"]);    // add the second manager's email later
Set(varIsManager, Lower(User().Email) in varManagers);

Set(varSeason, Coalesce(
    First(Filter(Seasons, 'Current Season' = true)),
    First(Sort(Seasons, 'Season Start', SortOrder.Descending))
));
```

## 2. scrHome – My Scorecard

**Hidden loader button.** Add a button named `btnLoad` with **Visible** = `false` and **OnSelect**:

```powerfx
ClearCollect(colMyPlans,
    Filter('Program Plans', Season.Id = varSeason.ID && 'Created By'.Email = User().Email));
ClearCollect(colMyDays,
    Sort(
        Filter('Daily Activity', Season.Id = varSeason.ID && 'Created By'.Email = User().Email),
        'Activity Date', SortOrder.Descending));

// Last 12 months of activity, across seasons, for realistic close rates
// (a spring call can book a fall group)
// Fetch the rep's rows, then filter dates inside the app (a date filter sent to
// SharePoint returned nothing on the live site, October 2026)
ClearCollect(colMyAll, Filter('Daily Activity', 'Created By'.Email = User().Email));
ClearCollect(colMyYear, Filter(colMyAll, 'Activity Date' >= DateAdd(Today(), -365, TimeUnit.Days)));
Set(varDirClose12, IfError(Sum(colMyYear, 'New Groups') / Sum(colMyYear, 'Sales Calls'), 0));

// Totals used by the tiles
Set(varGoal,          Sum(colMyPlans, 'Sales Goal Units'));
Set(varDirectTarget,  Sum(colMyPlans, 'Sales Calls Target'));
Set(varGroupsNeeded,  Sum(colMyPlans, 'Plan - New Groups Needed'));
Set(varDirectDone,    Sum(colMyDays, 'Sales Calls') + 0);        // + 0 turns an empty season's blank into 0
Set(varBooked,        Sum(colMyDays, 'New Groups'));
Set(varSalesDays,     Sum(colMyDays, 'Sales Day') + 0);
Set(varUnits,         Coalesce(First(Filter(colMyDays, !IsBlank('MFP Units Season-to-Date'))).'MFP Units Season-to-Date', 0));

// How far through the season we are (reference only; selling comes in bursts, so there's no weekly pace)
// IfError: a season with no Weeks would otherwise divide by 0 and stop the screen loading
Set(varElapsed, IfError(Max(0, Min(1,
    DateDiff(varSeason.'Season Start', Today(), TimeUnit.Days) / (varSeason.Weeks * 7))), 0));

// Selling days left in the plan (never below 1, so "per day" never divides by 0)
Set(varDaysLeft, Max(1, Coalesce(varSeason.'Sales Days Goal', 0) - varSalesDays));

If(varIsManager,
    ClearCollect(colAllPlans, Filter('Program Plans',  Season.Id = varSeason.ID));
    ClearCollect(colAllDays,  Filter('Daily Activity', Season.Id = varSeason.ID));
    ClearCollect(colAllRows,  'Daily Activity');
    ClearCollect(colAllYear,  Filter(colAllRows, 'Activity Date' >= DateAdd(Today(), -365, TimeUnit.Days)));
    ClearCollect(colReps,     Filter(Reps, Active = true));
    ClearCollect(colAllBase,  Filter('Rep Baselines', Season.Id = varSeason.ID))   // managers can see every rep's row
);
// This rep's starting numbers from MFP for the season (My Plan pre-fills from it)
Set(varBase, LookUp('Rep Baselines', Season.Id = varSeason.ID && Lower(Rep.Email) = Lower(User().Email)));

// Units and new groups come from the weekly MFP pull (Rep Baselines), not from what reps type.
// These replace the earlier varUnits / varBooked / varDirClose12 values above.
Set(varUnits,  varBase.'MFP Units to Date' + 0);
Set(varBooked, varBase.'MFP New Groups' + 0);
// Close rate = new groups in this season + last season (MFP) / sales calls logged in the last 12 months.
// Calls are only logged from go-live, so for the first year this reads high; under 20 calls it shows as "-".
Set(varCalls12, Sum(colMyYear, 'Sales Calls') + 0);
Set(varDirClose12, IfError((varBase.'MFP New Groups Last 2 Seasons' + 0) / varCalls12, 0))
```

**In the editor,** variables keep their last value until the formula runs again. **Run OnStart** (⋯ next to App) reloads the season but not btnLoad; btnLoad runs when Home opens, so Play, go to another screen and come back.

**scrHome.OnVisible:** look up the season first, then load. On a phone the published app can show Home before App.OnStart has finished, and btnLoad then filters by an empty season (blank targets, "division by zero"); found on the live build, October 13, 2026. Keep the manager emails the same as in App.OnStart.

```powerfx
If(IsBlank(varSeason),
    Set(varManagers, ["lynwood@ritebitefundraising.com"]);
    Set(varIsManager, Lower(User().Email) in varManagers);
    Set(varSeason, Coalesce(First(Filter(Seasons, 'Current Season' = true)), First(Sort(Seasons, 'Season Start', SortOrder.Descending))))
);
Select(btnLoad)
```

**Season dropdown** (`ddSeason`):
- Items: `Sort(Seasons, 'Season Start', SortOrder.Descending)`
- Value (field shown): `Season`
- Default: `varSeason.Season`
- OnChange: `Set(varSeason, ddSeason.Selected); Select(btnLoad)`

> Power Apps' `Text()` does **not** turn `"0%"` into a percentage the way Excel does (it rounds the plain number), so every percentage below multiplies by 100 first. This was found on the live build in October 2026.

**Header line** (Height about 60, two lines): how much of the season's delivery window is left, and what's done so far:

```powerfx
varSeason.Season & " · " &
If(Today() < varSeason.'Season Start',
    "starts " & Text(varSeason.'Season Start', "mmm d"),
    Text((1 - varElapsed) * 100, "0") & "% of season left") & Char(10) &
"Done so far: " & Text(IfError(varUnits / varGoal, 0) * 100, "0") & "% of unit goal · " &
varBooked & " of " & RoundUp(varGroupsNeeded, 0) & " new groups"
```

The season is its delivery window (Spring: Season Start Jan 1, **Weeks** 26; Fall: Jul 1, 26). Selling goes on all year, so a sales call can be logged on any date and counts toward the season set as **Current Season**; switch it when you rebuild for the next season (June for Fall).

**Tiles.** Add five tiles (a rectangle plus labels). The text formulas:

| Tile | Big number | Small line |
|---|---|---|
| Units | `Text(varUnits, "#,##0")` | `"of " & Text(varGoal, "#,##0") & " goal · " & Text((IfError(varUnits / varGoal, 0)) * 100, "0") & "%"` |
| Sales calls | `varDirectDone & " / " & varDirectTarget` | `Max(0, varDirectTarget - varDirectDone) & " to go · about " & RoundUp(Max(0, varDirectTarget - varDirectDone) / Max(1, varDaysLeft), 0) & " per selling day"` |
| Sales days | `varSalesDays & " / " & Coalesce(varSeason.'Sales Days Goal', 0)` | `"selling days logged"` |
| New groups | `varBooked & " / " & RoundUp(varGroupsNeeded, 0)` | `"booked of needed this season"` |
| Close rate (12 months) | `Text(varDirClose12 * 100, "0") & "%"` | `"plan " & Text(Value(First(colMyPlans).'Sales Call Close %') * 100, "0") & "%"` |

On the live build each tile is one label with `Char(10)` line breaks, for example the close-rate tile:

```powerfx
"CLOSE RATE (LAST 12 MONTHS)" & Char(10) &
If(varCalls12 < 20, "- (needs 20+ calls logged)", Text(varDirClose12 * 100, "0") & "%") &
" · plan " & Text(Value(First(colMyPlans).'Sales Call Close %') * 100, "0") & "%"
```

The units tile adds the MFP date on a third line: `... & Char(10) & "MFP as of " & If(IsBlank(varBase.'MFP As Of'), "not pulled yet", Text(varBase.'MFP As Of', "mmm d"))`. Units and new groups come from the weekly MFP pull (Rep Baselines), so they move on Mondays, not when a rep logs a day.

**Progress bars (optional, nice on a phone).** Under each activity tile, add a grey rectangle the full width, and on top of it a coloured rectangle with **Width**:

```powerfx
Parent.Width * Min(1, IfError(varDirectDone / varDirectTarget, 0))      // use the matching numbers for each tile
```

There's deliberately **no red/amber "behind pace" colour**. Selling comes in bursts, so being at 20% of target halfway through the season can be fine. Compare the progress bar with the "% of the season gone" in the header, and look at the **New groups** and **Close rate** tiles. If the 12-month close rate is below plan, the targets are too low and more calls will be needed. Close rates use a full year because a spring call can book a fall group, so one season alone is misleading.

**Button layout** (X 20, Width 600): btnGoLog Y 700, Height 70; btnGoPlan Y `btnGoLog.Y + btnGoLog.Height + 15`; btnGoTeam Y `btnGoPlan.Y + btnGoPlan.Height + 15`; **btnExit** Y `btnGoTeam.Y + btnGoTeam.Height + 40`, Height 55, Text `"Exit"`, OnSelect `Exit()` (closes the app without signing out; the iPhone player has no visible close button), Fill `Color.LightGray`, Color `Color.Black`.

**Buttons:** "Log a Day" → `Navigate(scrLog)`, "My Plan" → `Navigate(scrPlan)`, "Season Results" → `Navigate(scrResults)`, "Team" → `Navigate(scrTeam)` with **Visible** = `varIsManager`.

**Recent days (optional):** a small gallery with Items `FirstN(colMyDays, 5)`, showing `Text(ThisItem.'Activity Date', "ddd mmm d") & ": " & ThisItem.'Sales Calls' & " sales calls"`. (Display only. To edit an earlier day, the rep opens Log a Day and picks that date.)

## 3. scrLog – Log a Day

Controls: a date picker `dpDate`; a text input (Format = Number) `txtDirect` (sales calls); a read-only label `lblMFPNumbers`; and a multi-line text input `txtNotes`. Reps only type sales calls and notes. New groups and units come from the weekly MFP pull.

**Layout** (X 20, Width `Parent.Width - 40` on each): title label Y 5, Height 50, Size 20, Bold, VerticalAlign Middle; dpDate Y 60; txtDirect Y `dpDate.Y + dpDate.Height + 15`; lblMFPNumbers Y `txtDirect.Y + txtDirect.Height + 15`, Height 100, Fill light grey; txtNotes Y `lblMFPNumbers.Y + lblMFPNumbers.Height + 15`, Height 220; btnSave Y `txtNotes.Y + txtNotes.Height + 20`; btnBack Y `btnSave.Y + btnSave.Height + 15`.

**lblMFPNumbers.Text:**

```powerfx
"From MFP (updated weekly)" & Char(10) &
"New groups booked this season: " & (varBase.'MFP New Groups' + 0) & Char(10) &
"Season-to-date units: " & Text(varBase.'MFP Units to Date' + 0, "#,##0") & " · as of " &
If(IsBlank(varBase.'MFP As Of'), "not pulled yet", Text(varBase.'MFP As Of', "mmm d"))
```

**dpDate.DefaultDate:** `Today()`

**scrLog.OnVisible** and **dpDate.OnChange** (same formula): load that day's row if it already exists:

```powerfx
Set(varExisting, LookUp(colMyDays,
    DateDiff('Activity Date', dpDate.SelectedDate, TimeUnit.Days) = 0))
```

**Default** of each input:

| Control | Default | Hint text |
|---|---|---|
| txtDirect | `varExisting.'Sales Calls'` | Sales calls today |
| txtNotes | `varExisting.Notes` | Notes |

**Save button OnSelect:**

```powerfx
If(
    dpDate.SelectedDate > Today(),
        Notify("You can't log a day in the future.", NotificationType.Error),
    IsBlank(txtDirect.Text),
        Notify("Enter your sales calls (0 is fine).", NotificationType.Error),
    IfError(
        Patch('Daily Activity',
            If(IsBlank(varExisting), Defaults('Daily Activity'), varExisting),
            {
                Season: { Id: varSeason.ID, Value: varSeason.Season },
                'Activity Date': dpDate.SelectedDate,
                'Sales Calls': Value(txtDirect.Text),
                'Gatekeeper Contacts': 0,             // unused; 0 keeps the Sales Day formula working
                'New Groups Booked - Gatekeeper': 0,
                Notes: txtNotes.Text
            }),
        Notify("Couldn't save: " & FirstError.Message, NotificationType.Error),
        Notify("Day logged. Nice work!", NotificationType.Success);
        Navigate(scrHome)
    )
)
```

## 4. scrPlan – My Plan

**One plan per rep per season, for all programs combined** (Lynwood, October 2026). Butter Braid is about 85% of sales, and calls aren't tied to a program, so a per-program plan added data entry without telling reps anything new. The row's Program is saved as **All Programs**. Per-program results still come from the yearly MFP pull.

1. **Edit form** `frmPlan`: DataSource `'Program Plans'`, 1 column, **X** 0, **Width** 640. Put it just under the title (Y about 60) and stretch it down to the Save button.
   - **Item:** `First(colMyPlans)`
   - **DefaultMode:** `If(IsEmpty(colMyPlans), FormMode.New, FormMode.Edit)`
   - Fields, in this order: Season, Program (both hidden, below), Prior Year Units, Prior Year Groups, **Unit Goal**, Growth % (if no Unit Goal), Unit Retention %, Group Retention %, Avg Units per Group, **Sales Call Close %**, plus two hidden cards (below). Reorder with **frmPlan → Edit fields** (drag, or **⋯ → Move up**).
2. **Season card:** **Update** `{ Id: varSeason.ID, Value: varSeason.Season }`, **Visible** `false`. The rep never picks a season; it's always the one on the scorecard.
3. **Program card:** **Update** `{Value: "All Programs"}`, **Visible** `false`. The Program column needs **All Programs** among its choices; the setup script adds it.
   - **% of New Groups from In-Person** card: **Update** `1`, **Visible** `false`. Every new group comes from sales calls.
   - **Gatekeeper Close %** card: **Visible** `false`. Unused.
4. **Percent cards** (Growth %, Unit Retention %, Group Retention %, Sales Call Close %). SharePoint stores 50% as 0.5, so that reps can type 50:
   - The text input's **Default**: `If(IsBlank(Parent.Default), "", Parent.Default * 100)`. With plain `Parent.Default * 100`, a new plan starts at 0 instead of blank, and a 0 close rate makes the targets 0.
   - The card's **Update**: `Value(<that text input>.Text) / 100`
4a. **Pre-fill from MFP** (Rep Baselines list; add it as a data source). In **btnLoad.OnSelect** add:

   ```powerfx
   Set(varBase, LookUp('Rep Baselines', Season.Id = varSeason.ID && Lower(Rep.Email) = Lower(User().Email)));
   ```

   Then set the **Default** of these text inputs. A new plan fills in automatically; on an existing plan the rep taps **Fill in from MFP**:

   | Card | Text input Default |
   |---|---|
   | Prior Year Units | `If((frmPlan.Mode = FormMode.New \|\| varUseBase) && !IsBlank(varBase), varBase.'Prior Year Units', Parent.Default)` |
   | Prior Year Groups | same, with `varBase.'Prior Year Groups'` |
   | Avg Units per Group | same, with `varBase.'Avg Units per Group'` |
   | Unit Retention % | `If((frmPlan.Mode = FormMode.New \|\| varUseBase) && !IsBlank(varBase), Round(varBase.'Unit Retention %' * 100, 1), If(IsBlank(Parent.Default), "", Parent.Default * 100))` |
   | Group Retention % | same, with `varBase.'Group Retention %'` |

   - **scrPlan.OnVisible:** `Set(varUseBase, false); ResetForm(frmPlan)`
   - Button **btnFillMFP**: Text `"Fill in from MFP"`, **Visible** `!IsBlank(varBase)`, **OnSelect** `Set(varUseBase, true)`. The numbers appear in the boxes; nothing is saved until **Save plan**. Layout: **X** `btnSavePlan.X`, **Width** `btnSavePlan.Width`, **Height** `btnSavePlan.Height`, **Size** `btnSavePlan.Size`, **Y** `btnSavePlan.Y - btnSavePlan.Height - 10`; and **frmPlan.Height** `If(btnFillMFP.Visible, btnFillMFP.Y, btnSavePlan.Y) - frmPlan.Y - 10`.
   - Add `; Set(varUseBase, false)` to the end of **frmPlan.OnSuccess**.
   - New form cards are locked: select the card, **Advanced → Unlock to change properties**.
   - **Checked live (October 12, 2026), 2027 Spring:** the form opened with KJS's MFP numbers (16,369 units, 77 groups, 58% unit and 57.6% group retention, 212.6 per group). Unit Goal 18,000 at 9% → 41 new groups and 490 sales calls on Home.
   - Optional label under the title: `If(IsBlank(varBase), "", varBase.'Retained Groups' & " of " & varBase.'Base Season Groups' & " " & varBase.'Retention Measured From' & " groups came back last year")`

5. **Live preview under the form** (optional), so the rep sees the calls needed before saving. Add a label with **Text**:

   ```powerfx
   With({
       prior:  Value(<Prior Year Units input>.Text),
       growth: Value(<Growth % input>.Text) / 100,
       over:   Value(<Unit Goal input>.Text),
       ret:    Value(<Unit Retention % input>.Text) / 100,
       avg:    Value(<Avg Units per Group input>.Text),
       close:  Value(<Sales Call Close % input>.Text) / 100
   },
   With({ goal: If(over > 0, over, Round(prior * (1 + growth), 0)) },
   With({ groups: IfError(Max(0, goal - Round(prior * ret, 0)) / avg, 0) },
       "Goal " & goal & " units → " & RoundUp(groups, 0) & " new groups → " &
       RoundUp(IfError(groups / close, 0) * 1.1, 0) & " sales calls (incl. 10% cushion)")))
   ```

   Replace each `<… input>` with the control name Power Apps gave that field's text box (for example `DataCardValue5`).
6. **Save button** `btnSavePlan`: **Text** `"Save plan"`, **OnSelect** `SubmitForm(frmPlan)`
7. **frmPlan.OnSuccess:** `ClearCollect(colMyPlans, Filter('Program Plans', Season.Id = varSeason.ID && 'Created By'.Email = User().Email)); Notify("Plan saved", NotificationType.Success)`
8. **scrPlan.OnVisible:** `Set(varUseBase, false); ResetForm(frmPlan); Set(varPlanDirty, false); Set(varLeaveWarned, false)`, so the form opens on the rep's saved plan, or a blank one if they haven't made one yet.
9. **Unsaved-changes warning on Back.** Each visible box's text input (the DataCardValue inside the card, not the card) gets **OnChange** `Set(varPlanDirty, true)`. Back button **OnSelect**:

   ```powerfx
   If((varPlanDirty || varUseBase || frmPlan.Mode = FormMode.New) && !varLeaveWarned,
       Set(varLeaveWarned, true);
       Notify("Your plan isn't saved. Tap Save plan, or tap Back again to leave without saving.", NotificationType.Warning),
       ResetForm(frmPlan);
       Set(varUseBase, false);
       Set(varLeaveWarned, false);
       Navigate(scrHome);
       Set(varPlanDirty, false)
   )
   ```

   Add `; Set(varPlanDirty, false); Set(varLeaveWarned, false)` to **frmPlan.OnSuccess**. Two lessons from the live build (October 2026): `frmPlan.Unsaved` reported changes when there were none (likely the hidden cards and the ×100 percent boxes), and the form must be reset on the way **out**; resetting on the way in changes the boxes, fires OnChange and gives a false warning.

The yellow delegation warning on the form (about `Season.Id`) is harmless here: the app reads up to 500 rows and filters them on the phone, and there are about 12 plan rows a year.

**Checked live (October 8, 2026):** prior 20,000, Unit Goal 25,000, retention 80%, 250 per new group, Sales Call Close 9% → Home showed goal 25,000, 36 new groups and a target of 440 sales calls (36 ÷ 9% = 400, plus 10%).

**Setting the close rate:** it's one blended rate for all sales calls. For example, if 60% of groups came from in-person calls closing at 20% and 40% from gatekeeper contacts closing at 5%, the blend is 1 ÷ (0.6 ÷ 0.20 + 0.4 ÷ 0.05) = 1 ÷ 11 ≈ 9%. The Home screen's 12-month close rate is the rep's real number to compare with.

## 5. scrResults – Season Results

**Optional; skipped for now.** Actuals come from the yearly MFP pull and can be entered straight into the Program Plans list (Plan vs Actual view). If you build it later: copy scrPlan (right-click → Duplicate screen), change the form fields to the **Actual –** input columns (Total Units, Total Groups, Retained Units (ran last year), Retained Groups (ran last year)) and remove the live preview.

If you want a gallery of past seasons on this screen, its row text:


```powerfx
ThisItem.Season.Value & ": " & Text((ThisItem.'Actual - Attainment %') * 100, "0") & "%" & " of goal · retention " &
Text((ThisItem.'Actual - Unit Retention %') * 100, "0") & "%" & " (plan " & Text((ThisItem.'Unit Retention %') * 100, "0") & "%" & ")" &
" · " & ThisItem.'Actual - New Groups' & " new groups (plan " & RoundUp(ThisItem.'Plan - New Groups Needed', 0) & ")"
```

Add a line for the close rate over the last 12 months:

```powerfx
"Close rate, last 12 months: " & Text(varDirClose12 * 100, "0") & "%"
```

## 6. scrTeam – Team (managers)

Home's **Team** button: `Navigate(scrTeam)`, **Visible** `varIsManager`. Everything here comes from the manager collections btnLoad fills (colAllPlans, colAllDays, colAllYear, colReps).

1. **lblTeamTitle** (X 20, Y 10, W 600, Size 18): `"Team · " & varSeason.Season`
2. **lblTeamTotals** (X 20, Y 55, W 600, H 60):

   ```powerfx
   "Units " & Text(Sum(galTeam.AllItems, Units), "#,##0") & " of " & Text(Sum(galTeam.AllItems, Goal), "#,##0") & Char(10) &
   "Sales calls " & Sum(galTeam.AllItems, CallsDone) & " of " & Sum(galTeam.AllItems, CallsTarget)
   ```

3. **galTeam**: Insert → **Blank vertical gallery** (if you use a gallery with a layout, delete its Image, Title, Subtitle and NextArrow). X 20, Y 125, W 600, H 850, **TemplateSize** 190. **Items**:

   ```powerfx
   Sort(
       ForAll(colReps As r,
           With({
               p: Filter(colAllPlans, Lower('Created By'.Email) = Lower(r.Rep.Email)),
               d: Sort(Filter(colAllDays, Lower('Created By'.Email) = Lower(r.Rep.Email)), 'Activity Date', SortOrder.Descending),
               y: Filter(colAllYear, Lower('Created By'.Email) = Lower(r.Rep.Email)),
               b: LookUp(colAllBase, Lower(Rep.Email) = Lower(r.Rep.Email))
           },
           {
               RepName:     r.'Rep Name',
               Code:        r.'MFP Owning User Code',
               Goal:        Sum(p, 'Sales Goal Units') + 0,
               Units:       b.'MFP Units to Date' + 0,
               CallsDone:   Sum(d, 'Sales Calls') + 0,
               CallsTarget: Sum(p, 'Sales Calls Target') + 0,
               Booked:      b.'MFP New Groups' + 0,
               Needed:      RoundUp(Sum(p, 'Plan - New Groups Needed') + 0, 0),
               SalesDays:   Sum(d, 'Sales Day') + 0,
               LastDay:     First(d).'Activity Date',
               Calls12:     Sum(y, 'Sales Calls') + 0,
               Close12:     IfError((b.'MFP New Groups Last 2 Seasons' + 0) / Sum(y, 'Sales Calls'), 0),
               PlanClose:   First(p).'Sales Call Close %',
               HasPlan:     CountRows(p) > 0
           })
       ),
       IfError(Units / Goal, 0), SortOrder.Descending
   )
   ```

4. In the gallery row: **lblRepRow** (X 10, Y 5, W 560, H 175, Size 13):

   ```powerfx
   ThisItem.RepName & " (" & ThisItem.Code & ")" & Char(10) &
   "Units " & Text(ThisItem.Units, "#,##0") & " of " & Text(ThisItem.Goal, "#,##0") & " (" & Text(IfError(ThisItem.Units / ThisItem.Goal, 0) * 100, "0") & "%)" & Char(10) &
   "Sales calls " & ThisItem.CallsDone & " of " & ThisItem.CallsTarget & Char(10) &
   "Groups " & ThisItem.Booked & " of " & ThisItem.Needed & " · " & ThisItem.SalesDays & " selling days · last " & If(IsBlank(ThisItem.LastDay), "never", Text(ThisItem.LastDay, "mmm d")) & Char(10) &
   "Close (12 mo) " & If(ThisItem.Calls12 < 20, "-", Text(ThisItem.Close12 * 100, "0") & "%") & " · plan " & Text(Value(ThisItem.PlanClose) * 100, "0") & "%"
   ```

   and **lblNoPlan** (X 420, Y 5, W 150): Text `"No plan yet"`, Color `Color.Red`, FontWeight `FontWeight.Bold`, **Visible** `!ThisItem.HasPlan`.
5. **btnTeamBack** (X 20, Y 985, W 600, H 60): `Navigate(scrHome)`

A rep shows up once they're in the **Reps** list with **Active** ticked; their numbers come from rows they created themselves.

**Checked live (October 13, 2026), 2027 Spring:** one row, "Test – Lynwood as KJS", with 0 of 18,000 units, 0 of 490 sales calls, 0 of 41 groups and 17% close against a 9% plan; the totals line matched.

## 7. Publish and share

1. **File → Save → Publish.** Until you share it, only you can see it, which is good for testing.
2. **Share** the app (app → **Share**) with the reps and the other manager, as **User**, not Co-owner. **Untick "Send an email invitation"** if you don't want anyone notified yet. Power Apps shares to people or Entra security groups; it can't use the SharePoint groups.
3. Reps install **Power Apps** from the App Store / Google Play, sign in with their work account, and pin the app (or add it to their home screen).
4. Updates are automatic: republish, and everyone gets the new version the next time they open the app.

## Optional later

- **Plan approval:** add an "Approved" Yes/No column that only managers set, and lock the plan form when it's ticked.
- **Wide-screen manager dashboard:** a separate Tablet-format app with just the Team screen, for desktop use.
- **Power BI dashboard:** if your plan includes Power BI Pro (E5 does; Business Standard and Business Premium don't, as far as I know), connect Power BI Desktop to the lists for history charts across seasons.
