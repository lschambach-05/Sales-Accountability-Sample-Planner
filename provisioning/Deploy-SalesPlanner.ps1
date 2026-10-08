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
          Daily Activity     - one row per rep / selling day
      * Item-level security on Program Plans and Daily Activity so each rep can only
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
    # Extra calls/contacts on top of what the math says is needed (0.10 = 10%).
    [double]   $CallBuffer = 0.10,
    # Since October 2026 there is one kind of activity, "Sales Calls" (the Direct* columns). The
    # Indirect* (gatekeeper) columns stay in the lists, unused: the app saves them as 0 and plans
    # put 100% of new groups on sales calls. These labels only name those leftover columns.
    [string]   $DirectLabel = 'In-Person',
    [string]   $IndirectLabel = 'Gatekeeper',
    [string[]] $Programs = @(
        'All Programs',      # the app saves every plan as All Programs; the rest are kept for a per-program split later
        'Butter Braid Pastry',
        'Combo',
        'Wooden Spoon CD',
        'Joyful Tradition',
        'Bella Napoli',
        'Croissant Crowns'
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

# Pre-season plan inputs. The plan works BACKWARD from the goal:
#   goal -> minus retained units -> new units needed -> new groups needed
#   -> split direct / indirect -> divide by close rates -> calls & contacts needed -> + call buffer (10%).
# "Prior year" units/groups = the same season one year earlier (a 2027 Spring plan uses 2026 Spring).
# Which groups count as "retained" follows the season's Retention Rule (see Seasons list).
Add-NumberField $PP 'PriorUnits'
Add-NumberField $PP 'PriorGroups'
Add-NumberField $PP 'GrowthPct'            -Decimals 1 -Percent
Add-NumberField $PP 'GoalOverride'
Add-NumberField $PP 'RetentionPct'         -Decimals 1 -Percent
# For reference only (the math uses unit retention): share of last year's groups expected back.
Add-NumberField $PP 'GroupRetentionPct'    -Decimals 1 -Percent
Add-NumberField $PP 'AvgUnitsPerGroup'     -Decimals 1
Add-NumberField $PP 'DirectSharePct'       -Decimals 1 -Percent
Add-NumberField $PP 'DirectClosePct'       -Decimals 1 -Percent
Add-NumberField $PP 'IndirectClosePct'     -Decimals 1 -Percent

# Plan math. Each formula is written out in full rather than chaining calculated columns.
$buffer   = '(1+' + $CallBuffer.ToString([System.Globalization.CultureInfo]::InvariantCulture) + ')'
$goal     = 'IF([GoalOverride]>0,[GoalOverride],ROUND([PriorUnits]*(1+[GrowthPct]),0))'
$retained = 'ROUND([PriorUnits]*[RetentionPct],0)'
$newUnits = "MAX(0,$goal-$retained)"
$newGrps  = "IF([AvgUnitsPerGroup]=0,0,$newUnits/[AvgUnitsPerGroup])"
$dirNeed  = "IF([DirectClosePct]=0,0,$newGrps*[DirectSharePct]/[DirectClosePct])"
$indNeed  = "IF([IndirectClosePct]=0,0,$newGrps*(1-[DirectSharePct])/[IndirectClosePct])"
$goalRefs = @('GoalOverride', 'PriorUnits', 'GrowthPct')
$newRefs  = $goalRefs + @('RetentionPct', 'AvgUnitsPerGroup')
Add-CalcField $PP 'GoalUnits'          "=$goal"                     $goalRefs
Add-CalcField $PP 'PlanRetainedUnits'  "=$retained"                 @('PriorUnits', 'RetentionPct')
Add-CalcField $PP 'PlanNewUnits'       "=$newUnits"                 ($goalRefs + @('RetentionPct'))
Add-CalcField $PP 'PlanNewGroups'      "=$newGrps"                  $newRefs -Decimals 1
Add-CalcField $PP 'DirectCallsNeeded'  "=ROUNDUP($dirNeed,0)"       ($newRefs + @('DirectSharePct', 'DirectClosePct'))
Add-CalcField $PP 'DirectCallsTarget'  "=ROUNDUP($dirNeed*$buffer,0)" ($newRefs + @('DirectSharePct', 'DirectClosePct'))
Add-CalcField $PP 'IndirectNeeded'     "=ROUNDUP($indNeed,0)"       ($newRefs + @('DirectSharePct', 'IndirectClosePct'))
Add-CalcField $PP 'IndirectTarget'     "=ROUNDUP($indNeed*$buffer,0)" ($newRefs + @('DirectSharePct', 'IndirectClosePct'))

# Post-season actuals, per program, from the yearly MFP pull (old Goals tabs rows 22-35).
# Actual close rates are NOT per program: they come from the Daily Activity log over a rolling
# 12 months (calls and bookings across both seasons), which the app shows per rep.
Add-NumberField $PP 'ActTotalUnits'
Add-NumberField $PP 'ActTotalGroups'
Add-NumberField $PP 'ActRetainedUnits'
Add-NumberField $PP 'ActRetainedGroups'

Add-CalcField $PP 'ActAttainment'       "=IF($goal=0,0,[ActTotalUnits]/$goal)"                             ($goalRefs + @('ActTotalUnits')) -Decimals 1 -Percent
Add-CalcField $PP 'ActRetentionPct'     '=IF([PriorUnits]=0,0,[ActRetainedUnits]/[PriorUnits])'            @('PriorUnits', 'ActRetainedUnits') -Decimals 1 -Percent
Add-CalcField $PP 'ActGroupRetentionPct' '=IF([PriorGroups]=0,0,[ActRetainedGroups]/[PriorGroups])'          @('PriorGroups', 'ActRetainedGroups') -Decimals 1 -Percent
Add-CalcField $PP 'ActNewUnits'         '=[ActTotalUnits]-[ActRetainedUnits]'                              @('ActTotalUnits', 'ActRetainedUnits')
Add-CalcField $PP 'ActNewGroups'        '=[ActTotalGroups]-[ActRetainedGroups]'                            @('ActTotalGroups', 'ActRetainedGroups')
Add-CalcField $PP 'ActNewGroupAvg'      '=IF(([ActTotalGroups]-[ActRetainedGroups])=0,0,([ActTotalUnits]-[ActRetainedUnits])/([ActTotalGroups]-[ActRetainedGroups]))' @('ActTotalUnits', 'ActRetainedUnits', 'ActTotalGroups', 'ActRetainedGroups') -Decimals 1
Add-CalcField $PP 'ActRetainedGroupAvg' '=IF([ActRetainedGroups]=0,0,[ActRetainedUnits]/[ActRetainedGroups])' @('ActRetainedUnits', 'ActRetainedGroups') -Decimals 1

$bufferLabel = [math]::Round($CallBuffer * 100).ToString() + '%'
Rename-Fields $PP @{
    Title                = 'Notes'
    PriorUnits           = 'Prior Year Units'
    PriorGroups          = 'Prior Year Groups'
    GoalOverride         = 'Unit Goal'
    GrowthPct            = 'Growth % (if no Unit Goal)'
    RetentionPct         = 'Unit Retention %'
    GroupRetentionPct    = 'Group Retention %'
    AvgUnitsPerGroup     = 'Avg Units per Group'
    DirectSharePct       = "% of New Groups from $DirectLabel"
    DirectClosePct       = 'Sales Call Close %'
    IndirectClosePct     = "$IndirectLabel Close %"
    GoalUnits            = 'Sales Goal Units'
    PlanRetainedUnits    = 'Plan - Retained Units'
    PlanNewUnits         = 'Plan - New Units Needed'
    PlanNewGroups        = 'Plan - New Groups Needed'
    DirectCallsNeeded    = 'Sales Calls Needed'
    DirectCallsTarget    = 'Sales Calls Target'     # needed + call buffer ($bufferLabel)
    IndirectNeeded       = "$IndirectLabel Contacts Needed"
    IndirectTarget       = "$IndirectLabel Contacts Target"  # needed + call buffer ($bufferLabel)
    ActTotalUnits        = 'Actual - Total Units'
    ActTotalGroups       = 'Actual - Total Groups'
    ActRetainedUnits     = 'Actual - Retained Units (ran last year)'
    ActRetainedGroups    = 'Actual - Retained Groups (ran last year)'
    ActAttainment        = 'Actual - Attainment %'
    ActRetentionPct      = 'Actual - Unit Retention %'
    ActGroupRetentionPct = 'Actual - Group Retention %'
    ActNewUnits          = 'Actual - New Units'
    ActNewGroups         = 'Actual - New Groups'
    ActNewGroupAvg       = 'Actual - Avg Units per New Group'
    ActRetainedGroupAvg  = 'Actual - Avg Units per Retained Group'
}

$planFields = 'Season', 'Program', 'PriorUnits', 'GoalOverride', 'GrowthPct', 'GoalUnits', 'RetentionPct', 'PlanNewUnits', 'PlanNewGroups',
              'DirectClosePct', 'DirectCallsTarget'
Set-PnPView -List $PP -Identity 'All Items' -Fields $planFields | Out-Null
Add-ViewIfMissing $PP 'By Rep' (@('Author') + $planFields) `
    '<GroupBy Collapse="FALSE"><FieldRef Name="Author" /><FieldRef Name="Season" /></GroupBy><OrderBy><FieldRef Name="Program" /></OrderBy>' `
    '<FieldRef Name="PriorUnits" Type="SUM" />'
Add-ViewIfMissing $PP 'Plan vs Actual' @('Author', 'Season', 'Program', 'GoalUnits', 'ActTotalUnits', 'ActAttainment',
                                         'RetentionPct', 'ActRetentionPct', 'GroupRetentionPct', 'PriorGroups', 'ActRetainedGroups', 'ActGroupRetentionPct',
                                         'PlanNewGroups', 'ActNewGroups', 'AvgUnitsPerGroup', 'ActNewGroupAvg', 'DirectClosePct') `
    '<GroupBy Collapse="FALSE"><FieldRef Name="Season" /></GroupBy><OrderBy><FieldRef Name="Author" /><FieldRef Name="Program" /></OrderBy>' `
    '<FieldRef Name="ActTotalUnits" Type="SUM" />'

Set-ItemLevelSecurity $PP

# ---------------------------------------------------------------------------
# Daily Activity (one row per rep per selling day)
# ---------------------------------------------------------------------------

Write-Step 'Daily Activity list'
$DA = 'Daily Activity'
Get-OrNewList $DA 'DailyActivity' | Out-Null
Set-PnPField -List $DA -Identity 'Title' -Values @{ Required = $false } | Out-Null

Add-FieldXml $DA 'Season'       "<Field Type=""Lookup"" Name=""Season"" StaticName=""Season"" DisplayName=""Season"" List=""{$seasonsId}"" ShowField=""Title"" Required=""TRUE"" />"
Add-FieldXml $DA 'ActivityDate' '<Field Type="DateTime" Name="ActivityDate" StaticName="ActivityDate" DisplayName="ActivityDate" Format="DateOnly" Required="TRUE" />'
Add-NumberField $DA 'DirectCalls'      -Required
Add-NumberField $DA 'IndirectContacts' -Required
Add-NumberField $DA 'DirectBookings'
Add-NumberField $DA 'IndirectBookings'
Add-NumberField $DA 'MFPUnitsToDate'
Add-FieldXml $DA 'DayNotes' '<Field Type="Note" Name="DayNotes" StaticName="DayNotes" DisplayName="DayNotes" NumLines="4" RichText="FALSE" />'
# A sales day = any day with at least one call or contact logged (same rule as the old workbook).
Add-CalcField $DA 'SalesDay' '=IF([DirectCalls]+[IndirectContacts]>0,1,0)' @('DirectCalls', 'IndirectContacts')

Rename-Fields $DA @{
    ActivityDate     = 'Activity Date'
    DirectCalls      = 'Sales Calls'
    IndirectContacts = "$IndirectLabel Contacts"
    DirectBookings   = 'New Groups'
    IndirectBookings = "New Groups Booked - $IndirectLabel"
    MFPUnitsToDate   = 'MFP Units Season-to-Date'
    DayNotes         = 'Notes'
    SalesDay         = 'Sales Day'
}

$daFields = 'Season', 'ActivityDate', 'DirectCalls', 'DirectBookings', 'MFPUnitsToDate', 'SalesDay', 'DayNotes'
Set-PnPView -List $DA -Identity 'All Items' -Fields $daFields | Out-Null
Add-ViewIfMissing $DA 'By Rep' (@('Author') + $daFields) `
    '<GroupBy Collapse="FALSE"><FieldRef Name="Author" /><FieldRef Name="Season" /></GroupBy><OrderBy><FieldRef Name="ActivityDate" Ascending="FALSE" /></OrderBy>' `
    '<FieldRef Name="DirectCalls" Type="SUM" /><FieldRef Name="IndirectContacts" Type="SUM" /><FieldRef Name="DirectBookings" Type="SUM" /><FieldRef Name="IndirectBookings" Type="SUM" /><FieldRef Name="SalesDay" Type="SUM" />'

Set-ItemLevelSecurity $DA

# ---------------------------------------------------------------------------
# Rep Baselines (each rep's starting numbers per season, from the MFP pull)
# ---------------------------------------------------------------------------
# Loaded by tools/Import-RepBaselines.ps1, which gives each row its own permissions: managers
# Full Control, that rep Read. Reps have no access to the list itself, so each sees only their row.
# The app's My Plan screen pre-fills from it.

Write-Step 'Rep Baselines list'
$RB = 'Rep Baselines'
Get-OrNewList $RB 'RepBaselines' | Out-Null
Set-PnPField -List $RB -Identity 'Title' -Values @{ Required = $false } | Out-Null
Add-FieldXml $RB 'Season'  "<Field Type=""Lookup"" Name=""Season"" StaticName=""Season"" DisplayName=""Season"" List=""{$seasonsId}"" ShowField=""Title"" Required=""TRUE"" />"
Add-FieldXml $RB 'RepUser' '<Field Type="User" Name="RepUser" StaticName="RepUser" DisplayName="RepUser" UserSelectionMode="PeopleOnly" Required="TRUE" />'
Add-FieldXml $RB 'RepCode' '<Field Type="Text" Name="RepCode" StaticName="RepCode" DisplayName="RepCode" MaxLength="20" />'
Add-NumberField $RB 'PriorUnits'
Add-NumberField $RB 'PriorGroups'
Add-NumberField $RB 'AvgUnitsPerGroup'  -Decimals 1
Add-NumberField $RB 'RetentionPct'      -Decimals 1 -Percent
Add-NumberField $RB 'GroupRetentionPct' -Decimals 1 -Percent
Add-FieldXml $RB 'BaseSeason' '<Field Type="Text" Name="BaseSeason" StaticName="BaseSeason" DisplayName="BaseSeason" MaxLength="20" />'
Add-NumberField $RB 'BaseUnits'
Add-NumberField $RB 'BaseGroups'
Add-NumberField $RB 'RetainedUnits'
Add-NumberField $RB 'RetainedGroups'
Rename-Fields $RB @{
    Title             = 'Notes'
    RepUser           = 'Rep'
    RepCode           = 'Rep Code'
    PriorUnits        = 'Prior Year Units'
    PriorGroups       = 'Prior Year Groups'
    AvgUnitsPerGroup  = 'Avg Units per Group'
    RetentionPct      = 'Unit Retention %'
    GroupRetentionPct = 'Group Retention %'
    BaseSeason        = 'Retention Measured From'
    BaseUnits         = 'Base Season Units'
    BaseGroups        = 'Base Season Groups'
    RetainedUnits     = 'Retained Units'
    RetainedGroups    = 'Retained Groups'
}
Set-PnPView -List $RB -Identity 'All Items' -Fields 'Season', 'RepCode', 'RepUser', 'PriorUnits', 'PriorGroups', 'AvgUnitsPerGroup',
    'RetentionPct', 'GroupRetentionPct', 'BaseSeason', 'BaseUnits', 'BaseGroups', 'RetainedUnits', 'RetainedGroups' | Out-Null
Set-RepsAccess $RB $null

if (Get-PnPList -Identity 'Weekly Check-ins' -ErrorAction SilentlyContinue) {
    Write-Warning "The old 'Weekly Check-ins' list is no longer used (replaced by 'Daily Activity'). Delete it from Site contents if it's empty."
}

Write-Step 'Done'
Write-Host @"
Next steps (see docs/):
  1. Open the Reps list and fill in each rep's name and MFP Owning User Code.
     Then load the season's starting numbers: tools/Import-RepBaselines.ps1 (docs/05-mfp-yearly-pull.md).
  2. Open the Seasons list, set the Sales Days Goal, and tick 'Current Season' on the season in progress.
  3. Sign in as (or ask) one rep to confirm they can only see their own rows.
  4. Build the Power App (docs/03-power-app.md) and the weekly summary flows (docs/04-friday-reminder-flow.md).
"@
