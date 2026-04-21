param(
    [string]$Region = "ap-south-1",
    [string]$Project = "airbee",
    [string]$SourceLambdaName = "airbee-backend",
    [string]$PlatformLambdaName = "airbee-platform-api",
    [string]$BookingLambdaName = "airbee-booking-api",
    [string]$PlatformBucketName,
    [string]$BookingBucketName,
    [string[]]$PlatformHosts = @("app.airbee.com", "admin.airbee.com"),
    [string]$PublicBaseDomain = "book.airbee.com",
    [string[]]$PlatformAliases = @(),
    [string[]]$BookingAliases = @(),
    [string]$CertificateArn,
    [string]$CognitoUserPoolId,
    [string]$CognitoClientId,
    [string]$PlatformDistributionComment = "airbee-platform-site",
    [string]$BookingDistributionComment = "airbee-booking-site",
    [string]$PriceClass = "PriceClass_100"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$FrontendDir = Join-Path $Root "frontend"
$BuildRoot = Join-Path $Root ".cloudfront-build"
$PlatformBuildDir = Join-Path $BuildRoot "platform"
$BookingBuildDir = Join-Path $BuildRoot "booking"
$ForwardHostFunctionPath = Join-Path $PSScriptRoot "cloudfront-forward-host.js"
$SpaRewriteFunctionPath = Join-Path $PSScriptRoot "cloudfront-spa-rewrite.js"
$ManagedCachingOptimized = "658327ea-f89d-4fab-a63d-7e88639e58f6"
$ManagedCachingDisabled = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad"
$ManagedAllViewerExceptHostHeader = "b689b0a8-53d0-40ab-baf2-68738e2966ac"

function Invoke-AWS {
    $stdoutPath = Join-Path $env:TEMP ([guid]::NewGuid().ToString() + ".aws.out")
    $stderrPath = Join-Path $env:TEMP ([guid]::NewGuid().ToString() + ".aws.err")
    $argumentList = @("-m", "awscli") + @($args | ForEach-Object { [string]$_ })

    try {
        $process = Start-Process -FilePath "python" `
            -ArgumentList $argumentList `
            -NoNewWindow `
            -Wait `
            -PassThru `
            -RedirectStandardOutput $stdoutPath `
            -RedirectStandardError $stderrPath

        $stdout = ""
        if (Test-Path $stdoutPath) {
            $stdout = [string](Get-Content $stdoutPath -Raw)
        }

        $stderr = ""
        if (Test-Path $stderrPath) {
            $stderr = [string](Get-Content $stderrPath -Raw)
        }

        $message = @($stdout, $stderr) | Where-Object { $_ } | ForEach-Object { $_.Trim() }
        $combined = $message -join [Environment]::NewLine

        if ($process.ExitCode -ne 0) {
            if (-not $combined) {
                $combined = "python -m awscli exited with code $($process.ExitCode)"
            }
            throw "AWS CLI error: $combined"
        }

        return $stdout.Trim()
    } finally {
        Remove-Item $stdoutPath, $stderrPath -ErrorAction SilentlyContinue
    }
}

Set-Alias -Name aws -Value Invoke-AWS -Scope Script

function Normalize-NameList {
    param([object]$Value)

    if ($null -eq $Value) { return @() }

    $items = if ($Value -is [System.Array]) { $Value } else { @($Value) }
    $normalized = foreach ($item in $items) {
        foreach ($part in ("$item" -split '[,\s]+')) {
            $trimmed = $part.Trim().ToLowerInvariant()
            if ($trimmed) {
                $trimmed
            }
        }
    }

    return @($normalized | Select-Object -Unique)
}

function ConvertTo-NativeMap {
    param([object]$Value)

    if ($null -eq $Value) { return $null }

    if ($Value -is [System.Collections.IDictionary]) {
        $map = [ordered]@{}
        foreach ($key in $Value.Keys) {
            $map[$key] = ConvertTo-NativeMap -Value $Value[$key]
        }
        return $map
    }

    if ($Value -is [System.Management.Automation.PSCustomObject]) {
        $map = [ordered]@{}
        foreach ($property in $Value.PSObject.Properties) {
            $map[$property.Name] = ConvertTo-NativeMap -Value $property.Value
        }
        return $map
    }

    if ($Value -is [System.Array]) {
        $items = @($Value | ForEach-Object { ConvertTo-NativeMap -Value $_ })
        return ,$items
    }

    return $Value
}

function Merge-NativeMap {
    param(
        [object]$Base,
        [object]$Overlay
    )

    $baseMap = ConvertTo-NativeMap -Value $Base
    $overlayMap = ConvertTo-NativeMap -Value $Overlay

    if ($null -eq $baseMap) {
        if ($overlayMap -is [System.Array]) { return ,$overlayMap }
        return $overlayMap
    }
    if ($null -eq $overlayMap) {
        if ($baseMap -is [System.Array]) { return ,$baseMap }
        return $baseMap
    }

    $baseIsMap = $baseMap -is [System.Collections.IDictionary]
    $overlayIsMap = $overlayMap -is [System.Collections.IDictionary]
    if (-not $baseIsMap -or -not $overlayIsMap) {
        if ($overlayMap -is [System.Array]) { return ,$overlayMap }
        return $overlayMap
    }

    $merged = [ordered]@{}
    foreach ($key in $baseMap.Keys) {
        $merged[$key] = $baseMap[$key]
    }

    foreach ($key in $overlayMap.Keys) {
        $baseValue = $null
        if ($merged.Contains($key)) {
            $baseValue = $merged[$key]
        }

        $overlayValue = $overlayMap[$key]
        $baseValueIsMap = $baseValue -is [System.Collections.IDictionary]
        $overlayValueIsMap = $overlayValue -is [System.Collections.IDictionary]

        if ($baseValueIsMap -and $overlayValueIsMap) {
            $merged[$key] = Merge-NativeMap -Base $baseValue -Overlay $overlayValue
        } else {
            $merged[$key] = $overlayValue
        }
    }

    return $merged
}
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

function Ensure-FunctionUrlPermissions {
    param([string]$FunctionName)

    foreach ($statementId in @("FunctionUrlInvokeUrl", "FunctionUrlInvokeFunction")) {
        try {
            python -m awscli lambda remove-permission `
                --function-name $FunctionName `
                --statement-id $statementId `
                --region $Region `
                --output json 2>$null | Out-Null
        } catch {
        }
    }

    python -m awscli lambda add-permission `
        --function-name $FunctionName `
        --statement-id "FunctionUrlInvokeUrl" `
        --action lambda:InvokeFunctionUrl `
        --principal * `
        --function-url-auth-type NONE `
        --region $Region `
        --output json | Out-Null

    python -m awscli lambda add-permission `
        --function-name $FunctionName `
        --statement-id "FunctionUrlInvokeFunction" `
        --action lambda:InvokeFunction `
        --principal * `
        --invoked-via-function-url `
        --region $Region `
        --output json | Out-Null
}

function Ensure-LambdaFunctionUrl {
    param([string]$FunctionName)

    $config = $null
    try {
        $raw = python -m awscli lambda get-function-url-config --function-name $FunctionName --region $Region --output json 2>$null
        if ($LASTEXITCODE -eq 0 -and $raw) {
            $config = $raw | ConvertFrom-Json
        }
    } catch {
        $config = $null
    }

    if ($config) {
        $config = python -m awscli lambda update-function-url-config `
            --function-name $FunctionName `
            --auth-type NONE `
            --region $Region `
            --output json | ConvertFrom-Json
    } else {
        $config = python -m awscli lambda create-function-url-config `
            --function-name $FunctionName `
            --auth-type NONE `
            --region $Region `
            --output json | ConvertFrom-Json
    }

    Ensure-FunctionUrlPermissions -FunctionName $FunctionName
    return $config.FunctionUrl
}

function Ensure-Bucket {
    param([string]$BucketName)

    $head = & {
        $ErrorActionPreference = "Continue"
        python -m awscli s3api head-bucket --bucket $BucketName 2>$null
    }

    if ($LASTEXITCODE -ne 0) {
        if ($Region -eq "us-east-1") {
            python -m awscli s3api create-bucket --bucket $BucketName --region $Region --output json | Out-Null
        } else {
            python -m awscli s3api create-bucket `
                --bucket $BucketName `
                --region $Region `
                --create-bucket-configuration "LocationConstraint=$Region" `
                --output json | Out-Null
        }
        Write-Host "Created bucket: $BucketName" -ForegroundColor Green
    } else {
        Write-Host "Reusing bucket: $BucketName" -ForegroundColor Gray
    }

    python -m awscli s3api put-public-access-block `
        --bucket $BucketName `
        --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true `
        --region $Region | Out-Null

    python -m awscli s3api put-bucket-ownership-controls `
        --bucket $BucketName `
        --ownership-controls 'Rules=[{ObjectOwnership=BucketOwnerEnforced}]' `
        --region $Region | Out-Null
}

function Ensure-S3OriginAccessControl {
    param([string]$Name)

    $raw = python -m awscli cloudfront list-origin-access-controls --output json | ConvertFrom-Json
    $items = @()
    if ($raw.OriginAccessControlList -and $raw.OriginAccessControlList.Items) {
        $items = @($raw.OriginAccessControlList.Items)
    }
    $existing = $items | Where-Object { $_.Name -eq $Name } | Select-Object -First 1
    if ($existing) {
        return $existing.Id
    }

    $config = [ordered]@{
        Name = $Name
        Description = "AIR BEE S3 origin access control"
        SigningProtocol = "sigv4"
        SigningBehavior = "always"
        OriginAccessControlOriginType = "s3"
    }
    $configPath = Join-Path $env:TEMP ("{0}-oac.json" -f $Name)
    ($config | ConvertTo-Json -Depth 5) | Out-File -FilePath $configPath -Encoding ascii
    $created = python -m awscli cloudfront create-origin-access-control `
        --origin-access-control-config "file://$configPath" `
        --output json | ConvertFrom-Json
    return $created.OriginAccessControl.Id
}

function Ensure-CloudFrontFunction {
    param(
        [string]$Name,
        [string]$CodePath
    )

    $etag = $null
    $existing = $null
    try {
        $existing = python -m awscli cloudfront describe-function --name $Name --stage DEVELOPMENT --output json 2>$null | ConvertFrom-Json
        if ($LASTEXITCODE -eq 0) {
            $etag = $existing.ETag
        }
    } catch {
        $existing = $null
    }

    if ($existing) {
        $updated = python -m awscli cloudfront update-function `
            --name $Name `
            --if-match $etag `
            --function-config "Comment=AIR BEE preserves viewer host for Lambda origins,Runtime=cloudfront-js-2.0" `
            --function-code "fileb://$CodePath" `
            --output json | ConvertFrom-Json
        $etag = $updated.ETag
    } else {
        $created = python -m awscli cloudfront create-function `
            --name $Name `
            --function-config "Comment=AIR BEE preserves viewer host for Lambda origins,Runtime=cloudfront-js-2.0" `
            --function-code "fileb://$CodePath" `
            --output json | ConvertFrom-Json
        $etag = $created.ETag
    }

    $published = python -m awscli cloudfront publish-function `
        --name $Name `
        --if-match $etag `
        --output json | ConvertFrom-Json
    return $published.FunctionSummary.FunctionMetadata.FunctionARN
}

function Build-FrontendArtifact {
    param(
        [string]$Mode,
        [string]$OutputDir,
        [hashtable]$EnvironmentVariables
    )

    $previous = @{}
    foreach ($entry in $EnvironmentVariables.GetEnumerator()) {
        $previous[$entry.Key] = [System.Environment]::GetEnvironmentVariable($entry.Key, "Process")
        [System.Environment]::SetEnvironmentVariable($entry.Key, [string]$entry.Value, "Process")
    }

    try {
        Push-Location $FrontendDir
        & npm.cmd run ("build:{0}" -f $Mode)
        if ($LASTEXITCODE -ne 0) {
            throw "npm build failed for $Mode"
        }
        Pop-Location
    } catch {
        if ((Get-Location).Path -eq $FrontendDir) {
            Pop-Location
        }
        throw
    } finally {
        foreach ($entry in $EnvironmentVariables.GetEnumerator()) {
            [System.Environment]::SetEnvironmentVariable($entry.Key, $previous[$entry.Key], "Process")
        }
    }

    if (Test-Path $OutputDir) {
        Remove-Item -Recurse -Force $OutputDir
    }
    New-Item -ItemType Directory -Path $OutputDir | Out-Null
    Copy-Item -Recurse -Force (Join-Path $FrontendDir "dist\*") $OutputDir
}

function New-S3Origin {
    param(
        [string]$BucketName,
        [string]$OriginAccessControlId
    )

    return [ordered]@{
        Id = "s3-$BucketName"
        DomainName = "$BucketName.s3.$Region.amazonaws.com"
        OriginPath = ""
        CustomHeaders = [ordered]@{
            Quantity = 0
            Items = @()
        }
        S3OriginConfig = [ordered]@{
            OriginAccessIdentity = ""
            OriginReadTimeout = 30
        }
        ConnectionAttempts = 3
        ConnectionTimeout = 10
        OriginShield = [ordered]@{
            Enabled = $false
        }
        OriginAccessControlId = $OriginAccessControlId
    }
}

function New-LambdaOrigin {
    param(
        [string]$Id,
        [string]$FunctionUrl
    )

    $uri = [Uri]$FunctionUrl
    return [ordered]@{
        Id = $Id
        DomainName = $uri.Host
        OriginPath = ""
        CustomHeaders = [ordered]@{
            Quantity = 0
            Items = @()
        }
        CustomOriginConfig = [ordered]@{
            HTTPPort = 80
            HTTPSPort = 443
            OriginProtocolPolicy = "https-only"
            OriginSslProtocols = [ordered]@{
                Quantity = 1
                Items = @("TLSv1.2")
            }
            OriginReadTimeout = 30
            OriginKeepaliveTimeout = 5
        }
        ConnectionAttempts = 3
        ConnectionTimeout = 10
        OriginShield = [ordered]@{
            Enabled = $false
        }
        OriginAccessControlId = ""
    }
}

function New-DefaultBehavior {
    param(
        [string]$TargetOriginId,
        [string]$SpaRewriteFunctionArn
    )

    return [ordered]@{
        TargetOriginId = $TargetOriginId
        TrustedSigners = [ordered]@{
            Enabled = $false
            Quantity = 0
        }
        TrustedKeyGroups = [ordered]@{
            Enabled = $false
            Quantity = 0
        }
        ViewerProtocolPolicy = "redirect-to-https"
        AllowedMethods = [ordered]@{
            Quantity = 3
            Items = @("HEAD", "GET", "OPTIONS")
            CachedMethods = [ordered]@{
                Quantity = 3
                Items = @("HEAD", "GET", "OPTIONS")
            }
        }
        SmoothStreaming = $false
        Compress = $true
        LambdaFunctionAssociations = [ordered]@{
            Quantity = 0
            Items = @()
        }
        FunctionAssociations = [ordered]@{
            Quantity = 1
            Items = @(
                [ordered]@{
                    FunctionARN = $SpaRewriteFunctionArn
                    EventType = "viewer-request"
                }
            )
        }
        FieldLevelEncryptionId = ""
        CachePolicyId = $ManagedCachingOptimized
        GrpcConfig = [ordered]@{
            Enabled = $false
        }
    }
}

function New-ApiBehavior {
    param(
        [string]$PathPattern,
        [string]$TargetOriginId,
        [string]$ForwardHostFunctionArn
    )

    return [ordered]@{
        PathPattern = $PathPattern
        TargetOriginId = $TargetOriginId
        TrustedSigners = [ordered]@{
            Enabled = $false
            Quantity = 0
        }
        TrustedKeyGroups = [ordered]@{
            Enabled = $false
            Quantity = 0
        }
        ViewerProtocolPolicy = "redirect-to-https"
        AllowedMethods = [ordered]@{
            Quantity = 7
            Items = @("HEAD", "DELETE", "POST", "GET", "OPTIONS", "PUT", "PATCH")
            CachedMethods = [ordered]@{
                Quantity = 2
                Items = @("HEAD", "GET")
            }
        }
        SmoothStreaming = $false
        Compress = $false
        LambdaFunctionAssociations = [ordered]@{
            Quantity = 0
            Items = @()
        }
        FunctionAssociations = [ordered]@{
            Quantity = 1
            Items = @(
                [ordered]@{
                    FunctionARN = $ForwardHostFunctionArn
                    EventType = "viewer-request"
                }
            )
        }
        FieldLevelEncryptionId = ""
        CachePolicyId = $ManagedCachingDisabled
        OriginRequestPolicyId = $ManagedAllViewerExceptHostHeader
        GrpcConfig = [ordered]@{
            Enabled = $false
        }
    }
}

function New-ViewerCertificate {
    param(
        [string[]]$Aliases,
        [string]$CertArn
    )

    $aliasItems = @(if ($Aliases) { $Aliases } else { @() })

    if ($aliasItems.Count -gt 0) {
        if (-not $CertArn) {
            throw "CertificateArn is required when you provide CloudFront aliases. The certificate must be in us-east-1."
        }
        return [ordered]@{
            ACMCertificateArn = $CertArn
            SSLSupportMethod = "sni-only"
            MinimumProtocolVersion = "TLSv1.2_2021"
            CloudFrontDefaultCertificate = $false
            Certificate = $CertArn
            CertificateSource = "acm"
        }
    }

    return [ordered]@{
        CloudFrontDefaultCertificate = $true
    }
}

function Get-DistributionByComment {
    param([string]$Comment)

    $raw = python -m awscli cloudfront list-distributions --output json | ConvertFrom-Json
    $items = @()
    if ($raw.DistributionList -and $raw.DistributionList.Items) {
        $items = @($raw.DistributionList.Items)
    }
    if (-not $items) { return $null }
    return $items | Where-Object { $_.Comment -eq $Comment } | Select-Object -First 1
}

function Ensure-Distribution {
    param(
        [string]$Comment,
        [string[]]$Aliases,
        [object[]]$Origins,
        [hashtable]$DefaultBehavior,
        [object[]]$CacheBehaviors,
        [hashtable]$ViewerCertificate
    )

    $existing = Get-DistributionByComment -Comment $Comment
    $callerReference = "{0}-{1}" -f $Comment, [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    $id = $null
    $etag = $null
    $configResponse = $null
    if ($existing) {
        $id = $existing.Id
        $configResponse = (Invoke-AWS cloudfront get-distribution-config --id $id --output json) | ConvertFrom-Json
        $callerReference = $configResponse.DistributionConfig.CallerReference
        $etag = $configResponse.ETag
    }

    $aliasItems = @(if ($Aliases) { $Aliases } else { @() })
    $originItems = @(if ($Origins) { $Origins } else { @() })
    $cacheBehaviorItems = @(if ($CacheBehaviors) { $CacheBehaviors } else { @() })
    $loggingConfig = [ordered]@{
        Enabled = $false
        IncludeCookies = $false
        Bucket = ""
        Prefix = ""
    }
    if ($configResponse -and $configResponse.DistributionConfig -and $configResponse.DistributionConfig.PSObject.Properties['Logging']) {
        $existingLogging = $configResponse.DistributionConfig.Logging
        if ($existingLogging) {
            $loggingBucket = ""
            $loggingPrefix = ""
            if ($existingLogging.PSObject.Properties['Bucket'] -and $existingLogging.Bucket) {
                $loggingBucket = [string]$existingLogging.Bucket
            }
            if ($existingLogging.PSObject.Properties['Prefix'] -and $existingLogging.Prefix) {
                $loggingPrefix = [string]$existingLogging.Prefix
            }
            $loggingConfig = [ordered]@{
                Enabled = [bool]$existingLogging.Enabled
                IncludeCookies = [bool]$existingLogging.IncludeCookies
                Bucket = $loggingBucket
                Prefix = $loggingPrefix
            }
        }
    }

    $distributionConfig = [ordered]@{
        CallerReference = $callerReference
        Comment = $Comment
        Enabled = $true
        IsIPV6Enabled = $true
        DefaultRootObject = "index.html"
        HttpVersion = "http2"
        PriceClass = $PriceClass
        Aliases = [ordered]@{
            Quantity = $aliasItems.Count
            Items = $aliasItems
        }
        Origins = [ordered]@{
            Quantity = $originItems.Count
            Items = $originItems
        }
        DefaultCacheBehavior = $DefaultBehavior
        CacheBehaviors = [ordered]@{
            Quantity = $cacheBehaviorItems.Count
            Items = $cacheBehaviorItems
        }
        CustomErrorResponses = [ordered]@{
            Quantity = 0
            Items = @()
        }
        Logging = $loggingConfig
        Restrictions = [ordered]@{
            GeoRestriction = [ordered]@{
                RestrictionType = "none"
                Quantity = 0
            }
        }
        ViewerCertificate = $ViewerCertificate
    }

    if ($configResponse -and $configResponse.DistributionConfig) {
        $distributionConfig = Merge-NativeMap -Base $configResponse.DistributionConfig -Overlay $distributionConfig
    }

    $configPath = Join-Path $env:TEMP ("{0}-distribution.json" -f $Comment)
    ($distributionConfig | ConvertTo-Json -Depth 25) | Out-File -FilePath $configPath -Encoding ascii

    if ($existing) {
        $updated = (Invoke-AWS cloudfront update-distribution `
            --id $id `
            --if-match $etag `
            --distribution-config "file://$configPath" `
            --output json) | ConvertFrom-Json
        return $updated.Distribution
    }

    $created = (Invoke-AWS cloudfront create-distribution `
        --distribution-config "file://$configPath" `
        --output json) | ConvertFrom-Json
    return $created.Distribution
}

function Ensure-BucketPolicyForDistribution {
    param(
        [string]$BucketName,
        [string]$DistributionArn
    )

    $policy = [ordered]@{
        Version = "2012-10-17"
        Statement = @(
            [ordered]@{
                Sid = "AllowCloudFrontReadOnly"
                Effect = "Allow"
                Principal = [ordered]@{
                    Service = "cloudfront.amazonaws.com"
                }
                Action = "s3:GetObject"
                Resource = "arn:aws:s3:::$BucketName/*"
                Condition = [ordered]@{
                    StringEquals = [ordered]@{
                        "AWS:SourceArn" = $DistributionArn
                    }
                }
            }
        )
    }

    $policyPath = Join-Path $env:TEMP ("{0}-policy.json" -f $BucketName)
    ($policy | ConvertTo-Json -Depth 10) | Out-File -FilePath $policyPath -Encoding ascii
    python -m awscli s3api put-bucket-policy `
        --bucket $BucketName `
        --policy "file://$policyPath" `
        --region $Region | Out-Null
}

function Sync-BuildToBucket {
    param(
        [string]$SourceDir,
        [string]$BucketName
    )

    python -m awscli s3 sync $SourceDir ("s3://{0}" -f $BucketName) --delete --region $Region | Out-Null
}

function Invalidate-Distribution {
    param([string]$DistributionId)

    python -m awscli cloudfront create-invalidation `
        --distribution-id $DistributionId `
        --paths "/*" `
        --output json | Out-Null
}

function Update-LambdaDnsEnvironment {
    param(
        [string[]]$FunctionNames,
        [string]$PublicBaseDomainValue,
        [string]$PublicCnameTargetValue,
        [string]$PlatformHostsValue
    )

    foreach ($functionName in ($FunctionNames | Select-Object -Unique)) {
        $config = Get-LambdaConfiguration -FunctionName $functionName
        if (-not $config) {
            continue
        }

        $vars = [ordered]@{}
        if ($config.Environment -and $config.Environment.Variables) {
            $config.Environment.Variables.PSObject.Properties | ForEach-Object {
                $vars[$_.Name] = [string]$_.Value
            }
        }

        if ($PublicBaseDomainValue) { $vars["PUBLIC_BASE_DOMAIN"] = $PublicBaseDomainValue }
        if ($PublicCnameTargetValue) { $vars["PUBLIC_CNAME_TARGET"] = $PublicCnameTargetValue }
        if ($PlatformHostsValue) { $vars["PLATFORM_HOSTS"] = $PlatformHostsValue }

        $envPath = Join-Path $env:TEMP ("{0}-dns-env.json" -f $functionName)
        (@{ Variables = $vars } | ConvertTo-Json -Compress) | Out-File -FilePath $envPath -Encoding ascii
        python -m awscli lambda update-function-configuration `
            --function-name $functionName `
            --environment ("file://{0}" -f $envPath) `
            --region $Region `
            --output json | Out-Null
    }
}

$PlatformHosts = Normalize-NameList -Value $PlatformHosts
$PlatformAliases = Normalize-NameList -Value $PlatformAliases
$BookingAliases = Normalize-NameList -Value $BookingAliases

$identity = python -m awscli sts get-caller-identity --region $Region --output json | ConvertFrom-Json
$accountId = $identity.Account

if (-not $PlatformBucketName) {
    $PlatformBucketName = ("{0}-platform-site-{1}-{2}" -f $Project, $accountId, $Region).ToLowerInvariant()
}
if (-not $BookingBucketName) {
    $BookingBucketName = ("{0}-booking-site-{1}-{2}" -f $Project, $accountId, $Region).ToLowerInvariant()
}

$platformLambdaConfig = Get-LambdaConfiguration -FunctionName $PlatformLambdaName
if (-not $platformLambdaConfig) {
    $platformLambdaConfig = Get-LambdaConfiguration -FunctionName $SourceLambdaName
}
$platformEnv = @{}
if ($platformLambdaConfig -and $platformLambdaConfig.Environment -and $platformLambdaConfig.Environment.Variables) {
    $platformEnv = $platformLambdaConfig.Environment.Variables
}

$CognitoUserPoolId = Get-OrDefault -CurrentValue $CognitoUserPoolId -FallbackValue (Get-MapValue -Map $platformEnv -Key "COGNITO_USER_POOL_ID")
$CognitoClientId = Ensure-CognitoClientId -UserPoolId $CognitoUserPoolId -ClientId $CognitoClientId
if (-not $CognitoUserPoolId -or -not $CognitoClientId) {
    throw "CognitoUserPoolId and CognitoClientId are required to build the platform frontend."
}

if (-not (Test-Path $BuildRoot)) {
    New-Item -ItemType Directory -Path $BuildRoot | Out-Null
}

$platformFunctionUrl = Ensure-LambdaFunctionUrl -FunctionName $PlatformLambdaName
$bookingFunctionUrl = Ensure-LambdaFunctionUrl -FunctionName $BookingLambdaName

Build-FrontendArtifact `
    -Mode "platform" `
    -OutputDir $PlatformBuildDir `
    -EnvironmentVariables @{
        VITE_APP_HOSTING_MODE = "platform"
        VITE_API_URL = ""
        VITE_COGNITO_USER_POOL_ID = $CognitoUserPoolId
        VITE_COGNITO_CLIENT_ID = $CognitoClientId
        VITE_PUBLIC_BASE_DOMAIN = $PublicBaseDomain
        VITE_PLATFORM_HOSTS = ($PlatformHosts -join ',')
    }

Build-FrontendArtifact `
    -Mode "booking" `
    -OutputDir $BookingBuildDir `
    -EnvironmentVariables @{
        VITE_APP_HOSTING_MODE = "booking"
        VITE_API_URL = ""
        VITE_PUBLIC_BASE_DOMAIN = $PublicBaseDomain
    }

Ensure-Bucket -BucketName $PlatformBucketName
Ensure-Bucket -BucketName $BookingBucketName

$s3OacId = Ensure-S3OriginAccessControl -Name "$Project-s3-origin-access"
$forwardHostFunctionArn = Ensure-CloudFrontFunction -Name "$Project-forward-host" -CodePath $ForwardHostFunctionPath
$spaRewriteFunctionArn = Ensure-CloudFrontFunction -Name "$Project-spa-rewrite" -CodePath $SpaRewriteFunctionPath

$platformOrigins = @(
    (New-S3Origin -BucketName $PlatformBucketName -OriginAccessControlId $s3OacId),
    (New-LambdaOrigin -Id "platform-lambda-origin" -FunctionUrl $platformFunctionUrl)
)
$platformBehaviors = @(
    (New-ApiBehavior -PathPattern "/api/*" -TargetOriginId "platform-lambda-origin" -ForwardHostFunctionArn $forwardHostFunctionArn),
    (New-ApiBehavior -PathPattern "/ai/*" -TargetOriginId "platform-lambda-origin" -ForwardHostFunctionArn $forwardHostFunctionArn)
)
$platformDistribution = Ensure-Distribution `
    -Comment $PlatformDistributionComment `
    -Aliases $PlatformAliases `
    -Origins $platformOrigins `
    -DefaultBehavior (New-DefaultBehavior -TargetOriginId ("s3-{0}" -f $PlatformBucketName) -SpaRewriteFunctionArn $spaRewriteFunctionArn) `
    -CacheBehaviors $platformBehaviors `
    -ViewerCertificate (New-ViewerCertificate -Aliases $PlatformAliases -CertArn $CertificateArn)

$bookingOrigins = @(
    (New-S3Origin -BucketName $BookingBucketName -OriginAccessControlId $s3OacId),
    (New-LambdaOrigin -Id "booking-lambda-origin" -FunctionUrl $bookingFunctionUrl)
)
$bookingBehaviors = @(
    (New-ApiBehavior -PathPattern "/public/*" -TargetOriginId "booking-lambda-origin" -ForwardHostFunctionArn $forwardHostFunctionArn)
)
$bookingDistribution = Ensure-Distribution `
    -Comment $BookingDistributionComment `
    -Aliases $BookingAliases `
    -Origins $bookingOrigins `
    -DefaultBehavior (New-DefaultBehavior -TargetOriginId ("s3-{0}" -f $BookingBucketName) -SpaRewriteFunctionArn $spaRewriteFunctionArn) `
    -CacheBehaviors $bookingBehaviors `
    -ViewerCertificate (New-ViewerCertificate -Aliases $BookingAliases -CertArn $CertificateArn)

Ensure-BucketPolicyForDistribution -BucketName $PlatformBucketName -DistributionArn $platformDistribution.ARN
Ensure-BucketPolicyForDistribution -BucketName $BookingBucketName -DistributionArn $bookingDistribution.ARN

Sync-BuildToBucket -SourceDir $PlatformBuildDir -BucketName $PlatformBucketName
Sync-BuildToBucket -SourceDir $BookingBuildDir -BucketName $BookingBucketName
Invalidate-Distribution -DistributionId $platformDistribution.Id
Invalidate-Distribution -DistributionId $bookingDistribution.Id

$bookingCnameTarget = $bookingDistribution.DomainName
$preferredAlias = $BookingAliases | Where-Object { $_ -notlike "*." } | Select-Object -First 1
if ($preferredAlias) {
    $bookingCnameTarget = $preferredAlias
}

Update-LambdaDnsEnvironment `
    -FunctionNames @($PlatformLambdaName, $BookingLambdaName, $SourceLambdaName) `
    -PublicBaseDomainValue $PublicBaseDomain `
    -PublicCnameTargetValue $bookingCnameTarget `
    -PlatformHostsValue ($PlatformHosts -join ',')

Write-Host "" 
Write-Host "S3 + CloudFront + Lambda hosting ensured" -ForegroundColor Green
Write-Host "" 
Write-Host "Platform frontend" -ForegroundColor Cyan
Write-Host "  Bucket: $PlatformBucketName"
Write-Host "  Distribution ID: $($platformDistribution.Id)"
Write-Host "  Domain: https://$($platformDistribution.DomainName)"
Write-Host "  Lambda URL origin: $platformFunctionUrl"
Write-Host "" 
Write-Host "Booking frontend" -ForegroundColor Cyan
Write-Host "  Bucket: $BookingBucketName"
Write-Host "  Distribution ID: $($bookingDistribution.Id)"
Write-Host "  Domain: https://$($bookingDistribution.DomainName)"
Write-Host "  Lambda URL origin: $bookingFunctionUrl"
Write-Host "" 
Write-Host "DNS target for custom booking domains" -ForegroundColor Yellow
Write-Host "  PUBLIC_CNAME_TARGET=$bookingCnameTarget"
Write-Host "" 
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. If you want first-party domains, create an ACM certificate in us-east-1 and rerun this script with -CertificateArn and aliases."
Write-Host "  2. Point Route 53 aliases or CNAMEs at the CloudFront domains above."
Write-Host "  3. Wait for CloudFront deployment to finish, then test platform and booking routes through CloudFront instead of the direct API endpoints."







