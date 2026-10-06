<#
.SYNOPSIS
    Builds the Rite Bite Sales Planner on a SharePoint Online site.

.DESCRIPTION
    Creates (or updates, if they already exist):
      * Two SharePoint groups: "Sales Planner Managers" (Full Control) and "Sales Planner Reps" (Contribute)
      * Four lists:
          Seasons            - managers maintain, reps read only
          Reps               - managers only (roster used by the team view and the Friday reminder)
          Program Plans      - one row per rep / season / program; plan inputs + post-season actuals
          Weekly Check-ins   - one row per rep / week
      * Item-level security on Program Plans and Weekly Check-ins so each rep can only
        read and edit rows they created. Managers (Full Control) see everything.
      * Manager views ("By Rep") with totals.
      * Seed rows for the 2027 Spring and 2027 Fall seasons (dates from the original workbook).

    Safe to re-run: anything that already exists is left alone.

.PARAMETER SiteUrl
    The SharePoint site to build on, e.g. https://ritebite.sharepoint.com/sites/SalesPlanner
    Use a Communication site (no Microsoft 365 group) - see docs/01-setup.md.

.PARAMETER ClientId
    The Entra ID app (client) id used by PnP PowerShell to sign in - see docs/01-setup.md.

.PARAMETER ManagerEmails
    Email addresses of the people who see the team view.

.PARAMETER RepEmails
    Email addresses of the sales reps.

.EXAMPLE
    ./Deploy-SalesPlanner.ps1 -SiteUrl https://ritebite.sharepoint.com/sites/SalesPlanner `
        -ClientId 00000000-0000-0000-0000-000000000000 `
        -ManagerEmails lynwood@ritebitefundraising.com, manager2@ritebitefundraising.com `
        -RepEmails rep1@ritebitefundraising.com, rep2@ritebitefundraising.com
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string]   $SiteUrl,
    [Parameter(Mandatory)] [string]   $ClientId,
    [Parameter(Mandatory)] [string[]] $ManagerEmails,
    [string[]] $RepEmails = @(),
    [string[]] $Programs = @(
        'Butter Braid Pastry',
        'Combo',
        'Wooden Spoon CD',
        'Joyful Tradition',
        'Bella Napoli',
        'Croissant Crowns',
        'Batavia Music Buffs'
    )
)

$ErrorActionPreference = 'Stop'

$ManagersGroup = 'Sales Planner Managers'
$RepsGroup     = 'Sales Planner Reps'

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

function Write-Step([string] $Message) {
    Write-Host "`n== $Message" -ForegroundColor Cyan
}

function Get-OrNewList([string] $Title, [string] $Url) {
    $list = Get-PnPList -Identity $Title -ErrorAction SilentlyContinue
    if (-not $list) {
        Write-Host "   creating list '$Title'"
        $list = New-PnPList -Title $Title -Url "Lists/$Url" -Template GenericList -OnQuickLaunch
    }
    else {
        Write-Host "   list '$Title' already exists"
    }
    return $list
}

# Adds a field from schema XML. The field is created with DisplayName = InternalName so the
# internal name is exactly what we asked for, then renamed to the friendly display name at the
# end (Rename-Fields). Calculated formulas therefore reference internal names when created;
# SharePoint keeps them pointing at the right columns after the rename.
function Add-FieldXml([string] $List, [string] $InternalName, [string] $Xml) {
    if (Get-PnPField -List $List -Identity $InternalName -ErrorAction SilentlyContinue) {
        return
    }
    Add-PnPFieldFromXml -List $List -FieldXml $Xml | Out-Null
    Write-Host "   + $List / $InternalName"
}

function Add-NumberField([string] $List, [string] $Name, [int] $Decimals = 0, [switch] $Percent, [switch] $Required) {
    $pct = if ($Percent) { 'Percentage="TRUE"' } else { '' }
    $req = if ($Required) { 'TRUE' } else { 'FALSE' }
    Add-FieldXml $List $Name "<Field Type=""Number"" Name=""$Name"" StaticName=""$Name"" DisplayName=""$Name"" Min=""0"" Decimals=""$Decimals"" $pct Required=""$req"" />"
}

