param(
    [string]$Region = "ap-south-1",

    [string]$PlatformAppId,
    [string]$BookingAppId,

    [string]$PlatformAppName = "airbee-platform",
    [string]$BookingAppName = "airbee-booking",

    [string]$Repository,
    [string]$BranchName = "main",

    [string]$AccessToken,
    [string]$OAuthToken,

    [string]$ApiUrl,
    [string]$PlatformApiUrl,
    [string]$BookingApiUrl,

    [string]$UserPoolId,
    [string]$UserPoolClientId,
    [string[]]$PlatformHosts = "app.airbee.com,admin.airbee.com",
    [string]$PublicBaseDomain = "book.airbee.com"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$PlatformBuildSpecPath = Join-Path $Root "amplify-platform.yml"
$BookingBuildSpecPath = Join-Path $Root "amplify-booking.yml"

function Normalize-HostList {
    param([object]$Value)

    if ($null -eq $Value) { return "" }

    $items = if ($Value -is [System.Array]) { $Value } else { @($Value) }
    $normalized = foreach ($item in $items) {
        foreach ($part in ("$item" -split '[,\s]+')) {
            $trimmed = $part.Trim().ToLowerInvariant()
            if ($trimmed) {
                $trimmed
            }
        }
    }

    return (($normalized | Select-Object -Unique) -join ',')
}

$ResolvedPlatformApiUrl = if ($PlatformApiUrl) { $PlatformApiUrl } else { $ApiUrl }
$ResolvedBookingApiUrl = if ($BookingApiUrl) { $BookingApiUrl } else { $ApiUrl }
$PlatformHosts = Normalize-HostList -Value $PlatformHosts

if (-not $ResolvedPlatformApiUrl) {
    throw "Provide PlatformApiUrl or ApiUrl."
}
if (-not $ResolvedBookingApiUrl) {
    throw "Provide BookingApiUrl or ApiUrl."
}

function Invoke-AWS {
    $result = python -m awscli @args 2>&1
    if ($LASTEXITCODE -ne 0) { throw "AWS CLI error: $result" }
    return $result
}

Set-Alias -Name aws -Value Invoke-AWS -Scope Script

function Get-AmplifyAppById {
    param(
        [Parameter(Mandatory = $true)]
        [string]$AppId
    )

    try {
        $raw = python -m awscli amplify get-app --app-id $AppId --region $Region --output json 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $raw) { return $null }
        return ($raw | ConvertFrom-Json).app
    } catch {
        return $null
    }
}

function Get-AmplifyAppByName {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    $raw = python -m awscli amplify list-apps --region $Region --output json
    $apps = ($raw | ConvertFrom-Json).apps
    return $apps | Where-Object { $_.name -eq $Name } | Select-Object -First 1
}

function Get-Branch {
    param(
        [Parameter(Mandatory = $true)]
        [string]$AppId,
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    try {
        $raw = python -m awscli amplify get-branch --app-id $AppId --branch-name $Name --region $Region --output json 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $raw) { return $null }
        return ($raw | ConvertFrom-Json).branch
    } catch {
        return $null
    }
}

function Assert-CreateInputs {
    if (-not $Repository) {
        throw "Repository is required when creating a new Amplify app."
    }
    if (-not $AccessToken -and -not $OAuthToken) {
        throw "Provide either AccessToken or OAuthToken when creating a new Amplify app."
    }
}

