# 5. MFP pull (for prior-year and retention numbers)

**The planner works one season at a time** (Lynwood, October 2026). Before each season, pull that season from the two years before it: for **2027 Spring**, pull **Spring 2025 and Spring 2026**; in June, pull Fall 2025 and Fall 2026 for **2027 Fall**. (The October 2026 run below pulled all of 2024–2025, for the baseline workbook.)

Pull group-level sales from My Fundraising Place (MFP). Retained groups are then matched from the raw rows, not counted by hand in MFP.

**How:** paste the prompt below into a Claude session that has Claude in Chrome and the Sales Accountibility Sample Planner folder connected. Log in to MFP yourself first, because Claude can't enter your password. The browser is used read-only, and nothing in MFP is changed. Update the seasons at the top of the prompt each time.

_Runs: October 5, 2026 (all of 2024–2025, for the baseline workbook) and October 8, 2026 (Spring 2025 and Spring 2026, for 2027 Spring: 986 fundraisers; Spring 2025 matched the first run exactly, Spring 2026 had 466 fundraisers and 112,124 units). MFP stores a current owner on each group record, and the October 8 pull includes it. The decisions below came from the first run._

## Prompt to paste into Claude (with Chrome)

> **Task: export group-level sales from My Fundraising Place, read-only.**
>
> I'm logged in to My Fundraising Place (app.myfundraisingplace.com) in Chrome. Pull fundraiser-level sales for **Spring 2025 and Spring 2026** (delivery dates January 1 – June 30 of each year) for all owning users. This is read-only. Do not edit, reassign, save or submit anything in MFP. If any step would change data, stop and ask me.
>
> **Source (already decided, so don't re-ask):**
> - Main list: **Sales → Fundraisers**, all owning users, all statuses. Read it through the grid's own data request (`/grid/Fundraisers`, 50 rows per page) with a date window about 6 months wider than the target years on each side. The grid's date filter matches delivery date, so the counts per half-year should line up with the seasons.
> - The Fundraisers grid does **not** return Group ID or Group Name. Get them from **Sales → Invoices** (`/grid/Invoices`, same date window). Every invoice has a GroupId and a FundraiserId, so join them on FundraiserId. For fundraisers with no invoice (mostly canceled ones), read the group from `/api/fundraisers/{id}` (the `Group` object). That record also has `DeliveredOn`.
> - **Leave out invoices with no fundraiser attached.** These are mostly GJS wholesale accounts, a few hundred units a year at most.
>
> **One row per fundraiser, with these columns:**
>
> | Column | Notes |
> |---|---|
> | Owning User | The fundraiser's owning user. If the invoice owner is different, flag the row. |
> | Group ID | MFP's permanent group ID. This is the key column for retention. |
> | Group Owner | The group's **current** owning user, from the group record (`/api/groups/{id}`). The planner credits each group's history to this rep. |
> | Group Name | From the linked invoice or the fundraiser record |
> | Program | Program family, with OLD/NEW labels dropped (see below) |
> | Event Name | As shown in MFP |
> | Status / Fundraiser State | Closed, Open or Canceled / Paid, Booked, etc. |
> | Start Date, Delivery Date | Delivery Date is the primary invoice's Delivered On, converted to Central time |
> | Season | **By delivery date:** Jan 1–Jun 30 is Spring, Jul 1–Dec 31 is Fall. If there's no delivery date, use the start date and flag the row. |
> | Units | Total Items from the Fundraisers grid |
> | Invoice $, Invoices, Fundraiser ID, Flags | Flags cover: event-name season ≠ delivery season, no delivery date, different invoice owner, units that don't match the invoices, multiple invoice delivery dates |
>
> **Program names:** OLD/NEW labels mean nothing in MFP, because they're all the same program. Combine them: OLD/NEW Combo → Combo, OLD/NEW Wooden Spoon → Wooden Spoon, and "Braided Pastry 2022 With Pastry Ring" → Braided Pastry. Keep canceled fundraisers in the file (Status = Canceled, no units) so they can be filtered out. List any blank or odd programs for me rather than guessing.
>
> **Getting the data out of the browser:** the page data is too large to read back directly. Ask me before downloading. Then build a CSV in the page, download it to my Downloads folder, and ask for access to that folder to build the Excel file.
>
> **Save** to Rite Bite Claude Skills → Documents → Lynwood → Sales Accountibility Sample Planner:
> - `MFP group sales Spring 2025-2026.xlsx` (name it for the seasons pulled), with sheets **Fundraisers**, **Season Check** (rows, rows with units, units and invoice $ by season and status), **Units by Rep**, **Group Checks** (group names that appear under more than one Group ID) and **Notes** (source, season rule, anything that looked off).
> - CSV copies of each sheet: `MFP group sales Spring 2025-2026.csv` for Fundraisers, and `… - Notes.csv`, `… - Season Check.csv` and `… - Group Checks.csv`. Other Claude sessions can't read the whole xlsx through the connector, but they can read the CSVs.
>
> **Tell me:** rows per season, whether every row has a Group ID, how many rows were flagged and why, and any group names that appear under more than one Group ID.

## 2024–2025 run, for reference

| Season | Fundraisers | With units | Units |
|---|---|---|---|
| Spring 2024 | 527 | 498 | 133,992 |
| Fall 2024 | 697 | 649 | 218,620 |
| Spring 2025 | 520 | 493 | 122,586 |
| Fall 2025 | 691 | 661 | 212,213 |

- Every row had a Group ID (1,325 groups).
- Fundraiser units matched the linked invoices on every row except one. The Power BI dashboard was not checked.
- 86 rows had an event name whose season disagreed with the delivery date.
- 18 rows had a different rep on the invoice than on the fundraiser, left over from reassignments.
- 25 invoices with no fundraiser (185 units) were left out.
- 13 group names appear under more than one Group ID. Most are different organizations with the same name. A few may be duplicate records.

## Decisions (Lynwood, October 2026)

- **Braided Pastry** in MFP is the planner's **Butter Braid Pastry**.
- **Combo** is its own program.
- **Batavia Music Buffs** is a single group that runs all products. MFP names it as a program by year, but it is **not** a planner program (Lynwood, Oct 2026). Its units are planned under an existing program; see `PROGRAMS` in the baseline script.
- **Current reps:** BPR, JK, JMK, KJP, KJS, RB. Rollups: BLS → KJS, LBS → KJP, LMD → JMK.
- **A group's history moves to its current rep**, meaning the owner of its most recent counted fundraiser. Groups last owned by anyone else (BJS, GLP, LSS) go to the current rep with the most groups in the same city, or failing that the same county. See *Group locations* below.
- **Open fundraisers count if they were invoiced** (units sold). Open bookings with nothing sold are left out, and so are canceled fundraisers.
- **Duplicate group records:** Group ID 199961 is merged into 84951 (St. Paul's Lutheran School, JK). Other same-name IDs stay separate.

## What happens next (in the planner build)

With that file in the SharePoint folder, the retention numbers are calculated for each rep, program and season, using the season's Retention Rule. By default, a group counts as retained if it ran any program, in either season, the year before. Its units count toward the program it runs this year.

| Output per rep × program × season | Used for |
|---|---|
| Units, groups | Next year's Prior Year Units / Prior Year Groups |
| Retained units, retained groups | Actual – Retained Units / Groups and retention % |
| New units, new groups | Avg units per new group |

The result is a ready-to-import sheet for the Program Plans list, so reps start their 2026 plans with last year's numbers already filled in.

## Turning the pull into each rep's baseline

`tools/build_rep_baseline.py` turns the pull's CSV into **Rep Baseline (from MFP).xlsx**. The workbook has a Read Me tab, a planner-ready Rep Program Summary, Rep Totals, Group Detail and a Review tab. Every total and percentage is a live Excel formula over Group Detail.

```bash
python tools/build_rep_baseline.py "MFP group sales 2024-2025.csv" "Rep Baseline 2025 (from MFP).xlsx"
```

The rules (agreed with Lynwood, October 2026) are set at the top of the script. Update them when reps or programs change:

- **Current reps:** BPR, JK, JMK, KJP, KJS, RB. Rollups: BLS → KJS, LBS → KJP, LMD → JMK. Groups last owned by anyone else show as *Unassigned*.
- **Each group's history** goes to its current rep: the owner of its most recent counted fundraiser.
- **What counts:** Closed fundraisers, plus Open ones that were invoiced (units sold). Canceled fundraisers and Open bookings with nothing sold are left out.
- **Programs:** MFP "Braided Pastry" = Butter Braid Pastry. Combo is its own program. Batavia Music Buffs is one group, not a planner program.
- **Duplicate groups:** listed in `GROUP_MERGES`. **Placed groups:** listed in `OWNER_OVERRIDES`.
- **Retained:** the group ran any program, in either season, the previous year.

The sales data itself is kept in SharePoint, not in this repository.

## Plan starting numbers for each rep (pre-filled in My Plan)

Before a season, work out each rep's starting numbers from the pull and load them into the **Rep Baselines** list. My Plan then fills them in, so reps only add their Unit Goal and close rate.

**Which seasons the pull needs:** the same season two years back through last season. For **2027 Spring**: Spring 2025, Fall 2025 and Spring 2026. For **2027 Fall**, in June: Fall 2025, Spring 2026 and Fall 2026. The weekly pull's window covers these too.

1. Work out the numbers (one CSV per season planned):

   ```bash
   python tools/build_plan_baseline.py "2027 Spring" "Plan Baseline 2027 Spring.csv" "MFP group sales 2024-2025.csv" "MFP group sales Spring 2025-2026.csv"
   ```

   It needs the same season two years back through last season (for 2027 Spring: Spring 2025, Fall 2025 and Spring 2026); several pull files can be listed.

   It prints a table per rep to check. The rules are in [02-data-model.md](02-data-model.md#retention-one-definition-everywhere): returning = ran in either season of the year before, new = ran in neither; each group's history goes to the rep who owns it now; average = all of the rep's groups last season.

2. Make sure the season exists in the **Seasons** list and every rep is in the **Reps** list with their **MFP Owning User Code** and **Rep** person filled in.

3. Load it (PowerShell 7, same sign-in app as the setup script). Download `tools/Import-RepBaselines.ps1` from GitHub and unblock it like the setup script:

   ```powershell
   ./tools/Import-RepBaselines.ps1 `
       -SiteUrl  https://ritebitefundraising.sharepoint.com/sites/SalesPlanner `
       -ClientId <client id> `
       -CsvPath  "Plan Baseline 2027 Spring.csv"
   ```

   Each row gets its own permissions (managers + that rep). Running it again updates the rows rather than adding duplicates.

**2027 Spring (October 8, 2026):** built from the Spring 2025–2026 pull with MFP's current group owners. Every unit went to a current rep: the reps add up to the season totals (122,586 for Spring 2025, 112,124 for Spring 2026). The per-rep file is `Plan Baseline 2027 Spring.csv`, kept with the pull in SharePoint.

**Checked on the 2024–2025 pull** for 2026 Fall (Fall 2024 → Fall 2025), as a test: every Fall 2024 and Fall 2025 unit was credited to a current rep, and the per-rep units add up to the season totals (218,620 and 212,213). The groups moved from BPR to KJS count as KJS's, in both years. The per-rep numbers are in the CSV, kept with the pull in SharePoint, not in this repository.

## Weekly MFP numbers (units to date and new groups)

Reps only log **sales calls** in the app; Log a Day shows the MFP numbers but they can't be changed there. Season-to-date units and new groups booked come from MFP once a week (Monday morning, before the manager digest), so they're never more than a week old. Home, Log a Day and Team show the date of the last pull.

1. Log in to MFP in Chrome, then paste this into a Claude-with-Chrome session that has the planner folder connected (change the date in the file name):

   > **Task: weekly export of fundraisers from My Fundraising Place, read-only.**
   >
   > I'm logged in to My Fundraising Place (app.myfundraisingplace.com) in Chrome. Pull every fundraiser, for all owning users and all statuses (including Open and upcoming bookings), with a delivery date from **July 1, 2025 to June 30, 2027**. This is read-only. Don't edit, reassign, save or submit anything in MFP. If any step would change data, stop and ask me.
   >
   > Use the same method as the October 8, 2026 pull (`MFP group sales Spring 2025-2026.csv` in the folder below): the Fundraisers grid (`/grid/Fundraisers`) for the list, Group ID and Group Name from the Invoices grid joined on FundraiserId, and `/api/fundraisers/{id}` for fundraisers with no invoice (most upcoming bookings won't have one yet). Leave out invoices with no fundraiser.
   >
   > One row per fundraiser, with the **same columns** as that file: Owning User, Group ID, **Group Owner** (the group's current owning user, from `/api/groups/{id}`), Group Name, Program (OLD/NEW labels combined), Event Name, Status, Fundraiser State, Start Date, Delivery Date (Central time), Season (Jan 1–Jun 30 = Spring, Jul 1–Dec 31 = Fall, by delivery date; if there's no delivery date use the start date and flag it), Units, Invoice $, Invoices, Fundraiser ID, Flags. Keep canceled fundraisers (Status = Canceled).
   >
   > Ask me before downloading. Save **only a CSV** named `MFP progress 2026-10-14.csv` to Rite Bite Claude Skills → Documents → Lynwood → Sales Accountibility Sample Planner. No Excel file is needed.
   >
   > **Tell me:** rows and units per season and status, whether every row has a Group ID and Group Owner, and how many rows were flagged and why.

2. Work out the numbers:

   ```bash
   python tools/build_rep_progress.py "2027 Spring" 2027-03-08 "Rep Progress 2027 Spring.csv" "MFP progress 2027-03-08.csv"
   ```

3. Load them (updates only the MFP columns on each rep's Rep Baselines row). With `Import-RepProgress.ps1` (from `tools/` on GitHub) and the progress CSV both in Downloads, in PowerShell 7 (this picks the newest copy of each, so a browser's " (1)" doesn't matter):

   ```powershell
   $script = Get-ChildItem "$HOME\Downloads\Import-RepProgress*.ps1" | Sort-Object LastWriteTime | Select-Object -Last 1
   $csv = Get-ChildItem "$HOME\Downloads\Rep Progress 2027 Spring*.csv" | Sort-Object LastWriteTime | Select-Object -Last 1
   $script.FullName; $csv.FullName
   Unblock-File $script.FullName
   & $script.FullName -SiteUrl https://ritebitefundraising.sharepoint.com/sites/SalesPlanner -ClientId <client id> -CsvPath $csv.FullName
   ```

   First run, October 14, 2026 (pull of July 2025 – June 2027 deliveries, 1,866 fundraisers): loaded for the test rep; the others are skipped until they're in the Reps list.

Everything is by **delivery date** (the season a fundraiser runs in). MFP's "Booked On" date isn't used: groups often book a year ahead, so it doesn't show when the sale was won (Lynwood, October 2026).

| Column | Rule |
|---|---|
| MFP Units to Date | Units on the rep's fundraisers delivered in the current season (canceled left out) |
| MFP New Groups | Groups booked for the current season that didn't run in either of the two seasons before (for Spring 2027: not Fall 2026, not Spring 2026) |
| MFP New Groups Last 2 Seasons | New groups in the current season plus the one before, about a year of bookings. The close rate is this ÷ sales calls logged in the last 12 months |
| MFP As Of | The pull date |

Each group counts for the rep who owns it **now** (the owner on the group's record in MFP), once per season. A fundraiser counts as run or booked unless it's Canceled, Closed with no units, or Open with nothing sold more than 30 days after its delivery date, so a group booked for a season still under way already counts as running it (and isn't "new" the season after). Checked October 2026 with Spring 2026 as the season: units (112,124) and new groups per rep matched the plan baseline.

## Group locations (for placing unassigned groups)

When a group's last owner is no longer a rep, the group goes to the **current rep with the most groups in the same city**, or failing that, the **same county** (Lynwood, Oct 2026). Ties, and groups with no match, are listed for Lynwood to decide. This needs each group's location, which the sales pull doesn't include. Paste this into the Claude-with-Chrome session:

> **Task: export group locations from My Fundraising Place, read-only.**
>
> Using the groups in `MFP group sales 2024-2025.csv` (in my SharePoint folder Rite Bite Claude Skills → Documents → Lynwood → Sales Accountibility Sample Planner), look up each **Group ID**'s address in My Fundraising Place. This is **read-only**: don't edit or save anything in MFP.
>
> Save `MFP group locations.csv` to the same folder with one row per Group ID and these columns: **Group ID, Group Name, City, State, ZIP, County**. Fill County only if MFP stores it; otherwise leave it blank. If the address only exists on the group's invoices, use the bill-to or ship-to address and add a **Source** column saying which one.
>
> If looking up every group is too slow, do these 7 groups first, then the rest: 163565, 191059, 191570, 191969, 192955, 193455, 202009. Tell me how many groups have no address.
