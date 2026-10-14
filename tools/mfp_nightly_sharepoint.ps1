<#
.SYNOPSIS
    SharePoint and email steps for tools/mfp_nightly.py, signed in as the app with a certificate (no browser).

.DESCRIPTION
    -Action Season  Prints the Seasons list row ticked Current Season, and how many days the certificate has left.
    -Action Upload  Saves files to a document-library folder (created if missing), replacing same-named files.
    -Action Mail    Sends an email through Microsoft Graph (needs the Mail.Send application permission).

    The last line starting "RESULT: " is JSON that mfp_nightly.py reads. Setup: docs/06-nightly-mfp-export.md.

.EXAMPLE
    ./tools/mfp_nightly_sharepoint.ps1 -Action Season `
        -SiteUrl https://ritebitefundraising.sharepoint.com/sites/SalesPlanner `
        -ClientId <client id> -Tenant ritebitefundraising.onmicrosoft.com -Thumbprint <thumbprint>
#>
param(
    [Parameter(Mandatory)] [ValidateSet('Season', 'Upload', 'Mail')] [string] $Action,
    [Parameter(Mandatory)] [string] $SiteUrl,
    [Parameter(Mandatory)] [string] $ClientId,
    [Parameter(Mandatory)] [string] $Tenant,
    [Parameter(Mandatory)] [string] $Thumbprint,
    [string]   $Folder,      # Upload: site-relative, e.g. "Shared Documents/Lynwood/Sales Accountibility Sample Planner/Nightly"
    [string[]] $Paths,       # Upload: local files
    [string]   $From,        # Mail
    [string]   $To,          # Mail
    [string]   $Subject,     # Mail
    [string]   $BodyPath     # Mail: text file with the message
)

$ErrorActionPreference = 'Stop'

$cert = Get-Item "Cert:\CurrentUser\My\$Thumbprint" -ErrorAction SilentlyContinue
if (-not $cert) { throw "Certificate $Thumbprint isn't in Cert:\CurrentUser\My for $env:USERNAME. See docs/06, Certificate." }
$daysLeft = [int][math]::Floor(($cert.NotAfter - (Get-Date)).TotalDays)
if ($daysLeft -lt 0) { throw "Certificate $Thumbprint expired on $($cert.NotAfter.ToString('yyyy-MM-dd')). See docs/06, Certificate." }

Connect-PnPOnline -Url $SiteUrl -ClientId $ClientId -Tenant $Tenant -Thumbprint $Thumbprint

switch ($Action) {
    'Season' {
        $current = @(Get-PnPListItem -List 'Seasons' -PageSize 100 | Where-Object { $_['CurrentSeason'] })
        if ($current.Count -ne 1) {
            throw "Expected exactly one Seasons row ticked Current Season; found $($current.Count)."
        }
        $season = $current[0]['Title']
        Write-Host "Current season: $season; certificate good for $daysLeft more days"
        'RESULT: ' + (@{ season = $season; certDaysLeft = $daysLeft } | ConvertTo-Json -Compress)
    }
    'Upload' {
        if (-not $Folder -or -not $Paths) { throw 'Upload needs -Folder and -Paths.' }
        Resolve-PnPFolder -SiteRelativePath $Folder | Out-Null
        foreach ($p in $Paths) {
            Add-PnPFile -Path $p -Folder $Folder | Out-Null
            Write-Host "Saved $(Split-Path $p -Leaf) to $Folder"
        }
        'RESULT: ' + (@{ uploaded = $Paths.Count } | ConvertTo-Json -Compress)
    }
    'Mail' {
        if (-not ($From -and $To -and $Subject -and $BodyPath)) { throw 'Mail needs -From, -To, -Subject and -BodyPath.' }
        $message = @{
            message         = @{
                subject      = $Subject
                body         = @{ contentType = 'Text'; content = (Get-Content -Raw -Path $BodyPath) }
                toRecipients = @(@{ emailAddress = @{ address = $To } })
            }
            saveToSentItems = $false
        }
        Invoke-PnPGraphMethod -Url "v1.0/users/$From/sendMail" -Method Post -Content $message | Out-Null
        Write-Host "Email sent to $To"
        'RESULT: ' + (@{ sent = $true } | ConvertTo-Json -Compress)
    }
}