function Ensure-AmplifyApp {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [string]$ExistingAppId,
        [Parameter(Mandatory = $true)]
        [string]$BuildSpecPath,
        [Parameter(Mandatory = $true)]
        [hashtable]$EnvironmentVariables
    )

    $buildSpec = Get-Content $BuildSpecPath -Raw
    $envJson = $EnvironmentVariables | ConvertTo-Json -Compress
    $customRulesJson = @(
        @{
            source = "</^[^.]+$|\\.(?!(css|gif|ico|jpg|js|png|txt|svg|woff|ttf|map|json|webmanifest)$)([^.]+$)/>"
            target = "/index.html"
            status = "200"
        }
    ) | ConvertTo-Json -Compress

    $app = $null
    if ($ExistingAppId) {
        $app = Get-AmplifyAppById -AppId $ExistingAppId
    }
    if (-not $app) {
        $app = Get-AmplifyAppByName -Name $Name
    }

    if ($app) {
        Write-Host "Updating Amplify app: $($app.name) ($($app.appId))" -ForegroundColor Yellow
        $updated = python -m awscli amplify update-app `
            --app-id $app.appId `
            --name $Name `
            --platform WEB `
            --build-spec $buildSpec `
            --environment-variables $envJson `
            --enable-branch-auto-build `
            --custom-rules $customRulesJson `
            --region $Region `
            --output json | ConvertFrom-Json
        return $updated.app
    }

    Assert-CreateInputs
    Write-Host "Creating Amplify app: $Name" -ForegroundColor Yellow

    $createArgs = @(
        "amplify", "create-app",
        "--name", $Name,
        "--repository", $Repository,
        "--platform", "WEB",
        "--build-spec", $buildSpec,
        "--environment-variables", $envJson,
        "--enable-branch-auto-build",
        "--custom-rules", $customRulesJson,
        "--region", $Region,
        "--output", "json"
    )
    if ($AccessToken) {
        $createArgs += @("--access-token", $AccessToken)
    } else {
        $createArgs += @("--oauth-token", $OAuthToken)
    }

    $created = python -m awscli @createArgs | ConvertFrom-Json
    return $created.app
}

function Ensure-AmplifyBranch {
    param(
        [Parameter(Mandatory = $true)]
        [string]$AppId,
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    $branch = Get-Branch -AppId $AppId -Name $Name
    if ($branch) {
        Write-Host "Updating branch $Name on app $AppId" -ForegroundColor Yellow
        $updated = python -m awscli amplify update-branch `
            --app-id $AppId `
            --branch-name $Name `
            --stage PRODUCTION `
            --framework React `
            --enable-auto-build `
            --region $Region `
            --output json | ConvertFrom-Json
        return $updated.branch
    }

    Write-Host "Creating branch $Name on app $AppId" -ForegroundColor Yellow
    $created = python -m awscli amplify create-branch `
        --app-id $AppId `
        --branch-name $Name `
        --stage PRODUCTION `
        --framework React `
        --enable-auto-build `
        --region $Region `
        --output json | ConvertFrom-Json
    return $created.branch
}

$platformEnv = @{
    VITE_API_URL = $ResolvedPlatformApiUrl
    VITE_APP_HOSTING_MODE = "platform"
    VITE_PUBLIC_BASE_DOMAIN = $PublicBaseDomain
    VITE_PLATFORM_HOSTS = $PlatformHosts
}

if ($UserPoolId) {
    $platformEnv["VITE_COGNITO_USER_POOL_ID"] = $UserPoolId
}
if ($UserPoolClientId) {
    $platformEnv["VITE_COGNITO_CLIENT_ID"] = $UserPoolClientId
}

$bookingEnv = @{
    VITE_API_URL = $ResolvedBookingApiUrl
    VITE_APP_HOSTING_MODE = "booking"
    VITE_PUBLIC_BASE_DOMAIN = $PublicBaseDomain
}

$platformApp = Ensure-AmplifyApp `
    -Name $PlatformAppName `
    -ExistingAppId $PlatformAppId `
    -BuildSpecPath $PlatformBuildSpecPath `
    -EnvironmentVariables $platformEnv

$bookingApp = Ensure-AmplifyApp `
    -Name $BookingAppName `
    -ExistingAppId $BookingAppId `
    -BuildSpecPath $BookingBuildSpecPath `
    -EnvironmentVariables $bookingEnv

$platformBranch = Ensure-AmplifyBranch -AppId $platformApp.appId -Name $BranchName
$bookingBranch = Ensure-AmplifyBranch -AppId $bookingApp.appId -Name $BranchName

Write-Host ""
Write-Host "Amplify split hosting ensured" -ForegroundColor Green
Write-Host ""
Write-Host "Platform app" -ForegroundColor Cyan
Write-Host "  App ID: $($platformApp.appId)"
Write-Host "  Default domain: https://$BranchName.$($platformApp.defaultDomain)"
Write-Host "  API URL: $ResolvedPlatformApiUrl"
Write-Host "  Branch ARN: $($platformBranch.branchArn)"
Write-Host ""
Write-Host "Booking app" -ForegroundColor Cyan
Write-Host "  App ID: $($bookingApp.appId)"
Write-Host "  Default domain: https://$BranchName.$($bookingApp.defaultDomain)"
Write-Host "  API URL: $ResolvedBookingApiUrl"
Write-Host "  Branch ARN: $($bookingBranch.branchArn)"
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Point your admin host to the platform app."
Write-Host "  2. Point your booking wildcard/custom domains to the booking app."
Write-Host "  3. Run .\\scripts\\ensure-amplify-platform-domain.ps1 against the booking app for the wildcard booking base domain."
