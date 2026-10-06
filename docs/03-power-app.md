# 3. Build the Power App ("Rite Bite Sales Planner")

Reps could use the SharePoint lists directly, but a small app makes the Friday check-in about a one-minute job on a phone, and it shows each rep their own scorecard.

**Time:** roughly half a day for someone who has built a Power App before, longer for a first app (rough estimate).
**License:** "Power Apps for Microsoft 365" is included in M365 Business and Enterprise plans and covers apps that use SharePoint lists. Confirm against your own plan in the M365 admin center.

> **Honesty note:** the formulas below are written carefully but couldn't be tested inside your tenant. Power Apps underlines anything it doesn't accept in red, and the fix is usually a column display name that's slightly different. If something won't take, copy the red error message and send it over.

---

## Screens

| Screen | Who | What it does |
|---|---|---|
| **scrHome** – My Scorecard | Everyone | Season picker; units vs goal; direct calls, indirect contacts and sales days vs pace; missed check-ins |
| **scrCheckIn** – Friday Check-in | Everyone | One form for this week's numbers. Re-opening the same week edits it instead of duplicating it |
| **scrPlan** – My Plan | Everyone | Pre-season plan, one row per program, with projected units vs goal |
| **scrResults** – Season Results | Everyone | Post-season actuals per program |
| **scrTeam** – Team | Managers only | One row per rep: attainment, pace, last check-in |

## 0. Create the app and connect data

1. Go to **make.powerapps.com → + Create → Blank app → Blank canvas app**. Choose **Phone** format and name it *Rite Bite Sales Planner*.
2. **Data → Add data → SharePoint →** your Sales Planner site → tick **Seasons**, **Reps**, **Program Plans**, **Weekly Check-ins**.
3. **Settings → General → Data row limit**: set it to **2000**.

## 1. App.OnStart

Select **App** in the tree view and set **OnStart**:

```powerfx
// The two people who see the Team screen. SharePoint permissions are the real
// security: a rep who somehow opened the Team screen would still only see their own rows.
Set(varManagers, ["lynwood@ritebitefundraising.com", "SECOND.MANAGER@ritebitefundraising.com"]);
Set(varIsManager, Lower(User().Email) in varManagers);

Set(varSeason, Coalesce(
    First(Filter(Seasons, 'Current Season' = true)),
    First(Sort(Seasons, 'Season Start (Monday)', SortOrder.Descending))
));
```

## 2. scrHome – My Scorecard

**Hidden loader button.** Add a button named `btnLoad` with **Visible** = `false` and **OnSelect**:

```powerfx
ClearCollect(colMyPlans,
    Filter('Program Plans', Season.Id = varSeason.ID && 'Created By'.Email = User().Email));
ClearCollect(colMyCheckins,
    Sort(
        Filter('Weekly Check-ins', Season.Id = varSeason.ID && 'Created By'.Email = User().Email),
        'Week Ending (Friday)', SortOrder.Descending));

// Current week of the season (0 before it starts, capped at the last week)
Set(varWeekNow, Max(0, Min(varSeason.Weeks,
    RoundDown(DateDiff(varSeason.'Season Start (Monday)', Today(), TimeUnit.Days) / 7, 0) + 1)));

If(varIsManager,
    ClearCollect(colAllPlans,    Filter('Program Plans',    Season.Id = varSeason.ID));
    ClearCollect(colAllCheckins, Filter('Weekly Check-ins', Season.Id = varSeason.ID));
    ClearCollect(colReps,        Filter(Reps, Active = true))
);
```

**scrHome.OnVisible:** `Select(btnLoad)`

**Season dropdown** (`ddSeason`):
- Items: `Sort(Seasons, 'Season Start (Monday)', SortOrder.Descending)`
- Value (field shown): `Season`
- Default: `varSeason.Season`
- OnChange: `Set(varSeason, ddSeason.Selected); Select(btnLoad)`