function Add-CalcField([string] $List, [string] $Name, [string] $Formula, [string[]] $Refs, [int] $Decimals = 0, [switch] $Percent) {
    $pct  = if ($Percent) { 'Percentage="TRUE"' } else { '' }
    $refs = ($Refs | ForEach-Object { "<FieldRef Name=""$_"" />" }) -join ''
    $f    = [System.Security.SecurityElement]::Escape($Formula)
    Add-FieldXml $List $Name "<Field Type=""Calculated"" Name=""$Name"" StaticName=""$Name"" DisplayName=""$Name"" ResultType=""Number"" Decimals=""$Decimals"" $pct ReadOnly=""TRUE""><Formula>$f</Formula><FieldRefs>$refs</FieldRefs></Field>"
}

function Rename-Fields([string] $List, [hashtable] $Names) {
    foreach ($internal in $Names.Keys) {
        Set-PnPField -List $List -Identity $internal -Values @{ Title = $Names[$internal] } | Out-Null
    }
}

function Set-ItemLevelSecurity([string] $Title) {
    # Each user reads and edits only the items they created. Anyone with "Manage Lists"
    # (Full Control, Edit, Design) bypasses this and sees everything.
    Set-PnPList -Identity $Title -ReadSecurity AllUsersReadAccessOnItemsTheyCreate -WriteSecurity WriteOnlyMyItems | Out-Null
    Write-Host "   item-level security ON for '$Title'"
}

# Gives a list its own permissions (copied from the site) and changes what the reps group gets on it.
# Only runs the first time, so re-running the script never undoes manual permission changes.
function Set-RepsAccess([string] $Title, [string] $AddRole) {
    $list = Get-PnPList -Identity $Title -Includes HasUniqueRoleAssignments
    if ($list.HasUniqueRoleAssignments) { return }
    Set-PnPList -Identity $Title -BreakRoleInheritance -CopyRoleAssignments | Out-Null
    $p = @{ Identity = $Title; Group = $RepsGroup; RemoveRole = 'Contribute' }
    if ($AddRole) { $p.AddRole = $AddRole }
    Set-PnPListPermission @p | Out-Null
    Write-Host "   '$Title': reps now have '$(if ($AddRole) { $AddRole } else { 'no access' })'"
}

function Add-ViewIfMissing([string] $List, [string] $Title, [string[]] $Fields, [string] $Query, [string] $Aggregations) {
    if (Get-PnPView -List $List -Identity $Title -ErrorAction SilentlyContinue) { return }
    $params = @{ List = $List; Title = $Title; Fields = $Fields; Query = $Query; RowLimit = 500 }
    if ($Aggregations) { $params.Aggregations = $Aggregations }
    Add-PnPView @params | Out-Null
    Write-Host "   + view '$List / $Title'"
}

# ---------------------------------------------------------------------------
# Connect
# ---------------------------------------------------------------------------

Write-Step "Connecting to $SiteUrl"
Connect-PnPOnline -Url $SiteUrl -ClientId $ClientId -Interactive

# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------

Write-Step 'Groups and permissions'

foreach ($g in @(@{ Name = $ManagersGroup; Role = 'Full Control' }, @{ Name = $RepsGroup; Role = 'Contribute' })) {
    if (-not (Get-PnPGroup -Identity $g.Name -ErrorAction SilentlyContinue)) {
        New-PnPGroup -Title $g.Name | Out-Null
        Set-PnPGroupPermissions -Identity $g.Name -AddRole $g.Role | Out-Null
        Write-Host "   created group '$($g.Name)' ($($g.Role))"
    }
}

foreach ($email in $ManagerEmails) { Add-PnPGroupMember -Group $ManagersGroup -LoginName $email }
foreach ($email in $RepEmails)     { Add-PnPGroupMember -Group $RepsGroup     -LoginName $email }

