# 6. Nightly MFP export

**Goal (Lynwood, October 2026):** replace the Monday Claude-in-Chrome pull and the manual PowerShell load with a program that runs each evening on a Rite Bite computer, unattended, and updates the planner's MFP numbers by itself.

**Status (October 14, 2026):** written and tested here with a fake MFP (`tools/test_mfp_nightly.py`). The October 14 pull gives the same per-rep numbers as `build_rep_progress.py` did before the change. **Not yet run against MFP or with the certificate.** This cloud session can't reach MFP. Also, `MFP technical notes.txt` wasn't in the SharePoint folder when the program was written, so the MFP request details are settings for you to fill in from the notes (step 4 below).

## What it does

`tools/mfp_nightly.py run`, started each night by Windows Task Scheduler:

1. Reads the **Current Season** row of the Seasons list (for example 2027 Spring).
2. Logs in to MFP with the username in its settings and the password from Windows Credential Manager. It reads every fundraiser delivered from the start of the season three seasons back to the end of the current season (2027 Spring: July 1, 2025 to June 30, 2027), using the same four requests as the Chrome pulls (`/grid/Fundraisers`, `/grid/Invoices`, `/api/fundraisers/{id}`, `/api/groups/{id}`). Group owners are cached. Each night it looks up new groups plus about a seventh of the rest, so every owner is re-read about once a week. Records of closed and canceled fundraisers are cached too.
3. Builds the same CSV as the weekly pull (same columns, season by Central-time delivery date, same flags) and saves it as `MFP progress YYYY-MM-DD.csv`.
4. Runs `build_rep_progress.py`'s calculation (imported, not copied) → `Rep Progress <season> YYYY-MM-DD.csv`.
5. Saves both CSVs to SharePoint: Rite Bite Claude Skills → Documents → Lynwood → Sales Accountibility Sample Planner → **Nightly**. A subfolder keeps the main folder tidy; change `records_folder` in the settings to save elsewhere.
6. Runs `Import-RepProgress.ps1` with the certificate. It updates MFP Units to Date, MFP New Groups, MFP New Groups Last 2 Seasons and MFP As Of, and creates any missing rep row with the per-row permissions.
7. If any step fails, it **emails Lynwood** what failed and the end of the log. It also emails when the certificate has less than 30 days left.

**It stops, and emails, instead of loading numbers that look wrong:** MFP sends a web page instead of data; a field in the settings is missing from MFP's answer; the row count doesn't match MFP's total; a fundraiser has no Group ID; the owning users aren't rep codes; a status other than Open, Closed or Canceled appears; the list shrinks by more than 10% from the night before; or a past season's units move by more than 2%. If a change like that is real (for example, a big correction in MFP), run once with `--accept-changes`.

**Read-only in MFP:** the code refuses any request other than GET, apart from POST to the login form and to the two list (grid) requests. Those are listed in the settings, in case MFP's pages use POST to read lists.

**No sales data in GitHub:** the settings, caches, logs and CSVs live in `%LOCALAPPDATA%\RiteBite\MFP Nightly` on the computer and in SharePoint, and the password in Credential Manager. `.gitignore` also blocks `*.csv`, `*.xlsx`, `*.pfx`, `*.cer`, `config.json` and the cache, export and log folders. Local CSVs and logs older than 60 days are deleted.

## Setup on the Windows computer

Use the Windows account that will run the task, and stay in it for every step. The password in Credential Manager and the certificate both belong to that account. Commands go in **PowerShell 7** (Start → "PowerShell 7"), unless a step says otherwise.

### 1. The code

1. On GitHub, open this repository, switch to the branch with this program, then **Code → Download ZIP**.
2. Unzip it to `C:\RiteBite\SalesPlanner`, so that `C:\RiteBite\SalesPlanner\tools\mfp_nightly.py` exists.
3. Unblock the downloaded scripts:

   ```powershell
   Get-ChildItem -Recurse C:\RiteBite\SalesPlanner | Unblock-File
   cd C:\RiteBite\SalesPlanner
   ```

   (Or use `git clone`, then `git checkout` the branch, if Git is installed.)

### 2. Python

1. Install Python 3.12 or newer from **python.org → Downloads → Windows**. If the installer offers **"Add python.exe to PATH"**, tick it. Newer python.org releases may come as the "Python install manager" instead of the classic installer, so the screens may look different. Either way, the `py` command should work afterwards.
2. Check it, and install the three packages the program needs:

   ```powershell
   py --version
   py -m pip install -r tools\requirements-nightly.txt
   py tools\test_mfp_nightly.py
   ```

   The tests should end with `OK`. They use a fake MFP and don't connect to anything.
3. Note Python's full path for Task Scheduler (step 7):

   ```powershell
   py -c "import sys; print(sys.executable)"
   ```

4. **First check, before MFP:** run the calculation on the October 14 pull and compare it with the manual run's file. Download both from the SharePoint folder to Downloads first:

   ```powershell
   py tools\mfp_nightly.py check-offline "$HOME\Downloads\MFP progress 2026-10-14.csv" --season "2027 Spring" --asof 2026-10-14 --expect "$HOME\Downloads\Rep Progress 2027 Spring.csv"
   ```

   It should print **Matches**, plus season totals of **212,213** units for Fall 2025 and **112,124** for Spring 2026.

