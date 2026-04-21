param(
    [string]$Region = "ap-south-1",
    [string]$SourceLambdaName = "airbee-backend",
    [string]$PlatformLambdaName = "airbee-platform-api",
    [string]$BookingLambdaName = "airbee-booking-api",
    [string]$PlatformApiName = "airbee-platform-api",
    [string]$BookingApiName = "airbee-booking-api",
    [string]$DbHost,
    [string]$DbPort,
    [string]$DbName,
    [string]$DbUser,
    [string]$DbPassword,
    [string]$CognitoUserPoolId,
    [string]$CognitoClientId,
    [string]$LambdaRoleArn,
    [string]$PublicBaseDomain,
    [string]$PublicCnameTarget,
    [string[]]$PlatformHosts,
    [string]$AmplifyAppId,
    [string]$AmplifyBranch,
    [string]$AmplifyRegion,
    [string]$DjangoSecretKey,
    [string]$BedrockRegion,
    [string]$BedrockModelId,
    [string]$BedrockFallbackModelId,
    [string]$AwsBearerTokenBedrock,
    [switch]$WriteFrontendEnvFiles
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $Root "aws\backend"
$FrontendDir = Join-Path $Root "frontend"
$PackageDir = Join-Path $BackendDir "package"
$ZipPath = Join-Path $BackendDir "function.zip"

function Invoke-AWS {
    $result = python -m awscli @args 2>&1
    if ($LASTEXITCODE -ne 0) { throw "AWS CLI error: $result" }
    return $result
}

Set-Alias -Name aws -Value Invoke-AWS -Scope Script

function Get-LambdaConfiguration {
    param([string]$FunctionName)

    try {
        $raw = python -m awscli lambda get-function-configuration --function-name $FunctionName --region $Region --output json 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $raw) { return $null }
        return $raw | ConvertFrom-Json
    } catch {
        return $null
    }
}

function Get-ApiByName {
    param([string]$Name)

    $apis = python -m awscli apigatewayv2 get-apis --region $Region --output json | ConvertFrom-Json
    return $apis.Items | Where-Object { $_.Name -eq $Name } | Select-Object -First 1
}

function Get-OrDefault {
    param(
        [string]$CurrentValue,
        [string]$FallbackValue,
        [string]$DefaultValue = ""
    )

    if ($CurrentValue) { return $CurrentValue }
    if ($FallbackValue) { return $FallbackValue }
    return $DefaultValue
}

function Get-MapValue {
    param(
        [object]$Map,
        [string]$Key
    )

    if ($null -eq $Map) { return $null }
    if ($Map -is [System.Collections.IDictionary]) {
        if ($Map.Contains($Key)) {
            return [string]$Map[$Key]
        }
        return $null
    }

    $property = $Map.PSObject.Properties[$Key]
    if ($property) {
        return [string]$property.Value
    }

    return $null
}

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

function Ensure-CognitoClientId {
    param(
        [string]$UserPoolId,
        [string]$ClientId
    )

    if ($ClientId) { return $ClientId }
    if (-not $UserPoolId) { return $null }

    $raw = python -m awscli cognito-idp list-user-pool-clients --user-pool-id $UserPoolId --region $Region --output json
    $clients = ($raw | ConvertFrom-Json).UserPoolClients
    $preferred = $clients | Where-Object { $_.ClientName -eq "airbee-frontend" } | Select-Object -First 1
    if ($preferred) { return $preferred.ClientId }
    return ($clients | Select-Object -First 1).ClientId
}