# Reps must NOT be in the site's default Members group: that group has "Edit", which includes
# "Manage Lists", which lets a rep see every other rep's rows.
$members = Get-PnPGroup -AssociatedMemberGroup
$memberLogins = @(Get-PnPGroupMember -Group $members | Where-Object { $_.Email } | ForEach-Object { $_.Email.ToLower() })
foreach ($email in $RepEmails) {
    if ($memberLogins -contains $email.ToLower()) {
        Write-Warning "$email is in '$($members.Title)' (Edit). Remove them from that group or they will see every rep's data."
    }
}

# ---------------------------------------------------------------------------
# Seasons
# ---------------------------------------------------------------------------

Write-Step 'Seasons list'
Get-OrNewList 'Seasons' 'Seasons' | Out-Null
Add-FieldXml 'Seasons' 'SeasonStart'   '<Field Type="DateTime" Name="SeasonStart" StaticName="SeasonStart" DisplayName="SeasonStart" Format="DateOnly" Required="TRUE" />'
Add-FieldXml 'Seasons' 'Weeks'         '<Field Type="Number" Name="Weeks" StaticName="Weeks" DisplayName="Weeks" Min="1" Max="52" Decimals="0" Required="TRUE"><Default>20</Default></Field>'
Add-FieldXml 'Seasons' 'SalesDaysGoal' '<Field Type="Number" Name="SalesDaysGoal" StaticName="SalesDaysGoal" DisplayName="SalesDaysGoal" Min="0" Decimals="0" />'
Add-FieldXml 'Seasons' 'CurrentSeason' '<Field Type="Boolean" Name="CurrentSeason" StaticName="CurrentSeason" DisplayName="CurrentSeason"><Default>0</Default></Field>'
# Which rule was used to count retained groups/units for this season, so seasons counted
# under different rules aren't compared as if they were the same. Add choices here to change the rule.
Add-FieldXml 'Seasons' 'RetentionRule' ('<Field Type="Choice" Name="RetentionRule" StaticName="RetentionRule" DisplayName="RetentionRule" Format="Dropdown" Required="TRUE">' +
    '<Default>Any program, either season last year</Default><CHOICES>' +
    '<CHOICE>Any program, either season last year</CHOICE>' +
    '<CHOICE>Any program, same season last year</CHOICE>' +
    '<CHOICE>Same program, same season last year</CHOICE>' +
    '</CHOICES></Field>')
Rename-Fields 'Seasons' @{
    Title         = 'Season'
    SeasonStart   = 'Season Start'
    Weeks         = 'Weeks'
    SalesDaysGoal = 'Sales Days Goal'
    CurrentSeason = 'Current Season'
    RetentionRule = 'Retention Rule'
}
Set-PnPView -List 'Seasons' -Identity 'All Items' -Fields 'LinkTitle', 'SeasonStart', 'Weeks', 'SalesDaysGoal', 'CurrentSeason', 'RetentionRule' | Out-Null

if (-not (Get-PnPListItem -List 'Seasons' -PageSize 50)) {
    # Spring = Jan 1 - Jun 30, Fall = Jul 1 - Dec 31 (same split as the MFP delivery-date seasons).
    # Weeks = number of Fridays (check-in days) in the season.
    Add-PnPListItem -List 'Seasons' -Values @{ Title = '2027 Spring'; SeasonStart = [datetime]'2027-01-01'; Weeks = 26 } | Out-Null
    Add-PnPListItem -List 'Seasons' -Values @{ Title = '2027 Fall';   SeasonStart = [datetime]'2027-07-01'; Weeks = 27 } | Out-Null
    Write-Host '   seeded 2027 Spring and 2027 Fall'
}

# Reps may read seasons but not change them.
Set-RepsAccess 'Seasons' 'Read'

$seasonsId = (Get-PnPList -Identity 'Seasons').Id