**Scorecard tiles.** Add four tiles (a rectangle plus labels). The text formulas:

| Tile | Big number | Small line |
|---|---|---|
| Units | `Text(Coalesce(First(colMyCheckins).'MFP Units Season-to-Date', 0), "#,##0")` | `"of " & Text(Sum(colMyPlans, 'Sales Goal Units'), "#,##0") & " goal · " & Text(IfError(Coalesce(First(colMyCheckins).'MFP Units Season-to-Date', 0) / Sum(colMyPlans, 'Sales Goal Units'), 0), "0%")` |
| Direct calls | `Sum(colMyCheckins, 'Direct Calls')` | `"pace " & Round(Sum(colMyPlans, 'Direct Calls Goal') * varWeekNow / varSeason.Weeks, 0) & " · goal " & Sum(colMyPlans, 'Direct Calls Goal')` |
| Indirect contacts | `Sum(colMyCheckins, 'Indirect Contacts')` | `"pace " & Round(Sum(colMyPlans, 'Indirect Contacts Goal') * varWeekNow / varSeason.Weeks, 0) & " · goal " & Sum(colMyPlans, 'Indirect Contacts Goal')` |
| Sales days | `Sum(colMyCheckins, 'Sales Days')` | `"pace " & Round(varSeason.'Sales Days Goal' * varWeekNow / varSeason.Weeks, 0) & " · goal " & varSeason.'Sales Days Goal'` |

**Tile colour (on pace / close / behind).** Example for the Direct calls tile's rectangle **Fill**; repeat with the matching numbers for the others:

```powerfx
With({ actual: Sum(colMyCheckins, 'Direct Calls'),
       pace:   Sum(colMyPlans, 'Direct Calls Goal') * varWeekNow / varSeason.Weeks },
    If(pace = 0 || actual >= pace, RGBA(220, 242, 225, 1),     // green: on pace
       actual >= pace * 0.9,       RGBA(255, 243, 205, 1),     // amber: within 10%
                                   RGBA(248, 215, 218, 1)))    // red: behind
```

**Missed check-ins.** A small vertical gallery `galMissed` with **Items**:

```powerfx
Filter(
    ForAll(Sequence(Max(varWeekNow - 1, 0)) As w,
        { Due: DateAdd(varSeason.'Season Start (Monday)', (w.Value - 1) * 7 + 4, TimeUnit.Days) }
    ) As f,
    IsBlank(LookUp(colMyCheckins, DateDiff('Week Ending (Friday)', f.Due, TimeUnit.Days) = 0))
)
```

Label inside the gallery: `"Missing: week ending " & Text(ThisItem.Due, "mmm d")`. This lists every *completed* week with no check-in.

**Buttons:** "Friday Check-in" → `Navigate(scrCheckIn)`, "My Plan" → `Navigate(scrPlan)`, "Season Results" → `Navigate(scrResults)`, "Team" → `Navigate(scrTeam)` with **Visible** = `varIsManager`.

## 3. scrCheckIn – Friday Check-in

Controls: a date picker `dpWeekEnding`; text inputs (Format = Number) `txtDirect`, `txtIndirect`, `txtSalesDays`, `txtDirBook`, `txtIndBook`, `txtUnits`; and a multi-line text input `txtNotes`.

**dpWeekEnding.DefaultDate** (this Friday, or last Friday on a weekend):

```powerfx
DateAdd(Today(), Switch(Weekday(Today()), 7, -1, 1, -2, 6 - Weekday(Today())), TimeUnit.Days)
```

**scrCheckIn.OnVisible** and **dpWeekEnding.OnChange** (same formula): load that week's row if it already exists:

```powerfx
Set(varExisting, LookUp(colMyCheckins,
    DateDiff('Week Ending (Friday)', dpWeekEnding.SelectedDate, TimeUnit.Days) = 0))
```

**Default** of each input:

| Control | Default |
|---|---|
| txtDirect | `varExisting.'Direct Calls'` |
| txtIndirect | `varExisting.'Indirect Contacts'` |
| txtSalesDays | `varExisting.'Sales Days'` |
| txtDirBook | `varExisting.'New Groups Booked - Direct'` |
| txtIndBook | `varExisting.'New Groups Booked - Indirect'` |
| txtUnits | `varExisting.'MFP Units Season-to-Date'` |
| txtNotes | `varExisting.Notes` |

Add hint text to txtUnits: *"Season-to-date units from the MFP dashboard."*

**Save button OnSelect:**

```powerfx
If(
    Weekday(dpWeekEnding.SelectedDate) <> 6,
        Notify("Week Ending must be a Friday.", NotificationType.Error),
    IsBlank(txtDirect.Text) || IsBlank(txtIndirect.Text) || IsBlank(txtSalesDays.Text),
        Notify("Direct calls, indirect contacts and sales days are required (0 is fine).", NotificationType.Error),
    IfError(
        Patch('Weekly Check-ins',
            If(IsBlank(varExisting), Defaults('Weekly Check-ins'), varExisting),
            {
                Season: { Id: varSeason.ID, Value: varSeason.Season },
                'Week Ending (Friday)': dpWeekEnding.SelectedDate,
                'Direct Calls': Value(txtDirect.Text),
                'Indirect Contacts': Value(txtIndirect.Text),
                'Sales Days': Value(txtSalesDays.Text),
                'New Groups Booked - Direct': Value(txtDirBook.Text),
                'New Groups Booked - Indirect': Value(txtIndBook.Text),
                'MFP Units Season-to-Date': Value(txtUnits.Text),
                Notes: txtNotes.Text
            }),
        Notify("Couldn't save: " & FirstError.Message, NotificationType.Error),
        Notify("Check-in saved. Thanks!", NotificationType.Success); Navigate(scrHome)
    )
)
```

## 4. scrPlan – My Plan

1. **Gallery** `galPlans`, Items `colMyPlans`. Show in each row:
   - `ThisItem.Program.Value`
   - `"Goal " & ThisItem.'Sales Goal Units' & " · Projected " & Round(ThisItem.'Plan - Projected Total Units', 0) & " (" & Text(ThisItem.'Plan - % of Goal Covered', "0%") & " of goal)"`
2. **Edit form** `frmPlan`: DataSource `'Program Plans'`, Item `galPlans.Selected`. Fields: Season, Program, Sales Goal Units, Prior Year Units, Prior Year Groups, Retention %, Direct Calls Goal, Direct Close %, Indirect Contacts Goal, Indirect Close %, Avg Units per New Group.
3. **Season card:** set the card's **Update** to `{ Id: varSeason.ID, Value: varSeason.Season }` and **Visible** to `false`. The rep never picks a season; it's always the one on the scorecard.
4. **Percent cards (Retention %, Direct Close %, Indirect Close %).** SharePoint stores 85% as 0.85. So reps can type 85:
   - The text input's **Default**: `Parent.Default * 100`
   - The card's **Update**: `Value(<that text input>.Text) / 100`
5. **"Add program" button:** `NewForm(frmPlan)`
6. **Save button:** this blocks a second row for the same program and season:

   ```powerfx
   If(frmPlan.Mode = FormMode.New &&
      !IsBlank(LookUp(colMyPlans, Program.Value = <Program card's dropdown>.Selected.Value)),
       Notify("You already have a plan for that program this season. Select it to edit.", NotificationType.Warning),
       SubmitForm(frmPlan))
   ```

   Replace `<Program card's dropdown>` with the control name Power Apps gave it (for example `DataCardValue3`).
7. **frmPlan.OnSuccess:** `Refresh('Program Plans'); ClearCollect(colMyPlans, Filter('Program Plans', Season.Id = varSeason.ID && 'Created By'.Email = User().Email)); Notify("Plan saved", NotificationType.Success)`
8. Header totals: `"Season goal " & Sum(colMyPlans, 'Sales Goal Units') & " · Projected " & Round(Sum(colMyPlans, 'Plan - Projected Total Units'), 0)`

