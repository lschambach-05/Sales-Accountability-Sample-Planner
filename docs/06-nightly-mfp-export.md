# 6. Nightly MFP export (planned)

**Goal (Lynwood, October 2026):** replace the Monday Claude-in-Chrome pull and the manual PowerShell load with a program that runs each evening on a Rite Bite computer, unattended, and updates the planner's MFP numbers by itself.

## What the program should do

`tools/mfp_nightly.py`, run nightly by Windows Task Scheduler (e.g. 9 pm):

1. **Log in to My Fundraising Place** (app.myfundraisingplace.com) with a stored username and password. MFP has **no API** and **no two-factor login**. The password lives in Windows Credential Manager (e.g. the `keyring` package), never in the script or the repository.
2. **Download every fundraiser** with a delivery date from the start of the season three seasons back to the end of the current planner season (for 2027 Spring: July 1, 2025 to June 30, 2027), the same way the Chrome pulls did:
   - `/grid/Fundraisers` for the list (50 rows per page, all owning users, all statuses);
   - `/grid/Invoices` for Group ID and Group Name, joined on FundraiserId;
   - `/api/fundraisers/{id}` for fundraisers with no invoice (most upcoming bookings);
   - `/api/groups/{id}` for each group's **current owner**. Cache owners between runs so a normal night only looks up new groups.
   - Request formats, field names and the login form are documented in `MFP technical notes.txt` in the SharePoint folder below, written by the Chrome session. They're not public API, so MFP can change them; fail loudly when a response doesn't look as expected.
3. **Build the same CSV** as the weekly pull (columns: Owning User, Group ID, Group Owner, Group Name, Program, Event Name, Status, Fundraiser State, Start Date, Delivery Date, Season, Units, Invoice $, Invoices, Fundraiser ID, Flags), with the season by delivery date in Central time (Jan 1–Jun 30 = Spring, Jul 1–Dec 31 = Fall; no delivery date → start date, flagged). See the prompt in [05-mfp-pull.md](05-mfp-yearly-pull.md#weekly-mfp-numbers-units-to-date-and-new-groups).
4. **Run the existing calculation**: reuse `tools/build_rep_progress.py` / `tools/mfp_rules.py` (import them; don't reimplement the rules). The planner season is the Seasons list row ticked **Current Season**.
5. **Update Rep Baselines** the way `tools/Import-RepProgress.ps1` does (MFPUnitsToDate, MFPNewGroups, MFPNewGroups12, MFPAsOf on each rep's row for the season, matched by MFP code via the Reps list; new rows get per-item permissions: Sales Planner Managers Full Control + that rep Read). Unattended, so app-only auth with a certificate on the existing Sales Planner app registration (or calling the PowerShell script with certificate parameters).
6. **Save the day's CSV** to the SharePoint folder for the record, and **email Lynwood** if any step fails, so the numbers never go quietly stale.

## Checks before it runs unattended

- Output for 2027 Spring as of 2026-10-14 must match the manual run: BPR 0/2/25, JK 0/2/21, JMK 0/3/22, KJP 0/0/4, KJS 0/2/15, RB 0/3/14 (units / new groups / new groups last 2 seasons), and the season totals of the October 14 pull (Fall 2025 212,213 units; Spring 2026 112,124).
- Read-only in MFP: GET/list requests only, apart from the login.
- No sales data in the repository: CSVs, caches and logs go to the local machine or SharePoint, not GitHub.

## Open items for Lynwood

- Confirm MFP is fine with an automated nightly login (and whether they can create a read-only user for it).
- Which computer runs it (on in the evening, Python installed).
- Certificate for the app registration (the program's setup steps will cover it).

## Where things are

- SharePoint folder: Rite Bite Claude Skills → Documents → Lynwood → Sales Accountibility Sample Planner (pulls, `MFP progress YYYY-MM-DD.csv`, `MFP technical notes.txt`).
- Site: https://ritebitefundraising.sharepoint.com/sites/SalesPlanner (lists: Seasons, Reps, Rep Baselines).
- This session can't reach MFP (the cloud proxy blocks it), so MFP requests can only be tested on Lynwood's computer.