# ---------------------------------------------------------------------------
# Reps (manager-only roster)
# ---------------------------------------------------------------------------

Write-Step 'Reps list'
Get-OrNewList 'Reps' 'Reps' | Out-Null
Add-FieldXml 'Reps' 'RepUser' '<Field Type="User" Name="RepUser" StaticName="RepUser" DisplayName="RepUser" UserSelectionMode="PeopleOnly" Required="TRUE" />'
Add-FieldXml 'Reps' 'MFPCode' '<Field Type="Text" Name="MFPCode" StaticName="MFPCode" DisplayName="MFPCode" MaxLength="20" />'
Add-FieldXml 'Reps' 'Active'  '<Field Type="Boolean" Name="Active" StaticName="Active" DisplayName="Active"><Default>1</Default></Field>'
Rename-Fields 'Reps' @{
    Title   = 'Rep Name'
    RepUser = 'Rep'
    MFPCode = 'MFP Owning User Code'
    Active  = 'Active'
}
Set-PnPView -List 'Reps' -Identity 'All Items' -Fields 'LinkTitle', 'RepUser', 'MFPCode', 'Active' | Out-Null

$existingReps = @(Get-PnPListItem -List 'Reps' -PageSize 100 | Where-Object { $_['RepUser'] } | ForEach-Object { $_['RepUser'].Email.ToLower() })
foreach ($email in $RepEmails) {
    if ($existingReps -notcontains $email.ToLower()) {
        Add-PnPListItem -List 'Reps' -Values @{ Title = $email; RepUser = $email; Active = $true } | Out-Null
        Write-Host "   + rep $email (set their name and MFP code in the Reps list)"
    }
}

Set-RepsAccess 'Reps' $null

# ---------------------------------------------------------------------------
# Program Plans (plan inputs + post-season actuals, one row per rep/season/program)
# ---------------------------------------------------------------------------

Write-Step 'Program Plans list'
$PP = 'Program Plans'
Get-OrNewList $PP 'ProgramPlans' | Out-Null
Set-PnPField -List $PP -Identity 'Title' -Values @{ Required = $false } | Out-Null

$choices = ($Programs | ForEach-Object { '<CHOICE>' + [System.Security.SecurityElement]::Escape($_) + '</CHOICE>' }) -join ''
Add-FieldXml $PP 'Season'  "<Field Type=""Lookup"" Name=""Season"" StaticName=""Season"" DisplayName=""Season"" List=""{$seasonsId}"" ShowField=""Title"" Required=""TRUE"" />"
Add-FieldXml $PP 'Program' "<Field Type=""Choice"" Name=""Program"" StaticName=""Program"" DisplayName=""Program"" Format=""Dropdown"" Required=""TRUE""><CHOICES>$choices</CHOICES></Field>"

# Pre-season plan inputs (yellow cells on the old Goals tabs).
# "Prior year" units/groups = the same season one year earlier (a 2026 Fall plan uses 2025 Fall).
# Which groups count as "retained" follows the season's Retention Rule (see Seasons list).
Add-NumberField $PP 'GoalUnits'
Add-NumberField $PP 'PriorUnits'
Add-NumberField $PP 'PriorGroups'
Add-NumberField $PP 'RetentionPct'         -Decimals 1 -Percent
Add-NumberField $PP 'DirectCallsGoal'
Add-NumberField $PP 'DirectClosePct'       -Decimals 1 -Percent
Add-NumberField $PP 'IndirectContactsGoal'
Add-NumberField $PP 'IndirectClosePct'     -Decimals 1 -Percent
Add-NumberField $PP 'AvgUnitsPerGroup'     -Decimals 1

