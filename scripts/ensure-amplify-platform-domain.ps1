param(
    [Parameter(Mandatory = $true)]
    [string]$AppId,

    [Parameter(Mandatory = $true)]
    [string]$DomainName,

    [string]$BranchName = "main",

    [string]$Region = "ap-south-1",

    [switch]$IncludeApex
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-AWS {
    $result = python -m awscli @args 2>&1
    if ($LASTEXITCODE -ne 0) { throw "AWS CLI error: $result" }
    return $result
}

Set-Alias -Name aws -Value Invoke-AWS -Scope Script

$subDomainSettings = @(
    @{ prefix = "*"; branchName = $BranchName }
)

if ($IncludeApex) {
    $subDomainSettings += @{ prefix = ""; branchName = $BranchName }
}

$subDomainJson = $subDomainSettings | ConvertTo-Json -Compress

try {
    $existing = python -m awscli amplify get-domain-association `
        --app-id $AppId `
        --domain-name $DomainName `
        --region $Region `
        --output json 2>$null

    if ($LASTEXITCODE -eq 0 -and $existing) {
        $result = python -m awscli amplify update-domain-association `
            --app-id $AppId `
            --domain-name $DomainName `
            --sub-domain-settings $subDomainJson `
            --region $Region `
            --output json
    } else {
        $result = python -m awscli amplify create-domain-association `
            --app-id $AppId `
            --domain-name $DomainName `
            --sub-domain-settings $subDomainJson `
            --region $Region `
            --output json
    }
} catch {
    throw
}

$payload = $result | ConvertFrom-Json
$association = $payload.domainAssociation

Write-Host ""
Write-Host "Amplify platform domain synced" -ForegroundColor Green
Write-Host "  App ID: $AppId"
Write-Host "  Domain: $DomainName"
Write-Host "  Branch: $BranchName"
Write-Host "  Status: $($association.domainStatus)"
Write-Host "  Update Status: $($association.updateStatus)"

if ($association.certificateVerificationDNSRecord) {
    Write-Host ""
    Write-Host "Certificate verification DNS:" -ForegroundColor Yellow
    Write-Host "  $($association.certificateVerificationDNSRecord)"
}

if ($association.subDomains) {
    Write-Host ""
    Write-Host "Subdomain DNS records:" -ForegroundColor Yellow
    foreach ($subdomain in $association.subDomains) {
        $prefix = if ($subdomain.subDomainSetting.prefix -eq "") { "<apex>" } else { $subdomain.subDomainSetting.prefix }
        Write-Host "  Prefix: $prefix"
        Write-Host "    Branch: $($subdomain.subDomainSetting.branchName)"
        Write-Host "    Verified: $($subdomain.verified)"
        Write-Host "    DNS: $($subdomain.dnsRecord)"
    }
}
