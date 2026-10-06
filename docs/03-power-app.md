# 3. Build the Power App ("Rite Bite Sales Planner")

Reps could use the SharePoint lists directly, but a small phone app makes logging a selling day about a 20-second job. It also shows each rep how much activity their goal takes and how far along they are.

**Time:** roughly half a day for someone who has built a Power App before, longer for a first app (rough estimate).
**License:** "Power Apps for Microsoft 365" is included in M365 Business and Enterprise plans and covers apps that use SharePoint lists. Confirm against your own plan in the M365 admin center.

> **Honesty note:** the formulas below are written carefully but couldn't be tested inside your tenant. Power Apps underlines anything it doesn't accept in red, and the fix is usually a column display name that's slightly different. If something won't take, copy the red error message and send it over.

Column names below use the labels **In-Person** (direct sales calls) and **Gatekeeper** (indirect contacts), the setup script's defaults. If you change them (`-DirectLabel` / `-IndirectLabel`), use your labels instead.

---

## Screens

| Screen | Who | What it does |
|---|---|---|
| **scrHome** – My Scorecard | Everyone | Season picker; units vs goal; in-person calls, gatekeeper contacts and sales days vs target; new groups booked vs needed; close rates over the last 12 months |
| **scrLog** – Log a Day | Everyone | One quick form per selling day. Re-opening the same date edits that day instead of duplicating it |
| **scrPlan** – My Plan | Everyone | Goal, retention and conversion rates per program. Shows the calls and contacts each program needs |
| **scrResults** – Season Results | Everyone | Post-season actuals per program |
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
ClearCollect(colMyYear,
    Filter('Daily Activity', 'Created By'.Email = User().Email &&
        'Activity Date' >= DateAdd(Today(), -365, TimeUnit.Days)));
Set(varDirClose12, IfError(Sum(colMyYear, 'New Groups Booked - In-Person') / Sum(colMyYear, 'In-Person Calls'), 0));
Set(varIndClose12, IfError(Sum(colMyYear, 'New Groups Booked - Gatekeeper') / Sum(colMyYear, 'Gatekeeper Contacts'), 0));

// Totals used by the tiles
Set(varGoal,          Sum(colMyPlans, 'Sales Goal Units'));
Set(varDirectTarget,  Sum(colMyPlans, 'In-Person Calls Target'));
Set(varIndTarget,     Sum(colMyPlans, 'Gatekeeper Contacts Target'));
Set(varGroupsNeeded,  Sum(colMyPlans, 'Plan - New Groups Needed'));
Set(varDirectDone,    Sum(colMyDays, 'In-Person Calls'));
Set(varIndDone,       Sum(colMyDays, 'Gatekeeper Contacts'));
Set(varBooked,        Sum(colMyDays, 'New Groups Booked - In-Person') + Sum(colMyDays, 'New Groups Booked - Gatekeeper'));
Set(varSalesDays,     Sum(colMyDays, 'Sales Day'));
Set(varUnits,         Coalesce(First(Filter(colMyDays, !IsBlank('MFP Units Season-to-Date'))).'MFP Units Season-to-Date', 0));

// How far through the season we are (reference only; selling comes in bursts, so there's no weekly pace)
Set(varElapsed, Max(0, Min(1,
    DateDiff(varSeason.'Season Start', Today(), TimeUnit.Days) / (varSeason.Weeks * 7))));

// Selling days left in the plan (never below 1, so "per day" never divides by 0)
Set(varDaysLeft, Max(1, Coalesce(varSeason.'Sales Days Goal', 0) - varSalesDays));