function Ensure-BackendPackage {
    if (Test-Path $PackageDir) {
        Remove-Item -Recurse -Force $PackageDir
    }
    New-Item -ItemType Directory -Path $PackageDir | Out-Null

    Write-Host "Packaging backend Lambda bundle..." -ForegroundColor Yellow
    python -m pip install `
        --platform manylinux2014_x86_64 `
        --python-version 3.12 `
        --only-binary=:all: `
        --implementation cp `
        --quiet `
        -r (Join-Path $BackendDir "requirements.txt") `
        -t $PackageDir
    if ($LASTEXITCODE -ne 0) { throw "pip install failed for backend package" }

    Copy-Item -Recurse -Force (Join-Path $BackendDir "airbee") (Join-Path $PackageDir "airbee")
    Copy-Item -Recurse -Force (Join-Path $BackendDir "api") (Join-Path $PackageDir "api")
    Copy-Item -Force (Join-Path $BackendDir "lambda_handler.py") (Join-Path $PackageDir "lambda_handler.py")

    if (Test-Path $ZipPath) {
        Remove-Item $ZipPath -Force
    }

    python -c @"
import zipfile, pathlib
pkg = pathlib.Path(r'$PackageDir')
out = pathlib.Path(r'$ZipPath')
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zf:
    for path in pkg.rglob('*'):
        if path.is_file():
            zf.write(path, path.relative_to(pkg))
print(out)
"@
    if ($LASTEXITCODE -ne 0) { throw "Failed to build backend zip package" }
}

function Ensure-LambdaFunction {
    param(
        [string]$FunctionName,
        [hashtable]$EnvMap,
        [string]$RoleArn
    )

    $envPath = Join-Path $env:TEMP ("{0}-env.json" -f $FunctionName)
    (@{ Variables = $EnvMap } | ConvertTo-Json -Compress) | Out-File -FilePath $envPath -Encoding ascii

    $existing = Get-LambdaConfiguration -FunctionName $FunctionName
    if (-not $existing) {
        python -m awscli lambda create-function `
            --function-name $FunctionName `
            --runtime python3.12 `
            --role $RoleArn `
            --handler lambda_handler.handler `
            --zip-file ("fileb://{0}" -f $ZipPath) `
            --timeout 60 `
            --memory-size 512 `
            --environment ("file://{0}" -f $envPath) `
            --region $Region `
            --output json | Out-Null
        Write-Host "  Created Lambda: $FunctionName" -ForegroundColor Green
    } else {
        python -m awscli lambda update-function-code `
            --function-name $FunctionName `
            --zip-file ("fileb://{0}" -f $ZipPath) `
            --region $Region `
            --output json | Out-Null
        Start-Sleep -Seconds 5
        python -m awscli lambda update-function-configuration `
            --function-name $FunctionName `
            --role $RoleArn `
            --timeout 60 `
            --memory-size 512 `
            --environment ("file://{0}" -f $envPath) `
            --region $Region `
            --output json | Out-Null
        Write-Host "  Updated Lambda: $FunctionName" -ForegroundColor Green
    }
}