### 3. Settings file and the MFP password (Windows Credential Manager)

1. Create the settings file. It goes in `%LOCALAPPDATA%\RiteBite\MFP Nightly\config.json`, outside the code folder:

   ```powershell
   py tools\mfp_nightly.py init
   notepad "$env:LOCALAPPDATA\RiteBite\MFP Nightly\config.json"
   ```

2. Fill in `mfp_username`: the MFP login the program will use. A read-only MFP user is best, if MFP can create one (see Open items).
3. Store the password. It's typed, not shown, and saved in Windows Credential Manager, never in a file:

   ```powershell
   py tools\mfp_nightly.py set-password
   ```

   To check it: **Control Panel → Credential Manager → Windows Credentials → Generic Credentials**. You should see an entry for **RiteBite MFP Nightly**; the `keyring` package may show the username as part of its name. When the MFP password changes, run `set-password` again.

### 4. MFP request settings (from the technical notes)

The `mfp` section of the settings says how MFP's pages ask for data. It covers the login form's field names, each list's parameters (paging, all owning users, all statuses, delivery-date filter), and the names of the fields in MFP's answers. Fill in every `FILL IN` from `MFP technical notes.txt`. The fields the October 8 notes already name are filled in: `FundraiserId`, `GroupId`, `DeliveredOn`, `IsPrimary`. In `params`, write `{page}`, `{page_size}`, `{skip}`, `{date_from}` and `{date_to}` where those values go. For example, a Kendo-style list might use:

```json
"params": {"page": "{page}", "pageSize": "{page_size}", "filter": "DeliveredOn~gte~'{date_from}'~and~DeliveredOn~lte~'{date_to}'"}
```

That's only an illustration of the format, not MFP's real parameters. Then check the settings against MFP:

```powershell
py tools\mfp_nightly.py probe
```

`probe` logs in and reads one page of each list, one fundraiser record and one group record. It then prints every field MFP sent and says whether each field in the settings was found. MFP data shows on screen only and isn't saved. Repeat until it says **Settings look right**. Also check `dates_without_offset_are`: compare one delivery date with what MFP's screen shows.

Then do a full export without touching SharePoint, and compare it with the October 14 pull:

```powershell
py tools\mfp_nightly.py run --season "2027 Spring" --no-sharepoint
py tools\mfp_nightly.py compare "$HOME\Downloads\MFP progress 2026-10-14.csv" "$env:LOCALAPPDATA\RiteBite\MFP Nightly\exports\MFP progress <today's date>.csv"
```

Fall 2025 and Spring 2026 should match the October 14 pull almost row for row, and their totals should be 212,213 and 112,124 units. Fall 2026 and Spring 2027 will differ by whatever changed in MFP since October 14.

### 5. Certificate for unattended SharePoint access (needs a Global Administrator once)

The nightly run can't open a browser to sign in, so it signs in as an app with a certificate. This uses a **new, separate app registration**, not the "Rite Bite Sales Planner Setup" app. The setup app has broad permissions to act as whoever signs in. The nightly app gets only **Sites.Selected**, which covers just the two sites granted below, plus **Mail.Send** for the failure email. The setup app can still be deleted after setup, as [01-setup](01-setup.md) suggests. *(The plan above said to put the certificate on the existing app. That also works; this is the narrower option.)*

PnP PowerShell renamed some commands in 2024–2025 ("AzureAD" → "EntraID"). If a command below isn't found, try the older name, or check the PnP PowerShell documentation for your version.

1. Install PnP PowerShell for this Windows account, if it isn't already installed:

   ```powershell
   Install-Module PnP.PowerShell -Scope CurrentUser
   ```

2. Create the app and its certificate. Run this from the data folder, **not** the code folder: it writes `.pfx` and `.cer` files to the current folder.

   ```powershell
   cd "$env:LOCALAPPDATA\RiteBite\MFP Nightly"
   Register-PnPEntraIDApp -ApplicationName "Rite Bite MFP Nightly" `
       -Tenant ritebitefundraising.onmicrosoft.com `
       -Store CurrentUser -ValidYears 2 `
       -SharePointApplicationPermissions "Sites.Selected" `
       -GraphApplicationPermissions "Sites.Selected", "Mail.Send"
   ```

   - A browser or sign-in prompt opens. (If PnP asks for a sign-in option such as `-Interactive` or `-DeviceLogin`, add it.) A **Global Administrator** signs in and clicks **Accept**.
   - Copy the **AzureAppId/ClientId** and the **Certificate Thumbprint** it prints into the settings (`sharepoint.client_id`, `sharepoint.thumbprint`).
   - The certificate is installed in this account's certificate store (Cert:\CurrentUser\My). Move the `.pfx` file to a safe place, such as a password manager, or delete it. Never put it in the code folder or GitHub.

