<#
.SYNOPSIS
    Loads each rep's starting numbers for a season (from tools/build_plan_baseline.py) into the
    Rep Baselines list, so the app's My Plan screen can pre-fill them.

.DESCRIPTION
    For each CSV row: finds the rep in the Reps list by MFP Owning User Code, adds or updates their
    Rep Baselines row for the season, then gives that row its own permissions: the Sales Planner
    Managers group gets Full Control and the rep gets Read. No other rep can see it.

    Safe to run again: an existing row for the same season and rep code is updated, not duplicated.
    Rows for rep codes with no Reps list entry (or no Rep person set) are skipped and listed.

.EXAMPLE
    ./tools/Import-RepBaselines.ps1 `
        -SiteUrl  https://ritebitefundraising.sharepoint.com/sites/SalesPlanner `
        -ClientId <client id> `
        -CsvPath  "Plan Baseline 2027 Spring.csv"
#>
param(
    [Parameter(Mandatory)] [string] $SiteUrl,
    [Parameter(Mandatory)] [string] $ClientId,
    [Parameter(Mandatory)] [string] $CsvPath
)

$ErrorActionPreference = 'Stop'
$List = 'Rep Baselines'
$ManagersGroup = 'Sales Planner Managers'

Connect-PnPOnline -Url $SiteUrl -ClientId $ClientId -Interactive

$rows = @(Import-Csv -Path $CsvPath)
if (-not $rows) { throw "No rows in $CsvPath" }

# Rep code -> rep's email, from the Reps list
$repEmail = @{}
foreach ($i in Get-PnPListItem -List 'Reps' -PageSize 100) {
    if ($i['MFPCode'] -and $i['RepUser']) { $repEmail[$i['MFPCode'].Trim().ToUpper()] = $i['RepUser'].Email }
}

# Season name -> Seasons list item ID
$seasonId = @{}
foreach ($i in Get-PnPListItem -List 'Seasons' -PageSize 100) { $seasonId[$i['Title']] = $i.Id }

$existing = @(Get-PnPListItem -List $List -PageSize 500)
$skipped = @()

foreach ($r in $rows) {
    $code = $r.'Rep Code'.Trim().ToUpper()
    if (-not $seasonId.ContainsKey($r.Season)) { throw "Season '$($r.Season)' isn't in the Seasons list. Add it first." }
    if (-not $repEmail.ContainsKey($code)) { $skipped += $code; continue }

    $values = @{
        Season            = $seasonId[$r.Season]
        RepUser           = $repEmail[$code]
        RepCode           = $code
        PriorUnits        = [double]$r.'Prior Year Units'
        PriorGroups       = [double]$r.'Prior Year Groups'
        AvgUnitsPerGroup  = [double]$r.'Avg Units per Group'
        RetentionPct      = [double]$r.'Unit Retention %'
        GroupRetentionPct = [double]$r.'Group Retention %'
        BaseSeason        = $r.'Base Season'
        BaseUnits         = [double]$r.'Base Units'
        BaseGroups        = [double]$r.'Base Groups'
        RetainedUnits     = [double]$r.'Retained Units'
        RetainedGroups    = [double]$r.'Retained Groups'
    }

    $item = $existing | Where-Object { $_['RepCode'] -eq $code -and $_['Season'].LookupId -eq $seasonId[$r.Season] } | Select-Object -First 1
    if ($item) {
        Set-PnPListItem -List $List -Identity $item.Id -Values $values | Out-Null
        $action = 'updated'
    }
    else {
        $item = Add-PnPListItem -List $List -Values $values
        $action = 'added'
    }

    # Only managers and this rep can see the row. -ClearExisting stops it inheriting the list's permissions.
    Set-PnPListItemPermission -List $List -Identity $item.Id -Group $ManagersGroup -AddRole 'Full Control' -ClearExisting
    Set-PnPListItemPermission -List $List -Identity $item.Id -User $repEmail[$code] -AddRole 'Read'

    Write-Host ("   {0} {1} {2}: {3} units, {4} groups, unit retention {5:P0}, group retention {6:P0}" -f `
        $action, $r.Season, $code, $r.'Prior Year Units', $r.'Prior Year Groups', [double]$r.'Unit Retention %', [double]$r.'Group Retention %')
}

if ($skipped) {
    Write-Warning ("Skipped (no Reps list row with this MFP code and a Rep person): " + (($skipped | Sort-Object -Unique) -join ', '))
}
