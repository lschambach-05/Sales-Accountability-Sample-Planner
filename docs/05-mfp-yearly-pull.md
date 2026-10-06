# 5. Yearly MFP pull (for prior-year and retention numbers)

Once a year, pull group-level sales from My Fundraising Place (MFP) for the last two years. Retained groups are then matched from the raw rows, not counted by hand in MFP.

**How:** paste the prompt below into a Claude session that has Claude in Chrome and the Sales Accountibility Sample Planner folder connected. Log in to MFP yourself first, because Claude can't enter your password. The browser is used read-only, and nothing in MFP is changed. Update the years at the top of the prompt each time.

_Last run: October 5, 2026, covering 2024–2025. The decisions below came from that run._

## Prompt to paste into Claude (with Chrome)

> **Task: export group-level sales from My Fundraising Place, read-only.**
>
> I'm logged in to My Fundraising Place (app.myfundraisingplace.com) in Chrome. Pull fundraiser-level sales for **2024 and 2025** (Spring and Fall) for all owning users. This is read-only. Do not edit, reassign, save or submit anything in MFP. If any step would change data, stop and ask me.
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
> - `MFP group sales YYYY-YYYY.xlsx`, with sheets **Fundraisers**, **Season Check** (rows, rows with units, units and invoice $ by season and status), **Units by Rep**, **Group Checks** (group names that appear under more than one Group ID) and **Notes** (source, season rule, anything that looked off).
> - CSV copies of each sheet: `MFP group sales YYYY-YYYY.csv` for Fundraisers, and `… - Notes.csv`, `… - Season Check.csv` and `… - Group Checks.csv`. Other Claude sessions can't read the whole xlsx through the connector, but they can read the CSVs.
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
- **Programs:** MFP "Braided Pastry" = Butter Braid Pastry. Combo and Batavia Music Buffs are their own programs.
- **Duplicate groups:** listed in `GROUP_MERGES`. **Placed groups:** listed in `OWNER_OVERRIDES`.
- **Retained:** the group ran any program, in either season, the previous year.

The sales data itself is kept in SharePoint, not in this repository.

## Group locations (for placing unassigned groups)

When a group's last owner is no longer a rep, the group goes to the **current rep with the most groups in the same city**, or failing that, the **same county** (Lynwood, Oct 2026). Ties, and groups with no match, are listed for Lynwood to decide. This needs each group's location, which the sales pull doesn't include. Paste this into the Claude-with-Chrome session:

> **Task: export group locations from My Fundraising Place, read-only.**
>
> Using the groups in `MFP group sales 2024-2025.csv` (in my SharePoint folder Rite Bite Claude Skills → Documents → Lynwood → Sales Accountibility Sample Planner), look up each **Group ID**'s address in My Fundraising Place. This is **read-only**: don't edit or save anything in MFP.
>
> Save `MFP group locations.csv` to the same folder with one row per Group ID and these columns: **Group ID, Group Name, City, State, ZIP, County**. Fill County only if MFP stores it; otherwise leave it blank. If the address only exists on the group's invoices, use the bill-to or ship-to address and add a **Source** column saying which one.
>
> If looking up every group is too slow, do these 7 groups first, then the rest: 163565, 191059, 191570, 191969, 192955, 193455, 202009. Tell me how many groups have no address.