function Ensure-HttpApi {
    param([string]$Name)

    $api = Get-ApiByName -Name $Name
    if (-not $api) {
        $created = python -m awscli apigatewayv2 create-api `
            --name $Name `
            --protocol-type HTTP `
            --cors-configuration 'AllowOrigins=["*"],AllowMethods=["*"],AllowHeaders=["Authorization","Content-Type"]' `
            --region $Region `
            --output json | ConvertFrom-Json
        $api = $created
        Write-Host "  Created API: $Name" -ForegroundColor Green
    } else {
        Write-Host "  Reusing API: $Name" -ForegroundColor Gray
    }

    python -m awscli apigatewayv2 update-api `
        --api-id $api.ApiId `
        --cors-configuration 'AllowOrigins=["*"],AllowMethods=["*"],AllowHeaders=["Authorization","Content-Type"]' `
        --region $Region `
        --output json | Out-Null

    return $api
}

function Ensure-Integration {
    param(
        [string]$ApiId,
        [string]$LambdaArn
    )

    $integrationUri = "arn:aws:apigateway:${Region}:lambda:path/2015-03-31/functions/${LambdaArn}/invocations"
    $integrations = python -m awscli apigatewayv2 get-integrations --api-id $ApiId --region $Region --output json | ConvertFrom-Json
    $existing = $integrations.Items | Where-Object { $_.IntegrationUri -eq $integrationUri } | Select-Object -First 1
    if ($existing) {
        return $existing.IntegrationId
    }

    $created = python -m awscli apigatewayv2 create-integration `
        --api-id $ApiId `
        --integration-type AWS_PROXY `
        --integration-uri $integrationUri `
        --payload-format-version 2.0 `
        --region $Region `
        --output json | ConvertFrom-Json
    return $created.IntegrationId
}

function Ensure-JwtAuthorizer {
    param(
        [string]$ApiId,
        [string]$UserPoolId,
        [string]$ClientId
    )

    $issuer = "https://cognito-idp.${Region}.amazonaws.com/${UserPoolId}"
    $authorizers = python -m awscli apigatewayv2 get-authorizers --api-id $ApiId --region $Region --output json | ConvertFrom-Json
    $existing = $authorizers.Items | Where-Object { $_.Name -eq "cognito-jwt" } | Select-Object -First 1
    if ($existing) {
        python -m awscli apigatewayv2 update-authorizer `
            --api-id $ApiId `
            --authorizer-id $existing.AuthorizerId `
            --authorizer-type JWT `
            --identity-source '$request.header.Authorization' `
            --name cognito-jwt `
            --jwt-configuration ("Issuer={0},Audience={1}" -f $issuer, $ClientId) `
            --region $Region `
            --output json | Out-Null
        return $existing.AuthorizerId
    }

    $created = python -m awscli apigatewayv2 create-authorizer `
        --api-id $ApiId `
        --authorizer-type JWT `
        --identity-source '$request.header.Authorization' `
        --name cognito-jwt `
        --jwt-configuration ("Issuer={0},Audience={1}" -f $issuer, $ClientId) `
        --region $Region `
        --output json | ConvertFrom-Json
    return $created.AuthorizerId
}

function Ensure-Route {
    param(
        [string]$ApiId,
        [string]$RouteKey,
        [string]$IntegrationId,
        [string]$AuthorizationType = "NONE",
        [string]$AuthorizerId
    )

    $routes = python -m awscli apigatewayv2 get-routes --api-id $ApiId --region $Region --output json | ConvertFrom-Json
    $existing = $routes.Items | Where-Object { $_.RouteKey -eq $RouteKey } | Select-Object -First 1

    if ($existing) {
        $args = @(
            "apigatewayv2", "update-route",
            "--api-id", $ApiId,
            "--route-id", $existing.RouteId,
            "--target", "integrations/$IntegrationId",
            "--authorization-type", $AuthorizationType,
            "--region", $Region,
            "--output", "json"
        )
        if ($AuthorizationType -eq "JWT" -and $AuthorizerId) {
            $args += @("--authorizer-id", $AuthorizerId)
        }
        python -m awscli @args | Out-Null
    } else {
        $args = @(
            "apigatewayv2", "create-route",
            "--api-id", $ApiId,
            "--route-key", $RouteKey,
            "--target", "integrations/$IntegrationId",
            "--authorization-type", $AuthorizationType,
            "--region", $Region,
            "--output", "json"
        )
        if ($AuthorizationType -eq "JWT" -and $AuthorizerId) {
            $args += @("--authorizer-id", $AuthorizerId)
        }
        python -m awscli @args | Out-Null
    }
}

function Ensure-Stage {
    param([string]$ApiId)

    $stages = python -m awscli apigatewayv2 get-stages --api-id $ApiId --region $Region --output json | ConvertFrom-Json
    $defaultStage = $stages.Items | Where-Object { $_.StageName -eq '$default' } | Select-Object -First 1
    if ($defaultStage) {
        python -m awscli apigatewayv2 update-stage `
            --api-id $ApiId `
            --stage-name '$default' `
            --auto-deploy `
            --region $Region `
            --output json | Out-Null
    } else {
        python -m awscli apigatewayv2 create-stage `
            --api-id $ApiId `
            --stage-name '$default' `
            --auto-deploy `
            --region $Region `
            --output json | Out-Null
    }
}

function Ensure-LambdaInvokePermission {
    param(
        [string]$FunctionName,
        [string]$ApiId,
        [string]$StatementId
    )

    try {
        python -m awscli lambda remove-permission `
            --function-name $FunctionName `
            --statement-id $StatementId `
            --region $Region `
            --output json 2>$null | Out-Null
    } catch {
    }

    try {
        python -m awscli lambda add-permission `
            --function-name $FunctionName `
            --statement-id $StatementId `
            --action lambda:InvokeFunction `
            --principal apigateway.amazonaws.com `
            --source-arn ("arn:aws:execute-api:{0}:{1}:{2}/*/*" -f $Region, $AccountId, $ApiId) `
            --region $Region `
            --output json 2>&1 | Out-Null
    } catch {
        throw "Failed to grant API Gateway invoke permission on $FunctionName. $($_.Exception.Message)"
    }
}

$sourceConfig = Get-LambdaConfiguration -FunctionName $SourceLambdaName
$sourceEnv = @{}
if ($sourceConfig -and $sourceConfig.Environment -and $sourceConfig.Environment.Variables) {
    $sourceEnv = $sourceConfig.Environment.Variables
}

$identity = python -m awscli sts get-caller-identity --region $Region --output json | ConvertFrom-Json
$AccountId = $identity.Account

$DbHost = Get-OrDefault -CurrentValue $DbHost -FallbackValue (Get-MapValue -Map $sourceEnv -Key "DB_HOST")
$DbPort = Get-OrDefault -CurrentValue $DbPort -FallbackValue (Get-MapValue -Map $sourceEnv -Key "DB_PORT") -DefaultValue "5432"
$DbName = Get-OrDefault -CurrentValue $DbName -FallbackValue (Get-MapValue -Map $sourceEnv -Key "DB_NAME") -DefaultValue "airbee"
$DbUser = Get-OrDefault -CurrentValue $DbUser -FallbackValue (Get-MapValue -Map $sourceEnv -Key "DB_USER") -DefaultValue "airbee"
$DbPassword = Get-OrDefault -CurrentValue $DbPassword -FallbackValue (Get-MapValue -Map $sourceEnv -Key "DB_PASSWORD")
$CognitoUserPoolId = Get-OrDefault -CurrentValue $CognitoUserPoolId -FallbackValue (Get-MapValue -Map $sourceEnv -Key "COGNITO_USER_POOL_ID")
$LambdaRoleArn = Get-OrDefault -CurrentValue $LambdaRoleArn -FallbackValue $sourceConfig.Role
$PublicBaseDomain = Get-OrDefault -CurrentValue $PublicBaseDomain -FallbackValue (Get-MapValue -Map $sourceEnv -Key "PUBLIC_BASE_DOMAIN")
$PublicCnameTarget = Get-OrDefault -CurrentValue $PublicCnameTarget -FallbackValue (Get-MapValue -Map $sourceEnv -Key "PUBLIC_CNAME_TARGET")
$PlatformHosts = Normalize-HostList -Value (Get-OrDefault -CurrentValue (Normalize-HostList -Value $PlatformHosts) -FallbackValue (Get-MapValue -Map $sourceEnv -Key "PLATFORM_HOSTS"))
$AmplifyAppId = Get-OrDefault -CurrentValue $AmplifyAppId -FallbackValue (Get-MapValue -Map $sourceEnv -Key "AMPLIFY_APP_ID")
$AmplifyBranch = Get-OrDefault -CurrentValue $AmplifyBranch -FallbackValue (Get-MapValue -Map $sourceEnv -Key "AMPLIFY_BRANCH") -DefaultValue "main"
$AmplifyRegion = Get-OrDefault -CurrentValue $AmplifyRegion -FallbackValue (Get-MapValue -Map $sourceEnv -Key "AMPLIFY_REGION") -DefaultValue $Region
$DjangoSecretKey = Get-OrDefault -CurrentValue $DjangoSecretKey -FallbackValue (Get-MapValue -Map $sourceEnv -Key "DJANGO_SECRET_KEY") -DefaultValue "airbee-split-backend-secret"
$BedrockRegion = Get-OrDefault -CurrentValue $BedrockRegion -FallbackValue (Get-MapValue -Map $sourceEnv -Key "BEDROCK_REGION") -DefaultValue $Region
$BedrockModelId = Get-OrDefault -CurrentValue $BedrockModelId -FallbackValue (Get-MapValue -Map $sourceEnv -Key "BEDROCK_MODEL_ID") -DefaultValue "anthropic.claude-3-haiku-20240307-v1:0"
$BedrockFallbackModelId = Get-OrDefault -CurrentValue $BedrockFallbackModelId -FallbackValue (Get-MapValue -Map $sourceEnv -Key "BEDROCK_FALLBACK_MODEL_ID") -DefaultValue "apac.amazon.nova-lite-v1:0"
$AwsBearerTokenBedrock = Get-OrDefault -CurrentValue $AwsBearerTokenBedrock -FallbackValue (Get-MapValue -Map $sourceEnv -Key "AWS_BEARER_TOKEN_BEDROCK")
$CognitoClientId = Ensure-CognitoClientId -UserPoolId $CognitoUserPoolId -ClientId $CognitoClientId

if (-not $DbHost -or -not $DbPassword -or -not $LambdaRoleArn -or -not $CognitoUserPoolId -or -not $CognitoClientId) {
    throw "Missing required shared settings. Ensure the source lambda exists or pass DbHost, DbPassword, LambdaRoleArn, CognitoUserPoolId, and CognitoClientId explicitly."
}

Ensure-BackendPackage

$sharedEnv = [ordered]@{
    DB_HOST = $DbHost
    DB_PORT = $DbPort
    DB_NAME = $DbName
    DB_USER = $DbUser
    DB_PASSWORD = $DbPassword
    COGNITO_USER_POOL_ID = $CognitoUserPoolId
    BEDROCK_REGION = $BedrockRegion
    BEDROCK_MODEL_ID = $BedrockModelId
    BEDROCK_FALLBACK_MODEL_ID = $BedrockFallbackModelId
    DJANGO_SECRET_KEY = $DjangoSecretKey
}
if ($PublicBaseDomain) { $sharedEnv["PUBLIC_BASE_DOMAIN"] = $PublicBaseDomain }
if ($PublicCnameTarget) { $sharedEnv["PUBLIC_CNAME_TARGET"] = $PublicCnameTarget }
if ($PlatformHosts) { $sharedEnv["PLATFORM_HOSTS"] = $PlatformHosts }
if ($AmplifyAppId) { $sharedEnv["AMPLIFY_APP_ID"] = $AmplifyAppId }
if ($AmplifyBranch) { $sharedEnv["AMPLIFY_BRANCH"] = $AmplifyBranch }
if ($AmplifyRegion) { $sharedEnv["AMPLIFY_REGION"] = $AmplifyRegion }
if ($AwsBearerTokenBedrock) { $sharedEnv["AWS_BEARER_TOKEN_BEDROCK"] = $AwsBearerTokenBedrock }

$platformEnv = [ordered]@{}
foreach ($entry in $sharedEnv.GetEnumerator()) { $platformEnv[$entry.Key] = $entry.Value }
$platformEnv["AIRBEE_API_SURFACE"] = "platform"

$bookingEnv = [ordered]@{}
foreach ($entry in $sharedEnv.GetEnumerator()) { $bookingEnv[$entry.Key] = $entry.Value }
$bookingEnv["AIRBEE_API_SURFACE"] = "public"

Write-Host "Deploying split backend Lambdas..." -ForegroundColor Yellow
Ensure-LambdaFunction -FunctionName $PlatformLambdaName -EnvMap $platformEnv -RoleArn $LambdaRoleArn
Ensure-LambdaFunction -FunctionName $BookingLambdaName -EnvMap $bookingEnv -RoleArn $LambdaRoleArn

$platformLambdaArn = "arn:aws:lambda:${Region}:${AccountId}:function:${PlatformLambdaName}"
$bookingLambdaArn = "arn:aws:lambda:${Region}:${AccountId}:function:${BookingLambdaName}"

Write-Host "Configuring platform API Gateway..." -ForegroundColor Yellow
$platformApi = Ensure-HttpApi -Name $PlatformApiName
$platformIntegrationId = Ensure-Integration -ApiId $platformApi.ApiId -LambdaArn $platformLambdaArn
$platformAuthorizerId = Ensure-JwtAuthorizer -ApiId $platformApi.ApiId -UserPoolId $CognitoUserPoolId -ClientId $CognitoClientId
Ensure-Route -ApiId $platformApi.ApiId -RouteKey "ANY /api/{proxy+}" -IntegrationId $platformIntegrationId -AuthorizationType "JWT" -AuthorizerId $platformAuthorizerId
Ensure-Route -ApiId $platformApi.ApiId -RouteKey "ANY /ai/{proxy+}" -IntegrationId $platformIntegrationId -AuthorizationType "JWT" -AuthorizerId $platformAuthorizerId
Ensure-Route -ApiId $platformApi.ApiId -RouteKey "OPTIONS /api/{proxy+}" -IntegrationId $platformIntegrationId -AuthorizationType "NONE"
Ensure-Route -ApiId $platformApi.ApiId -RouteKey "OPTIONS /ai/{proxy+}" -IntegrationId $platformIntegrationId -AuthorizationType "NONE"
Ensure-Stage -ApiId $platformApi.ApiId
Ensure-LambdaInvokePermission -FunctionName $PlatformLambdaName -ApiId $platformApi.ApiId -StatementId "PlatformApiGatewayInvoke"

Write-Host "Configuring booking API Gateway..." -ForegroundColor Yellow
$bookingApi = Ensure-HttpApi -Name $BookingApiName
$bookingIntegrationId = Ensure-Integration -ApiId $bookingApi.ApiId -LambdaArn $bookingLambdaArn
Ensure-Route -ApiId $bookingApi.ApiId -RouteKey "ANY /public/{proxy+}" -IntegrationId $bookingIntegrationId -AuthorizationType "NONE"
Ensure-Route -ApiId $bookingApi.ApiId -RouteKey "OPTIONS /public/{proxy+}" -IntegrationId $bookingIntegrationId -AuthorizationType "NONE"
Ensure-Stage -ApiId $bookingApi.ApiId
Ensure-LambdaInvokePermission -FunctionName $BookingLambdaName -ApiId $bookingApi.ApiId -StatementId "BookingApiGatewayInvoke"

$platformApiUrl = "https://$($platformApi.ApiId).execute-api.$Region.amazonaws.com"
$bookingApiUrl = "https://$($bookingApi.ApiId).execute-api.$Region.amazonaws.com"

if ($WriteFrontendEnvFiles) {
    $platformEnvFile = @"
VITE_APP_HOSTING_MODE=platform
VITE_COGNITO_USER_POOL_ID=$CognitoUserPoolId
VITE_COGNITO_CLIENT_ID=$CognitoClientId
VITE_API_URL=$platformApiUrl
VITE_PLATFORM_HOSTS=$PlatformHosts
VITE_PUBLIC_BASE_DOMAIN=$PublicBaseDomain
"@
    $bookingEnvFile = @"
VITE_APP_HOSTING_MODE=booking
VITE_API_URL=$bookingApiUrl
VITE_PUBLIC_BASE_DOMAIN=$PublicBaseDomain
"@
    $platformEnvFile | Out-File -FilePath (Join-Path $FrontendDir ".env.platform.local") -Encoding ascii
    $bookingEnvFile | Out-File -FilePath (Join-Path $FrontendDir ".env.booking.local") -Encoding ascii
    Write-Host "Wrote frontend env files for platform and booking modes." -ForegroundColor Green
}

Write-Host "" 
Write-Host "Split backend ensured" -ForegroundColor Green
Write-Host "  Platform Lambda: $PlatformLambdaName"
Write-Host "  Platform API: $platformApiUrl"
Write-Host "  Booking Lambda: $BookingLambdaName"
Write-Host "  Booking API: $bookingApiUrl"
Write-Host "" 
Write-Host "Use these with the split frontend hosting:" -ForegroundColor Yellow
Write-Host "  Platform app -> $platformApiUrl"
Write-Host "  Booking app  -> $bookingApiUrl"