# Plan math (blue cells). Formulas are written out in full rather than chaining calculated columns.
$retained = '[PriorUnits]*[RetentionPct]'
$newGroups = '([DirectCallsGoal]*[DirectClosePct]+[IndirectContactsGoal]*[IndirectClosePct])'
$projected = "($retained+$newGroups*[AvgUnitsPerGroup])"
Add-CalcField $PP 'PlanRetainedUnits'  "=$retained"                               @('PriorUnits', 'RetentionPct')
Add-CalcField $PP 'PlanDirectGroups'   '=[DirectCallsGoal]*[DirectClosePct]'      @('DirectCallsGoal', 'DirectClosePct') -Decimals 1
Add-CalcField $PP 'PlanIndirectGroups' '=[IndirectContactsGoal]*[IndirectClosePct]' @('IndirectContactsGoal', 'IndirectClosePct') -Decimals 1
Add-CalcField $PP 'PlanNewGroups'      "=$newGroups"                              @('DirectCallsGoal', 'DirectClosePct', 'IndirectContactsGoal', 'IndirectClosePct') -Decimals 1
Add-CalcField $PP 'PlanNewUnits'       "=$newGroups*[AvgUnitsPerGroup]"           @('DirectCallsGoal', 'DirectClosePct', 'IndirectContactsGoal', 'IndirectClosePct', 'AvgUnitsPerGroup')
Add-CalcField $PP 'PlanTotalUnits'     "=$projected"                              @('PriorUnits', 'RetentionPct', 'DirectCallsGoal', 'DirectClosePct', 'IndirectContactsGoal', 'IndirectClosePct', 'AvgUnitsPerGroup')
Add-CalcField $PP 'PlanCoverage'       "=IF([GoalUnits]=0,0,$projected/[GoalUnits])" @('GoalUnits', 'PriorUnits', 'RetentionPct', 'DirectCallsGoal', 'DirectClosePct', 'IndirectContactsGoal', 'IndirectClosePct', 'AvgUnitsPerGroup') -Decimals 1 -Percent

# Post-season actuals (old Goals tabs rows 22-35)
Add-NumberField $PP 'ActTotalUnits'
Add-NumberField $PP 'ActRetainedUnits'
Add-NumberField $PP 'ActRetainedGroups'
Add-NumberField $PP 'ActDirectCalls'
Add-NumberField $PP 'ActDirectBookings'
Add-NumberField $PP 'ActIndirectContacts'
Add-NumberField $PP 'ActIndirectBookings'

Add-CalcField $PP 'ActAttainment'       '=IF([GoalUnits]=0,0,[ActTotalUnits]/[GoalUnits])'                 @('GoalUnits', 'ActTotalUnits') -Decimals 1 -Percent
Add-CalcField $PP 'ActRetentionPct'     '=IF([PriorUnits]=0,0,[ActRetainedUnits]/[PriorUnits])'            @('PriorUnits', 'ActRetainedUnits') -Decimals 1 -Percent
Add-CalcField $PP 'ActGroupRetentionPct' '=IF([PriorGroups]=0,0,[ActRetainedGroups]/[PriorGroups])'          @('PriorGroups', 'ActRetainedGroups') -Decimals 1 -Percent
Add-CalcField $PP 'ActNewUnits'         '=[ActTotalUnits]-[ActRetainedUnits]'                              @('ActTotalUnits', 'ActRetainedUnits')
Add-CalcField $PP 'ActNewGroups'        '=[ActDirectBookings]+[ActIndirectBookings]'                       @('ActDirectBookings', 'ActIndirectBookings')
Add-CalcField $PP 'ActDirectClosePct'   '=IF([ActDirectCalls]=0,0,[ActDirectBookings]/[ActDirectCalls])'   @('ActDirectCalls', 'ActDirectBookings') -Decimals 1 -Percent
Add-CalcField $PP 'ActIndirectClosePct' '=IF([ActIndirectContacts]=0,0,[ActIndirectBookings]/[ActIndirectContacts])' @('ActIndirectContacts', 'ActIndirectBookings') -Decimals 1 -Percent
Add-CalcField $PP 'ActNewGroupAvg'      '=IF(([ActDirectBookings]+[ActIndirectBookings])=0,0,([ActTotalUnits]-[ActRetainedUnits])/([ActDirectBookings]+[ActIndirectBookings]))' @('ActTotalUnits', 'ActRetainedUnits', 'ActDirectBookings', 'ActIndirectBookings') -Decimals 1
Add-CalcField $PP 'ActRetainedGroupAvg' '=IF([ActRetainedGroups]=0,0,[ActRetainedUnits]/[ActRetainedGroups])' @('ActRetainedUnits', 'ActRetainedGroups') -Decimals 1