## 5. scrResults – Season Results

Copy scrPlan (right-click → Duplicate screen) and change the form fields to the **Actual –** input columns: Total Units, Retained Units (ran last year), Retained Groups (ran last year), Direct Calls, Direct Bookings, Indirect Contacts, Indirect Bookings. Remove the "Add program" button; results go on the existing plan rows.

Gallery row text:

```powerfx
ThisItem.Program.Value & ": " & Text(ThisItem.'Actual - Attainment %', "0%") & " of goal · direct close " &
Text(ThisItem.'Actual - Direct Close %', "0%") & " (plan " & Text(ThisItem.'Direct Close %', "0%") & ")" &
" · groups back " & Text(ThisItem.'Actual - Group Retention %', "0%")
```

## 6. scrTeam – Team (managers)

**Gallery** `galTeam`, **Items**:

```powerfx
Sort(
    ForAll(colReps As r,
        With({
            p: Filter(colAllPlans, Lower('Created By'.Email) = Lower(r.Rep.Email)),
            c: Sort(Filter(colAllCheckins, Lower('Created By'.Email) = Lower(r.Rep.Email)),
                    'Week Ending (Friday)', SortOrder.Descending)
        },
        {
            RepName:      r.'Rep Name',
            Code:         r.'MFP Owning User Code',
            Goal:         Sum(p, 'Sales Goal Units'),
            Units:        Coalesce(First(c).'MFP Units Season-to-Date', 0),
            DirectCalls:  Sum(c, 'Direct Calls'),
            DirectGoal:   Sum(p, 'Direct Calls Goal'),
            Indirect:     Sum(c, 'Indirect Contacts'),
            IndirectGoal: Sum(p, 'Indirect Contacts Goal'),
            SalesDays:    Sum(c, 'Sales Days'),
            CheckIns:     CountRows(c),
            LastCheckIn:  First(c).'Week Ending (Friday)',
            HasPlan:      CountRows(p) > 0
        })
    ),
    IfError(Units / Goal, 0), SortOrder.Descending
)
```

Labels in each row:

- `ThisItem.RepName & " (" & ThisItem.Code & ")"`
- `Text(IfError(ThisItem.Units / ThisItem.Goal, 0), "0%") & " of " & ThisItem.Goal & " units"`
- `"Direct " & ThisItem.DirectCalls & " / pace " & Round(ThisItem.DirectGoal * varWeekNow / varSeason.Weeks, 0)`
- `"Indirect " & ThisItem.Indirect & " / pace " & Round(ThisItem.IndirectGoal * varWeekNow / varSeason.Weeks, 0)`
- `"Check-ins " & ThisItem.CheckIns & " of " & Max(varWeekNow - 1, 0) & " · last " & If(IsBlank(ThisItem.LastCheckIn), "never", Text(ThisItem.LastCheckIn, "mmm d"))`
- A red "No plan yet" label with **Visible** `!ThisItem.HasPlan`

Team totals across the top: `Sum(galTeam.AllItems, Units)`, `Sum(galTeam.AllItems, Goal)`, and so on.

## 7. Publish and share

1. **File → Save → Publish.**
2. **Share** the app with the 6 reps and the other manager (as **User**, not Co-owner). Power Apps shares to people or Entra security groups; it can't use the SharePoint groups.
3. Reps install **Power Apps** from the App Store / Google Play, sign in with their work account, and pin the app.

## Optional later

- **Plan approval:** add an "Approved" Yes/No column that only managers set, and lock the plan form when it's ticked.
- **Power BI dashboard:** if your plan includes Power BI Pro (E5 does; Business Standard and Business Premium don't, as far as I know), connect Power BI Desktop to the two lists for history charts across seasons.