3. Let the app into the two sites only. Sign in as an admin with the setup app, then grant **Full Control** on Sales Planner (needed to set each new Rep Baselines row's permissions) and **Write** on Rite Bite Claude Skills (to save the CSVs):

   ```powershell
   Connect-PnPOnline -Url https://ritebitefundraising.sharepoint.com/sites/SalesPlanner -ClientId <setup app client id> -Interactive
   $app = "<nightly app client id>"
   $p = Grant-PnPEntraIDAppSitePermission -AppId $app -DisplayName "Rite Bite MFP Nightly" -Site https://ritebitefundraising.sharepoint.com/sites/SalesPlanner -Permissions Write
   Set-PnPEntraIDAppSitePermission -Site https://ritebitefundraising.sharepoint.com/sites/SalesPlanner -PermissionId $p.Id -Permissions FullControl
   Grant-PnPEntraIDAppSitePermission -AppId $app -DisplayName "Rite Bite MFP Nightly" -Site https://ritebitefundraising.sharepoint.com/sites/RiteBiteClaudeSkills -Permissions Write
   ```

   As far as I know, Full Control can't be granted directly, which is why it's granted as Write first and then raised. If these commands give you trouble, the simpler (broader) choice is to give the app the **Sites.FullControl.All** application permission in Entra ID instead of Sites.Selected.

4. Optional, recommended: by default, **Mail.Send** lets the app send as any mailbox in the company. Your Exchange admin can limit it to Lynwood's mailbox with an Exchange Online application access policy, or "RBAC for Applications". Microsoft has been moving from the first to the second, so check their current documentation.

5. Test it. This reads the current season, saves a small test file to the Nightly folder and sends a test email:

   ```powershell
   py tools\mfp_nightly.py test-sharepoint
   ```

   Delete `SharePoint test.txt` from the Nightly folder afterwards.

6. **Before the certificate expires** (2 years with `-ValidYears 2`), the program starts emailing a warning 30 days ahead. To renew, create a new certificate and add it to the same app, then put the new thumbprint in the settings. Or repeat step 2 with a new app name and redo step 3.

### 6. First full run, by hand

```powershell
py tools\mfp_nightly.py run
```

Check the log in `%LOCALAPPDATA%\RiteBite\MFP Nightly\logs`, the two CSVs in SharePoint → Nightly, and the **MFP As Of** date on Rep Baselines and in the app.

### 7. Task Scheduler (every evening)

1. Start → **Task Scheduler** → **Create Task…** (not "Create Basic Task").
2. **General**:
   - Name: `MFP nightly export`.
   - **Run whether user is logged on or not**. Leave **"Do not store password"** unticked: the task needs the account's saved credentials to read Credential Manager and the certificate.
   - Configure for: Windows 10 / Windows 11.
3. **Triggers** → New: **Daily**, **9:00 PM**, Enabled.
4. **Actions** → New: **Start a program**.
   - Program/script: the full Python path from step 2.3 (for example `C:\Users\<you>\AppData\Local\Programs\Python\Python312\python.exe`).
   - Add arguments: `"C:\RiteBite\SalesPlanner\tools\mfp_nightly.py" run`
   - Start in: `C:\RiteBite\SalesPlanner`
5. **Conditions**: untick **Start the task only if the computer is on AC power**, and tick **Wake the computer to run this task**.
6. **Settings**: tick **Run task as soon as possible after a scheduled start is missed**, and set **Stop the task if it runs longer than** 2 hours.
7. OK, then enter the Windows password when asked.
8. Test: right-click the task → **Run**. When it finishes, **Last Run Result** should be `(0x0)`; `(0x1)` means a problem, which is also emailed and in the log.

The computer must be on, or asleep, not shut down, at 9 pm. `pwsh` and PnP PowerShell must be installed for this same Windows account.

## Changing things later

- **MFP changes a page:** the run stops and emails. Run `probe`, update the settings, and run `run` by hand.
- **Rules (reps, rollups, merges, placed groups):** `tools/mfp_rules.py`, as before. Download the new code to `C:\RiteBite\SalesPlanner`. The settings and caches are separate, so they stay.
- **A group's owner changed and can't wait a week:** delete `cache\group_owners.json` in the data folder. The next run re-reads every owner, which takes longer that night.

## Open items for Lynwood

- Confirm MFP is fine with an automated nightly login, and whether they can create a read-only user for it.
- Which computer runs it (on in the evening, Python installed).
- `MFP technical notes.txt` wasn't found in the SharePoint folder on October 14, 2026. Its details go into the settings (step 4).

## Where things are

- SharePoint folder: Rite Bite Claude Skills → Documents → Lynwood → Sales Accountibility Sample Planner (pulls, `MFP progress YYYY-MM-DD.csv`, `MFP technical notes.txt`; nightly CSVs in **Nightly**).
- Site: https://ritebitefundraising.sharepoint.com/sites/SalesPlanner (lists: Seasons, Reps, Rep Baselines).
- Code: `tools/mfp_nightly.py` (program), `tools/mfp_nightly_sharepoint.ps1` (SharePoint and email steps), `tools/mfp_nightly.example.json` (settings template), `tools/test_mfp_nightly.py` (tests), `tools/Import-RepProgress.ps1` (now also takes `-Tenant` and `-Thumbprint`).
