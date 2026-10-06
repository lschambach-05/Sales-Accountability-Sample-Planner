# 1. Set up the SharePoint site and lists

**Time:** about 30–60 minutes the first time (rough estimate).
**Who:** someone with Microsoft 365 admin rights, or a manager plus your M365 admin for step 2.

At the end of this step you'll have a private SharePoint site with four lists. Each rep can see and edit only their own rows, and the two managers can see everything.

---

## Step 1: Create the site

1. Go to **SharePoint** (office.com → SharePoint) → **+ Create site**.
2. Choose **Communication site**, not "Team site".
   - A Team site creates a Microsoft 365 group whose members get **Edit** rights. Edit includes "Manage Lists", which lets a rep see every other rep's rows. A Communication site doesn't have this problem.
3. Name it **Sales Planner**. Note the address, for example `https://ritebite.sharepoint.com/sites/SalesPlanner`.
4. Privacy: leave the site's default **Members** group **empty**. The setup script creates its own groups.

## Step 2: One-time sign-in app for PnP PowerShell (needs an M365 admin)

The setup script uses **PnP PowerShell**, a free, widely used Microsoft community tool. Since late 2024, PnP requires each company to register its own sign-in app in Entra ID (formerly Azure AD). This is done once.

On a Windows or Mac computer:

```powershell
# Install PowerShell 7.4 or later first: https://aka.ms/powershell
Install-Module PnP.PowerShell -Scope CurrentUser

Register-PnPEntraIDAppForInteractiveLogin `
    -ApplicationName "Rite Bite Sales Planner Setup" `
    -Tenant ritebite.onmicrosoft.com
```

- Replace `ritebite.onmicrosoft.com` with your tenant's `onmicrosoft.com` name. It's shown in the Microsoft 365 admin center under **Settings → Domains**.
- A browser window opens. A **Global Administrator** must sign in and click **Accept** (admin consent).
- Copy the **Client ID** it prints. You'll need it in step 3.

> This app grants broad delegated SharePoint permissions, but it only acts as the person signed in, and only while the script runs. After setup you can delete it in Entra ID → App registrations. You'd need it again only to re-run the script.

## Step 3: Run the setup script

From this repository folder:

```powershell
./provisioning/Deploy-SalesPlanner.ps1 `
    -SiteUrl  https://ritebite.sharepoint.com/sites/SalesPlanner `
    -ClientId <client id from step 2> `
    -ManagerEmails lynwood@ritebitefundraising.com, <second manager email> `
    -RepEmails <rep1 email>, <rep2 email>, <rep3 email>, <rep4 email>, <rep5 email>, <rep6 email>
```

The script:

| Creates | Purpose | Who can see it |
|---|---|---|
| Group **Sales Planner Managers** (Full Control) | You + the second manager | n/a |
| Group **Sales Planner Reps** (Contribute) | The 6 reps | n/a |
| **Seasons** list | Season name, start date (Jan 1 or Jul 1), number of weeks, sales-days goal, which season is current | Managers edit; reps read only |
| **Reps** list | Roster: name, MFP Owning User code, active? | Managers only |
| **Program Plans** list | Each rep's pre-season plan per program, plus post-season actuals | Each rep: only their own rows. Managers: all |
| **Weekly Check-ins** list | Each rep's Friday numbers | Each rep: only their own rows. Managers: all |

It's safe to run again (for example, to add a new rep). Anything that already exists is skipped.

**If the script stops with an error:** copy the red error text and send it to me, or to whoever is helping. The script couldn't be run against a real tenant before handoff, so a first-run error is possible.

## Step 4: Finish the lists by hand (5 minutes)

1. **Reps** list: for each rep, replace the email in *Rep Name* with their name and fill in their **MFP Owning User Code** (for example BLS, KJS).
2. **Seasons** list:
   - The script adds **2027 Spring** (Jan 1, 2027, 26 weeks) and **2027 Fall** (Jul 1, 2027, 27 weeks). Seasons run Jan 1 – Jun 30 and Jul 1 – Dec 31, matching the MFP numbers. Weeks = the number of Fridays in the season.
   - Fill in the **Sales Days Goal** for each season.
   - Tick **Current Season** on the one in progress. To pilot it now, add a **2026 Fall** row with its real start date.

## Step 5: Test the privacy (don't skip)

1. Ask one rep (or use a test account in the Reps group) to open the site and add a test row to **Weekly Check-ins**.
2. Ask a second rep to open **Weekly Check-ins**. **They should not see the first rep's row.**
3. You (manager) should see both rows, and the **By Rep** view should group them.
4. Delete the test rows.

If a rep can see other people's rows, they are almost certainly in a group with Edit or Full Control. Check **Site settings → Site permissions** and make sure reps are *only* in "Sales Planner Reps".

## Next

- [2. Data model and formulas](02-data-model.md): what each column means
- [3. Power App](03-power-app.md): the phone-friendly app reps actually use
- [4. Friday reminder flow](04-friday-reminder-flow.md): automatic nudges for missed check-ins
