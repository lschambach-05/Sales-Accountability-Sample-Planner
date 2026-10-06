# 5. Yearly MFP pull (for prior-year and retention numbers)

Once a year, pull **group-level** sales from My Fundraising Place (MFP) for the last two years. Retained groups are then matched from the raw rows, not counted by hand in MFP.

**How:** paste the prompt below into a Claude session that has **Claude in Chrome**, with you logged in to MFP. The browser is used **read-only**; nothing in MFP is changed. Update the years at the top of the prompt each time.

---

## Prompt to paste into Claude (with Chrome)

> **Task: export group-level sales from My Fundraising Place, read-only.**
>
> I'm logged in to My Fundraising Place (app.myfundraisingplace.com) in Chrome. Pull fundraiser/group-level sales for **2024 and 2025** (both Fall and Spring seasons) for **all owning users** (sales reps). This is **read-only**: do not edit, reassign, save, or submit anything in MFP. If any step would change data, stop and ask me.
>
> **What I need: one row per fundraiser (group × program × season):**
>
> | Column | Notes |
> |---|---|
> | Owning User | Rep code, for example BLS or KJS |
> | Group ID | MFP's permanent ID for the organization/group, if one exists. This is the most important column: it's how we tell whether a group ran the previous year. |
> | Group Name | As shown in MFP |
> | Program | For example Butter Braid, Wooden Spoon, Joyful Tradition, Bella Napoli, Croissant Crowns |
> | Fundraiser start or delivery date | Whatever date MFP uses to place a fundraiser in a season |
> | Season | Fall or Spring, plus the year, based on that date |
> | Units | Units sold for that fundraiser |
>
> **Steps:**
> 1. First find the screen or report in MFP that lists fundraisers with owning user, group, program, date, and units, and that **includes standing/recurring accounts**. Note: the Invoices grid is known to miss standing/recurring accounts, so don't use it as the only source unless you confirm it includes them. Tell me which screen you chose and why before pulling everything.
> 2. If MFP has an Excel/CSV export on that screen, use it. Otherwise read the grid page by page.
> 3. Check that each season's unit totals roughly match MFP's own totals or dashboard for that season. Report any gaps.
> 4. Save one Excel file named `MFP group sales 2024-2025.xlsx` to my SharePoint folder **Rite Bite Claude Skills → Documents → Lynwood → Sales Accountibility Sample Planner**. Put the raw rows on a sheet called `Fundraisers`, and add a `Notes` sheet saying which MFP screen and filters you used, the date ranges you treated as Fall and Spring, and anything that looked off.
> 5. Tell me: how many rows per season, whether a stable Group ID was available, and any groups whose ID or name looked inconsistent between years.

---

## What happens next (in the planner build)

With that file in the SharePoint folder, the retention numbers are calculated for each rep and program, using the season's **Retention Rule** (default: a group is retained if it ran **any program, in either season, the previous year**). Its units count toward the program it runs this year.

| Output per rep × program × season | Used for |
|---|---|
| Units, groups | Next year's **Prior Year Units / Prior Year Groups** |
| Retained units, retained groups | **Actual – Retained Units / Groups** and retention % |
| New units, new groups | Avg units per new group |

The result is a ready-to-import sheet for the **Program Plans** list, so reps start their 2026 plans with last year's numbers already filled in.

## Turning the pull into each rep's baseline

`tools/build_rep_baseline.py` turns the pull's CSV into **Rep Baseline (from MFP).xlsx**. The workbook has a Read Me tab, a planner-ready Rep Program Summary, Rep Totals, Group Detail and a Review tab. Every total and percentage is a live Excel formula over Group Detail.

```bash
python tools/build_rep_baseline.py "MFP group sales 2024-2025.csv" "Rep Baseline 2025 (from MFP).xlsx"
```

The rules (agreed with Lynwood, October 2026) are set at the top of the script. Update them when reps or programs change:

- **Current reps:** BPR, JK, JMK, KJP, KJS, RB. Rollups: BLS → KJS, LBS → KJP, LMD → JMK. Groups last owned by anyone else show as *Unassigned*.
- **Each group's history** goes to its current rep: the owner of its most recent counted fundraiser.
- **What counts:** Closed fundraisers, plus Open ones that were invoiced (units sold). Canceled fundraisers and Open bookings with nothing sold are left out.
- **Programs:** MFP "Braided Pastry" = Butter Braid Pastry. Combo is its own program.
- **Retained:** the group ran any program, in either season, the previous year.

The sales data itself is kept in SharePoint, not in this repository.