Rename-Fields $PP @{
    Title                = 'Notes'
    GoalUnits            = 'Sales Goal Units'
    PriorUnits           = 'Prior Year Units'
    PriorGroups          = 'Prior Year Groups'
    RetentionPct         = 'Retention %'
    DirectCallsGoal      = 'Direct Calls Goal'
    DirectClosePct       = 'Direct Close %'
    IndirectContactsGoal = 'Indirect Contacts Goal'
    IndirectClosePct     = 'Indirect Close %'
    AvgUnitsPerGroup     = 'Avg Units per New Group'
    PlanRetainedUnits    = 'Plan - Retained Units'
    PlanDirectGroups     = 'Plan - Direct New Groups'
    PlanIndirectGroups   = 'Plan - Indirect New Groups'
    PlanNewGroups        = 'Plan - New Groups'
    PlanNewUnits         = 'Plan - New Units'
    PlanTotalUnits       = 'Plan - Projected Total Units'
    PlanCoverage         = 'Plan - % of Goal Covered'
    ActTotalUnits        = 'Actual - Total Units'
    ActRetainedUnits     = 'Actual - Retained Units (ran last year)'
    ActRetainedGroups    = 'Actual - Retained Groups (ran last year)'
    ActDirectCalls       = 'Actual - Direct Calls'
    ActDirectBookings    = 'Actual - Direct Bookings'
    ActIndirectContacts  = 'Actual - Indirect Contacts'
    ActIndirectBookings  = 'Actual - Indirect Bookings'
    ActAttainment        = 'Actual - Attainment %'
    ActRetentionPct      = 'Actual - Unit Retention %'
    ActGroupRetentionPct = 'Actual - Group Retention %'
    ActNewUnits          = 'Actual - New Units'
    ActNewGroups         = 'Actual - New Groups'
    ActDirectClosePct    = 'Actual - Direct Close %'
    ActIndirectClosePct  = 'Actual - Indirect Close %'
    ActNewGroupAvg       = 'Actual - Avg Units per New Group'
    ActRetainedGroupAvg  = 'Actual - Avg Units per Retained Group'
}

$planFields = 'Season', 'Program', 'GoalUnits', 'PriorUnits', 'PriorGroups', 'RetentionPct', 'DirectCallsGoal', 'DirectClosePct',
              'IndirectContactsGoal', 'IndirectClosePct', 'AvgUnitsPerGroup', 'PlanNewGroups', 'PlanTotalUnits', 'PlanCoverage'
Set-PnPView -List $PP -Identity 'All Items' -Fields $planFields | Out-Null
Add-ViewIfMissing $PP 'By Rep' (@('Author') + $planFields) `
    '<GroupBy Collapse="FALSE"><FieldRef Name="Author" /><FieldRef Name="Season" /></GroupBy><OrderBy><FieldRef Name="Program" /></OrderBy>' `
    '<FieldRef Name="GoalUnits" Type="SUM" /><FieldRef Name="DirectCallsGoal" Type="SUM" /><FieldRef Name="IndirectContactsGoal" Type="SUM" />'
Add-ViewIfMissing $PP 'Plan vs Actual' @('Author', 'Season', 'Program', 'GoalUnits', 'PlanTotalUnits', 'ActTotalUnits', 'ActAttainment',
                                         'RetentionPct', 'ActRetentionPct', 'PriorGroups', 'ActRetainedGroups', 'ActGroupRetentionPct', 'DirectClosePct', 'ActDirectClosePct', 'IndirectClosePct', 'ActIndirectClosePct') `
    '<GroupBy Collapse="FALSE"><FieldRef Name="Season" /></GroupBy><OrderBy><FieldRef Name="Author" /><FieldRef Name="Program" /></OrderBy>' `
    '<FieldRef Name="GoalUnits" Type="SUM" /><FieldRef Name="ActTotalUnits" Type="SUM" />'