If(varIsManager,
    ClearCollect(colAllPlans, Filter('Program Plans',  Season.Id = varSeason.ID));
    ClearCollect(colAllDays,  Filter('Daily Activity', Season.Id = varSeason.ID));
    ClearCollect(colAllYear,  Filter('Daily Activity', 'Activity Date' >= DateAdd(Today(), -365, TimeUnit.Days)));
    ClearCollect(colReps,     Filter(Reps, Active = true))
);
```

**scrHome.OnVisible:** `Select(btnLoad)`

**Season dropdown** (`ddSeason`):
- Items: `Sort(Seasons, 'Season Start', SortOrder.Descending)`
- Value (field shown): `Season`
- Default: `varSeason.Season`
- OnChange: `Set(varSeason, ddSeason.Selected); Select(btnLoad)`

**Header line:** `varSeason.Season & " · " & Text(varElapsed, "0%") & " of the season gone"`

**Tiles.** Add six tiles (a rectangle plus labels). The text formulas:

| Tile | Big number | Small line |
|---|---|---|
| Units | `Text(varUnits, "#,##0")` | `"of " & Text(varGoal, "#,##0") & " goal · " & Text(IfError(varUnits / varGoal, 0), "0%")` |
| In-person calls | `varDirectDone & " / " & varDirectTarget` | `Max(0, varDirectTarget - varDirectDone) & " to go · about " & RoundUp(Max(0, varDirectTarget - varDirectDone) / varDaysLeft, 0) & " per selling day"` |
| Gatekeeper contacts | `varIndDone & " / " & varIndTarget` | `Max(0, varIndTarget - varIndDone) & " to go · about " & RoundUp(Max(0, varIndTarget - varIndDone) / varDaysLeft, 0) & " per selling day"` |
| Sales days | `varSalesDays & " / " & Coalesce(varSeason.'Sales Days Goal', 0)` | `"selling days logged"` |
| New groups | `varBooked & " / " & RoundUp(varGroupsNeeded, 0)` | `"booked of needed this season"` |
| Close rates (12 months) | `Text(varDirClose12, "0%") & " in-person · " & Text(varIndClose12, "0%") & " gatekeeper"` | `"plan: " & Text(IfError(Sum(colMyPlans, 'Plan - New Groups Needed' * '% of New Groups from In-Person') / Sum(colMyPlans, 'In-Person Calls Needed'), 0), "0%") & " · " & Text(IfError(Sum(colMyPlans, 'Plan - New Groups Needed' * (1 - '% of New Groups from In-Person')) / Sum(colMyPlans, 'Gatekeeper Contacts Needed'), 0), "0%")` |

**Progress bars (optional, nice on a phone).** Under each activity tile, add a grey rectangle the full width, and on top of it a coloured rectangle with **Width**:

```powerfx
Parent.Width * Min(1, IfError(varDirectDone / varDirectTarget, 0))      // use the matching numbers for each tile
```

There's deliberately **no red/amber "behind pace" colour**. Selling comes in bursts, so being at 20% of target halfway through the season can be fine. Compare the progress bar with the "% of the season gone" in the header, and look at the **New groups** and **Close rates** tiles. If the 12-month close rates are below plan, the targets are too low and more calls will be needed. Close rates use a full year because a spring call can book a fall group, so one season alone is misleading.

**Buttons:** "Log a Day" → `Navigate(scrLog)`, "My Plan" → `Navigate(scrPlan)`, "Season Results" → `Navigate(scrResults)`, "Team" → `Navigate(scrTeam)` with **Visible** = `varIsManager`.

**Recent days (optional):** a small gallery with Items `FirstN(colMyDays, 5)`, showing `Text(ThisItem.'Activity Date', "ddd mmm d") & ": " & ThisItem.'In-Person Calls' & " in-person, " & ThisItem.'Gatekeeper Contacts' & " gatekeeper"`. (Display only. To edit an earlier day, the rep opens Log a Day and picks that date.)

## 3. scrLog – Log a Day

Controls: a date picker `dpDate`; text inputs (Format = Number) `txtDirect`, `txtIndirect`, `txtDirBook`, `txtIndBook`, `txtUnits`; and a multi-line text input `txtNotes`.

**dpDate.DefaultDate:** `Today()`

**scrLog.OnVisible** and **dpDate.OnChange** (same formula): load that day's row if it already exists:

```powerfx
Set(varExisting, LookUp(colMyDays,
    DateDiff('Activity Date', dpDate.SelectedDate, TimeUnit.Days) = 0))
