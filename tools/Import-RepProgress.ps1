<#
.SYNOPSIS
    Loads the weekly MFP numbers (from tools/build_rep_progress.py) onto each rep's Rep Baselines row:
    MFP Units to Date, MFP New Groups, MFP New Groups Last 2 Seasons and MFP As Of.

.DESCRIPTION
    Matches rows by season and MFP Owning User Code. Rows are normally created by Import-RepBaselines.ps1
    before the season; if a rep has no row yet, one is created here with the same per-row permissions
    (managers Full Control, that rep Read). Only the four MFP columns are changed on existing rows.

    With -Tenant and -Thumbprint it signs in as the app with a certificate instead of as you (no browser), which
    is how tools/mfp_nightly.py runs it each night (docs/06-nightly-mfp-export.md).

.EXAMPLE
    ./tools/Import-RepProgress.ps1 `
        -SiteUrl  https://ritebitefundraising.sharepoint.com/sites/SalesPlanner `
        -ClientId <client id> `
        -CsvPath  "Rep Progress 2027 Spring.csv"
#>
param(
    [Parameter(Mandatory)] [string] $SiteUrl,
    [Parameter(Mandatory)] [string] $ClientId,
    [Parameter(Mandatory)] [string] $CsvPath,
    [string] $Tenant,       # e.g. ritebitefundraising.onmicrosoft.com; with -Thumbprint, for unattended runs
    [string] $Thumbprint    # certificate in Cert:\CurrentUser\My
)

$ErrorActionPreference = 'Stop'
$List = 'Rep Baselines'
$ManagersGroup = 'Sales Planner Managers'

if ($Thumbprint) {
    Connect-PnPOnline -Url $SiteUrl -ClientId $ClientId -Tenant $Tenant -Thumbprint $Thumbprint
}
else {
    Connect-PnPOnline -Url $SiteUrl -ClientId $ClientId -Interactive
}

$rows = @(Import-Csv -Path $CsvPath)
if (-not $rows) { throw "No rows in $CsvPath" }

$repEmail = @{}
foreach ($i in Get-PnPListItem -List 'Reps' -PageSize 100) {
    if ($i['MFPCode'] -and $i['RepUser']) { $repEmail[$i['MFPCode'].Trim().ToUpper()] = $i['RepUser'].Email }
}
$seasonId = @{}
foreach ($i in Get-PnPListItem -List 'Seasons' -PageSize 100) { $seasonId[$i['Title']] = $i.Id }

$existing = @(Get-PnPListItem -List $List -PageSize 500)
$skipped = @()

foreach ($r in $rows) {
    $code = $r.'Rep Code'.Trim().ToUpper()
    if (-not $seasonId.ContainsKey($r.Season)) { throw "Season '$($r.Season)' isn't in the Seasons list." }
    if (-not $repEmail.ContainsKey($code)) { $skipped += $code; continue }

    $values = @{
        MFPUnitsToDate = [double]$r.'MFP Units to Date'
        MFPNewGroups   = [double]$r.'MFP New Groups'
        MFPNewGroups12 = [double]$r.'MFP New Groups 12 Mo'
        MFPAsOf        = [datetime]$r.'As Of'
    }
    $item = $existing | Where-Object { $_['RepCode'] -eq $code -and $_['Season'].LookupId -eq $seasonId[$r.Season] } | Select-Object -First 1
    if ($item) {
        Set-PnPListItem -List $List -Identity $item.Id -Values $values | Out-Null
    }
    else {
        $values.Season  = $seasonId[$r.Season]
        $values.RepUser = $repEmail[$code]
        $values.RepCode = $code
        $item = Add-PnPListItem -List $List -Values $values
        Set-PnPListItemPermission -List $List -Identity $item.Id -Group $ManagersGroup -AddRole 'Full Control' -ClearExisting
        Set-PnPListItemPermission -List $List -Identity $item.Id -User $repEmail[$code] -AddRole 'Read'
    }
    Write-Host ("   {0} {1}: {2} units, {3} new groups this season, {4} over the last 2 seasons (as of {5})" -f `
        $r.Season, $code, $r.'MFP Units to Date', $r.'MFP New Groups', $r.'MFP New Groups 12 Mo', $r.'As Of')
}

if ($skipped) {
    Write-Warning ("Skipped (no Reps list row with this MFP code and a Rep person): " + (($skipped | Sort-Object -Unique) -join ', '))
}