Set-ItemLevelSecurity $PP

# ---------------------------------------------------------------------------
# Weekly Check-ins (one row per rep per week)
# ---------------------------------------------------------------------------

Write-Step 'Weekly Check-ins list'
$WC = 'Weekly Check-ins'
Get-OrNewList $WC 'WeeklyCheckins' | Out-Null
Set-PnPField -List $WC -Identity 'Title' -Values @{ Required = $false } | Out-Null

Add-FieldXml $WC 'Season'     "<Field Type=""Lookup"" Name=""Season"" StaticName=""Season"" DisplayName=""Season"" List=""{$seasonsId}"" ShowField=""Title"" Required=""TRUE"" />"
Add-FieldXml $WC 'WeekEnding' '<Field Type="DateTime" Name="WeekEnding" StaticName="WeekEnding" DisplayName="WeekEnding" Format="DateOnly" Required="TRUE" />'
Add-NumberField $WC 'DirectCalls'      -Required
Add-NumberField $WC 'IndirectContacts' -Required
Add-FieldXml $WC 'SalesDays' '<Field Type="Number" Name="SalesDays" StaticName="SalesDays" DisplayName="SalesDays" Min="0" Max="7" Decimals="0" Required="TRUE" />'
Add-NumberField $WC 'DirectBookings'
Add-NumberField $WC 'IndirectBookings'
Add-NumberField $WC 'MFPUnitsToDate'
Add-FieldXml $WC 'WeekNotes' '<Field Type="Note" Name="WeekNotes" StaticName="WeekNotes" DisplayName="WeekNotes" NumLines="4" RichText="FALSE" />'

Rename-Fields $WC @{
    WeekEnding       = 'Week Ending (Friday)'
    DirectCalls      = 'Direct Calls'
    IndirectContacts = 'Indirect Contacts'
    SalesDays        = 'Sales Days'
    DirectBookings   = 'New Groups Booked - Direct'
    IndirectBookings = 'New Groups Booked - Indirect'
    MFPUnitsToDate   = 'MFP Units Season-to-Date'
    WeekNotes        = 'Notes'
}

$wcFields = 'Season', 'WeekEnding', 'DirectCalls', 'IndirectContacts', 'SalesDays', 'DirectBookings', 'IndirectBookings', 'MFPUnitsToDate', 'WeekNotes'
Set-PnPView -List $WC -Identity 'All Items' -Fields $wcFields | Out-Null
Add-ViewIfMissing $WC 'By Rep' (@('Author') + $wcFields) `
    '<GroupBy Collapse="FALSE"><FieldRef Name="Author" /><FieldRef Name="Season" /></GroupBy><OrderBy><FieldRef Name="WeekEnding" Ascending="FALSE" /></OrderBy>' `
    '<FieldRef Name="DirectCalls" Type="SUM" /><FieldRef Name="IndirectContacts" Type="SUM" /><FieldRef Name="SalesDays" Type="SUM" /><FieldRef Name="DirectBookings" Type="SUM" /><FieldRef Name="IndirectBookings" Type="SUM" />'

Set-ItemLevelSecurity $WC

Write-Step 'Done'
Write-Host @"
Next steps (see docs/):
  1. Open the Reps list and fill in each rep's name and MFP Owning User Code.
  2. Open the Seasons list, set the Sales Days Goal, and tick 'Current Season' on the season in progress.
  3. Sign in as (or ask) one rep to confirm they can only see their own rows.
  4. Build the Power App (docs/03-power-app.md) and the Friday reminder flow (docs/04-friday-reminder-flow.md).
"@