```

**Default** of each input:

| Control | Default | Hint text |
|---|---|---|
| txtDirect | `varExisting.'In-Person Calls'` | In-person calls today |
| txtIndirect | `varExisting.'Gatekeeper Contacts'` | Gatekeeper contacts today |
| txtDirBook | `varExisting.'New Groups Booked - In-Person'` | New groups booked (in-person) |
| txtIndBook | `varExisting.'New Groups Booked - Gatekeeper'` | New groups booked (gatekeeper) |
| txtUnits | `varExisting.'MFP Units Season-to-Date'` | MFP season-to-date units (if you checked today) |
| txtNotes | `varExisting.Notes` | Notes |

**Save button OnSelect:**

```powerfx
If(
    dpDate.SelectedDate > Today(),
        Notify("You can't log a day in the future.", NotificationType.Error),
    dpDate.SelectedDate < varSeason.'Season Start',
        Notify("That date is before " & varSeason.Season & " started.", NotificationType.Error),
    IsBlank(txtDirect.Text) || IsBlank(txtIndirect.Text),
        Notify("Enter in-person calls and gatekeeper contacts (0 is fine).", NotificationType.Error),
    IfError(
        Patch('Daily Activity',
            If(IsBlank(varExisting), Defaults('Daily Activity'), varExisting),
            {
                Season: { Id: varSeason.ID, Value: varSeason.Season },
                'Activity Date': dpDate.SelectedDate,
                'In-Person Calls': Value(txtDirect.Text),
                'Gatekeeper Contacts': Value(txtIndirect.Text),
                'New Groups Booked - In-Person': Value(txtDirBook.Text),
                'New Groups Booked - Gatekeeper': Value(txtIndBook.Text),
                'MFP Units Season-to-Date': If(IsBlank(txtUnits.Text), Blank(), Value(txtUnits.Text)),
                Notes: txtNotes.Text
            }),
        Notify("Couldn't save: " & FirstError.Message, NotificationType.Error),
        Notify("Day logged. Nice work!", NotificationType.Success);
        Navigate(scrHome)
    )
)
```

## 4. scrPlan – My Plan

1. **Gallery** `galPlans`, Items `colMyPlans`. Show in each row:
   - `ThisItem.Program.Value`
   - `"Goal " & ThisItem.'Sales Goal Units' & " · " & RoundUp(ThisItem.'Plan - New Groups Needed', 0) & " new groups needed"`
   - `"Target: " & ThisItem.'In-Person Calls Target' & " in-person calls · " & ThisItem.'Gatekeeper Contacts Target' & " gatekeeper contacts"`
2. **Edit form** `frmPlan`: DataSource `'Program Plans'`, Item `galPlans.Selected`. Fields, in this order:
   - Season, Program
   - Prior Year Units, Prior Year Groups
   - Growth Goal %, Goal Units Override
   - Retention %, Avg Units per New Group
   - % of New Groups from In-Person, In-Person Close %, Gatekeeper Close %
3. **Season card:** set the card's **Update** to `{ Id: varSeason.ID, Value: varSeason.Season }` and **Visible** to `false`. The rep never picks a season; it's always the one on the scorecard.
4. **Percent cards** (Growth Goal %, Retention %, % of New Groups from In-Person, In-Person Close %, Gatekeeper Close %). SharePoint stores 50% as 0.5, so that reps can type 50:
   - The text input's **Default**: `Parent.Default * 100`
   - The card's **Update**: `Value(<that text input>.Text) / 100`
5. **Live preview under the form**, so the rep sees the calls needed before saving. Add a label with **Text**:

   ```powerfx
   With({
       prior:  Value(<Prior Year Units input>.Text),
       growth: Value(<Growth Goal % input>.Text) / 100,
       over:   Value(<Goal Units Override input>.Text),
       ret:    Value(<Retention % input>.Text) / 100,
       avg:    Value(<Avg Units input>.Text),
       share:  Value(<% from In-Person input>.Text) / 100,
       dc:     Value(<In-Person Close % input>.Text) / 100,
       ic:     Value(<Gatekeeper Close % input>.Text) / 100
   },
   With({ goal: If(over > 0, over, Round(prior * (1 + growth), 0)) },
   With({ groups: IfError(Max(0, goal - Round(prior * ret, 0)) / avg, 0) },
       "Goal " & goal & " units → " & RoundUp(groups, 0) & " new groups → " &
       RoundUp(IfError(groups * share / dc, 0) * 1.1, 0) & " in-person calls and " &
       RoundUp(IfError(groups * (1 - share) / ic, 0) * 1.1, 0) & " gatekeeper contacts (incl. 10% cushion)")))
   ```

   Replace each `<… input>` with the control name Power Apps gave that field's text box (for example `DataCardValue5`).
6. **"Add program" button:** `NewForm(frmPlan)`
7. **Save button:** this blocks a second row for the same program and season:

   ```powerfx
   If(frmPlan.Mode = FormMode.New &&
      !IsBlank(LookUp(colMyPlans, Program.Value = <Program card's dropdown>.Selected.Value)),
       Notify("You already have a plan for that program this season. Select it to edit.", NotificationType.Warning),
       SubmitForm(frmPlan))
   ```

8. **frmPlan.OnSuccess:** `Refresh('Program Plans'); ClearCollect(colMyPlans, Filter('Program Plans', Season.Id = varSeason.ID && 'Created By'.Email = User().Email)); Notify("Plan saved", NotificationType.Success)`
9. **Header totals:** `"Season goal " & Sum(colMyPlans, 'Sales Goal Units') & " · " & Sum(colMyPlans, 'In-Person Calls Target') & " in-person calls · " & Sum(colMyPlans, 'Gatekeeper Contacts Target') & " gatekeeper contacts"`

## 5. scrResults – Season Results

Copy scrPlan (right-click → Duplicate screen) and change the form fields to the **Actual –** input columns: Total Units, Total Groups, Retained Units (ran last year), Retained Groups (ran last year). Remove the "Add program" button and the live preview, because results go on the existing plan rows. Normally these are filled from the yearly MFP pull, so this screen is mostly for viewing and correcting.

Gallery row text:

```powerfx
ThisItem.Program.Value & ": " & Text(ThisItem.'Actual - Attainment %', "0%") & " of goal · retention " &
Text(ThisItem.'Actual - Unit Retention %', "0%") & " (plan " & Text(ThisItem.'Retention %', "0%") & ")" &
" · " & ThisItem.'Actual - New Groups' & " new groups (plan " & RoundUp(ThisItem.'Plan - New Groups Needed', 0) & ")"
```

Add a line under the gallery for the close rates, which cover the rep overall rather than each program:

```powerfx
"Close rates, last 12 months: " & Text(varDirClose12, "0%") & " in-person · " & Text(varIndClose12, "0%") & " gatekeeper"
```

## 6. scrTeam – Team (managers)

**Gallery** `galTeam`, **Items**:

```powerfx
Sort(
    ForAll(colReps As r,
        With({
            p: Filter(colAllPlans, Lower('Created By'.Email) = Lower(r.Rep.Email)),
            d: Sort(Filter(colAllDays, Lower('Created By'.Email) = Lower(r.Rep.Email)),
                    'Activity Date', SortOrder.Descending),
            y: Filter(colAllYear, Lower('Created By'.Email) = Lower(r.Rep.Email))
        },
        {
            RepName:      r.'Rep Name',
            Code:         r.'MFP Owning User Code',
            Goal:         Sum(p, 'Sales Goal Units'),
            Units:        Coalesce(First(Filter(d, !IsBlank('MFP Units Season-to-Date'))).'MFP Units Season-to-Date', 0),
            DirectDone:   Sum(d, 'In-Person Calls'),
            DirectTarget: Sum(p, 'In-Person Calls Target'),
            IndDone:      Sum(d, 'Gatekeeper Contacts'),
            IndTarget:    Sum(p, 'Gatekeeper Contacts Target'),
            Booked:       Sum(d, 'New Groups Booked - In-Person') + Sum(d, 'New Groups Booked - Gatekeeper'),
            Needed:       RoundUp(Sum(p, 'Plan - New Groups Needed'), 0),
            SalesDays:    Sum(d, 'Sales Day'),
            LastDay:      First(d).'Activity Date',
            DirClose12:   IfError(Sum(y, 'New Groups Booked - In-Person') / Sum(y, 'In-Person Calls'), 0),
            IndClose12:   IfError(Sum(y, 'New Groups Booked - Gatekeeper') / Sum(y, 'Gatekeeper Contacts'), 0),
            HasPlan:      CountRows(p) > 0
        })
    ),
    IfError(Units / Goal, 0), SortOrder.Descending
)
```

Labels in each row:

- `ThisItem.RepName & " (" & ThisItem.Code & ")"`
- `Text(IfError(ThisItem.Units / ThisItem.Goal, 0), "0%") & " of " & ThisItem.Goal & " units"`
- `"In-Person " & ThisItem.DirectDone & " / " & ThisItem.DirectTarget & " · Gatekeeper " & ThisItem.IndDone & " / " & ThisItem.IndTarget`
- `"Groups " & ThisItem.Booked & " / " & ThisItem.Needed & " · " & ThisItem.SalesDays & " selling days · last " & If(IsBlank(ThisItem.LastDay), "never", Text(ThisItem.LastDay, "mmm d"))`
- `"Close (12 mo) " & Text(ThisItem.DirClose12, "0%") & " in-person · " & Text(ThisItem.IndClose12, "0%") & " gatekeeper"`
- A red "No plan yet" label with **Visible** `!ThisItem.HasPlan`

Team totals across the top: `Sum(galTeam.AllItems, Units)`, `Sum(galTeam.AllItems, Goal)`, and so on.

## 7. Publish and share

1. **File → Save → Publish.** Until you share it, only you can see it, which is good for testing.
2. **Share** the app (app → **Share**) with the reps and the other manager, as **User**, not Co-owner. **Untick "Send an email invitation"** if you don't want anyone notified yet. Power Apps shares to people or Entra security groups; it can't use the SharePoint groups.
3. Reps install **Power Apps** from the App Store / Google Play, sign in with their work account, and pin the app (or add it to their home screen).
4. Updates are automatic: republish, and everyone gets the new version the next time they open the app.

## Optional later

- **Plan approval:** add an "Approved" Yes/No column that only managers set, and lock the plan form when it's ticked.
- **Wide-screen manager dashboard:** a separate Tablet-format app with just the Team screen, for desktop use.
- **Power BI dashboard:** if your plan includes Power BI Pro (E5 does; Business Standard and Business Premium don't, as far as I know), connect Power BI Desktop to the lists for history charts across seasons.
