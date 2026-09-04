$ErrorActionPreference = "Stop"
$OutputEncoding = [System.Text.UTF8Encoding]::new()

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendPort = if ($env:BACKEND_PORT) { $env:BACKEND_PORT } else { "8080" }
$dbApiPort = if ($env:DB_API_PORT) { $env:DB_API_PORT } else { "8081" }
$frontendPort = if ($env:FRONTEND_PORT) { $env:FRONTEND_PORT } else { "3000" }
$multimodalPort = if ($env:MULTIMODAL_SERVICE_PORT) { $env:MULTIMODAL_SERVICE_PORT } else { "8002" }
$sandboxPort = if ($env:SANDBOX_SERVICE_PORT) { $env:SANDBOX_SERVICE_PORT } else { "8003" }

$backendBaseUrl = "http://localhost:$backendPort"
$syncApiUrl = "$backendBaseUrl/api/v1/url-analysis"
$asyncApiUrl = "$backendBaseUrl/api/analyze"
$dbApiUrl = "http://localhost:$dbApiPort/api"
$sandboxApiUrl = "http://localhost:$sandboxPort/analyze"
$pollTimeoutSeconds = 75
$requiredServices = @(
    "database", "db-api", "ml-service", "sandbox", "multimodal-service",
    "page-ai-mock", "url-ai-mock", "backend", "frontend"
)

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}

function Assert-ContainerFile {
    param([string]$Service, [string]$Path, [string]$Description)
    docker compose exec -T $Service test -f $Path
    Assert-True ($LASTEXITCODE -eq 0) "$Description 파일을 찾을 수 없습니다: $Path"
}

function Convert-ErrorBody {
    param($ErrorRecord)
    if ([string]::IsNullOrWhiteSpace($ErrorRecord.ErrorDetails.Message)) { return $null }
    return $ErrorRecord.ErrorDetails.Message | ConvertFrom-Json
}

function Wait-BackendReady {
    param([int]$TimeoutSeconds = 60)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        try {
            $health = Invoke-RestMethod -Uri "$backendBaseUrl/health" -Method Get -TimeoutSec 2
            if ($health.status -eq "UP") { return }
        } catch {
        }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)
    throw "Backend가 ${TimeoutSeconds}초 안에 HTTP 요청 준비를 완료하지 못했습니다."
}

function Invoke-IntegratedAnalysis {
    param([string]$Url)
    $body = @{ url = $Url } | ConvertTo-Json
    $result = Invoke-RestMethod -Uri $syncApiUrl -Method Post -ContentType "application/json" -Body $body -TimeoutSec 75
    foreach ($field in @("id", "riskScore", "finalResult", "mlResult", "multimodalResult", "xaiResult")) {
        Assert-True ($null -ne $result.$field -and -not [string]::IsNullOrWhiteSpace([string]$result.$field)) "분석 응답에 $field 필드가 없습니다."
    }
    $stored = Invoke-RestMethod -Uri "$dbApiUrl/analyze/$($result.id)" -TimeoutSec 15
    Assert-True ($stored.id -eq $result.id -and $stored.url -eq $Url) "DB 저장 후 조회한 결과가 분석 응답과 일치하지 않습니다."
    return $stored
}

function Wait-AnalysisJob {
    param([string]$AnalysisId)
    $deadline = (Get-Date).AddSeconds($pollTimeoutSeconds)
    $result = $null
    do {
        Start-Sleep -Milliseconds 500
        $result = Invoke-RestMethod -Uri "$asyncApiUrl/$AnalysisId" -Method Get -TimeoutSec 10
    } while (@("COMPLETED", "FAILED") -notcontains $result.status -and (Get-Date) -lt $deadline)
    return $result
}

Push-Location $repoRoot
try {
    Write-Host "[1/11] 필수 컨테이너와 Backend 추적 헤더 확인"
    $runningServices = @(docker compose ps --status running --services)
    foreach ($service in $requiredServices) {
        Assert-True ($runningServices -contains $service) "$service 컨테이너가 실행 중이 아닙니다."
    }
    $backendContainerId = docker compose ps -q backend
    $backendLogConfig = docker inspect --format '{{json .HostConfig.LogConfig}}' $backendContainerId | ConvertFrom-Json
    Assert-True ($backendLogConfig.Type -eq "json-file") "Backend Docker 로그 드라이버가 json-file이 아닙니다."
    Assert-True (-not [string]::IsNullOrWhiteSpace($backendLogConfig.Config.'max-size')) "Backend Docker 로그 크기 제한이 없습니다."
    Assert-True (-not [string]::IsNullOrWhiteSpace($backendLogConfig.Config.'max-file')) "Backend Docker 로그 보관 개수 제한이 없습니다."
    Wait-BackendReady
    $smokeRequestId = "finder-smoke-$([Guid]::NewGuid().ToString('N'))"
    $healthResponse = Invoke-WebRequest -UseBasicParsing -Uri "$backendBaseUrl/health" -Method Get -Headers @{ "X-Request-Id" = $smokeRequestId }
    $responseRequestId = @($healthResponse.Headers["X-Request-Id"])[0]
    Assert-True (-not [string]::IsNullOrWhiteSpace($responseRequestId)) "X-Request-Id 응답 헤더가 없습니다."
    Assert-True ($responseRequestId -eq $smokeRequestId) "X-Request-Id 응답 헤더가 요청값과 일치하지 않습니다. 실제 값: $responseRequestId"

    Write-Host "[2/11] Frontend HTTP 응답 확인"
    $frontendResponse = Invoke-WebRequest -UseBasicParsing -Uri "http://localhost:$frontendPort/" -TimeoutSec 15
    Assert-True ($frontendResponse.StatusCode -eq 200) "Frontend가 HTTP 200을 반환하지 않았습니다."

    Write-Host "[3/11] 정상 URL 실제 통합 분석 및 DB 저장 확인"
    $normal = Invoke-IntegratedAnalysis "https://example.com"

    Write-Host "[4/11] 합성 의심 URL 실제 통합 분석 및 DB 저장 확인"
    $suspicious = Invoke-IntegratedAnalysis "https://example.com/secure-bank-login?verify=account"

    Write-Host "[5/11] Sandbox 수집 데이터와 저장 파일 조회 확인"
    $sandboxBody = @{ url = "https://example.com" } | ConvertTo-Json
    $sandboxResult = Invoke-RestMethod -Uri $sandboxApiUrl -Method Post -ContentType "application/json" -Body $sandboxBody -TimeoutSec 45
    Assert-True (-not [string]::IsNullOrWhiteSpace($sandboxResult.analysisId)) "Sandbox analysisId가 반환되지 않았습니다."
    Assert-True ($sandboxResult.schemaVersion -eq "1.0") "Sandbox 계약 버전이 올바르지 않습니다."
    Assert-True ($sandboxResult.collectionStatus -eq "COMPLETED") "Sandbox 수집 상태가 완료가 아닙니다."
    Assert-True ($sandboxResult.statusCode -eq 200) "예상하지 못한 대상 페이지 상태: $($sandboxResult.statusCode)"
    Assert-True (-not [string]::IsNullOrWhiteSpace($sandboxResult.html)) "HTML이 반환되지 않았습니다."
    Assert-True (-not [string]::IsNullOrWhiteSpace($sandboxResult.text)) "Text가 반환되지 않았습니다."
    Assert-True (-not [string]::IsNullOrWhiteSpace($sandboxResult.screenshotBase64)) "Screenshot이 반환되지 않았습니다."
    Assert-True ($sandboxResult.redirectChain.Count -ge 1) "Redirect 경로가 반환되지 않았습니다."
    Assert-True ($null -ne $sandboxResult.inputs) "입력 필드 목록이 반환되지 않았습니다."
    Assert-True ($null -ne $sandboxResult.forms) "Form 목록이 반환되지 않았습니다."
    Assert-True ($null -ne $sandboxResult.links) "링크 목록이 반환되지 않았습니다."
    Assert-True ($null -ne $sandboxResult.network.requests -and $sandboxResult.network.requests.Count -gt 0) "Network 요청이 수집되지 않았습니다."
    Assert-ContainerFile "sandbox" $sandboxResult.htmlPath "HTML"
    Assert-ContainerFile "sandbox" $sandboxResult.textPath "Text"
    Assert-ContainerFile "sandbox" $sandboxResult.screenshotPath "Screenshot"
    Assert-ContainerFile "sandbox" "/data/analyses/$($sandboxResult.analysisId)/metadata.json" "Metadata"
    $artifactBaseUrl = "$backendBaseUrl/api/analyses/$($sandboxResult.analysisId)"
    $artifactHtml = Invoke-WebRequest -UseBasicParsing -Uri "$artifactBaseUrl/html" -Method Get
    $artifactText = Invoke-WebRequest -UseBasicParsing -Uri "$artifactBaseUrl/text" -Method Get
    $artifactScreenshot = Invoke-WebRequest -UseBasicParsing -Uri "$artifactBaseUrl/screenshot" -Method Get
    $artifactMetadata = Invoke-RestMethod -Uri "$artifactBaseUrl/metadata" -Method Get
    Assert-True ($artifactHtml.StatusCode -eq 200) "HTML 조회 API가 실패했습니다."
    Assert-True ($artifactText.StatusCode -eq 200) "Text 조회 API가 실패했습니다."
    Assert-True ($artifactScreenshot.StatusCode -eq 200) "Screenshot 조회 API가 실패했습니다."
    Assert-True ($artifactMetadata.analysisId -eq $sandboxResult.analysisId) "Metadata의 analysisId가 일치하지 않습니다."

    Write-Host "[6/11] 비동기 모의 AI 분석 Job 완료 확인"
    $job = Invoke-RestMethod -Uri $asyncApiUrl -Method Post -ContentType "application/json" -Body $sandboxBody
    Assert-True (-not [string]::IsNullOrWhiteSpace($job.analysisId)) "비동기 analysisId가 반환되지 않았습니다."
    $jobResult = Wait-AnalysisJob $job.analysisId
    Assert-True ($jobResult.status -eq "COMPLETED") "비동기 분석이 ${pollTimeoutSeconds}초 안에 완료되지 않았습니다. 실제 상태: $($jobResult.status)"
    Assert-True ($null -eq $jobResult.failedStage) "완료된 분석에 failedStage가 포함되어 있습니다."
    Assert-True ($jobResult.result.analysisId -eq $job.analysisId) "Backend와 Sandbox의 analysisId가 일치하지 않습니다."
    Assert-True ($jobResult.urlAnalysis.stage -eq "URL_RULE_MOCK") "URL AI 모의 서비스 결과가 아닙니다. 실제 stage: $($jobResult.urlAnalysis.stage)"
    Assert-True ($null -ne $jobResult.urlAnalysis.riskScore) "URL 위험 점수가 반환되지 않았습니다."
    Assert-True (-not [string]::IsNullOrWhiteSpace($jobResult.result.text)) "비동기 분석 Text가 비어 있습니다."
    Assert-True ($jobResult.result.artifacts.html -eq "/api/analyses/$($job.analysisId)/html") "HTML 조회 URL이 올바르지 않습니다."
    Assert-True ($jobResult.result.artifacts.screenshot -eq "/api/analyses/$($job.analysisId)/screenshot") "Screenshot 조회 URL이 올바르지 않습니다."
    Assert-True ($jobResult.pageAnalysis.analysisId -eq $job.analysisId) "Backend와 페이지 AI의 analysisId가 일치하지 않습니다."
    Assert-True ($jobResult.pageAnalysis.serviceMode -eq "MOCK") "페이지 AI 모의 서비스 결과가 아닙니다."
    Assert-True ($jobResult.finalAnalysis.policyMode -eq "TEMPORARY") "임시 최종 점수 정책이 적용되지 않았습니다."
    Assert-True ($jobResult.finalAnalysis.riskScore -ge 0 -and $jobResult.finalAnalysis.riskScore -le 100) "최종 위험 점수 범위가 올바르지 않습니다."
    Assert-ContainerFile "backend" "/data/jobs/$($job.analysisId).job" "Job"

    Write-Host "[7/11] 페이지 AI 실패 시 중간 결과 보존 확인"
    $failureBody = @{ url = "https://example.com/?finder_page_ai_fail=1" } | ConvertTo-Json
    $failureJob = Invoke-RestMethod -Uri $asyncApiUrl -Method Post -ContentType "application/json" -Body $failureBody
    $failureResult = Wait-AnalysisJob $failureJob.analysisId
    Assert-True ($failureResult.status -eq "FAILED") "페이지 AI 실패 테스트가 FAILED로 종료되지 않았습니다. 실제 상태: $($failureResult.status)"
    Assert-True ($failureResult.errorCode -eq "PAGE_ANALYSIS_FAILED") "예상하지 못한 페이지 AI 오류 코드: $($failureResult.errorCode)"
    Assert-True ($failureResult.failedStage -eq "PAGE_ANALYZING") "실패 단계가 PAGE_ANALYZING이 아닙니다."
    Assert-True ($null -ne $failureResult.urlAnalysis -and $null -ne $failureResult.result) "페이지 AI 실패 후 중간 결과가 보존되지 않았습니다."
    Assert-True ($null -eq $failureResult.pageAnalysis -and $null -eq $failureResult.finalAnalysis) "페이지 AI 실패 후 잘못된 최종 결과가 생성되었습니다."

    Write-Host "[8/11] Sandbox 내부 주소 차단 확인"
    $blockedError = $null
    try {
        $blockedBody = @{ url = "http://127.0.0.1" } | ConvertTo-Json
        Invoke-RestMethod -Uri $sandboxApiUrl -Method Post -ContentType "application/json" -Body $blockedBody -TimeoutSec 15
    } catch {
        $blockedError = Convert-ErrorBody $_
    }
    Assert-True ($null -ne $blockedError) "내부 주소가 오류 응답 없이 처리되었습니다."
    Assert-True ($blockedError.code -eq "PRIVATE_ADDRESS_BLOCKED") "예상하지 못한 차단 코드: $($blockedError.code)"
    Assert-True ($blockedError.schemaVersion -eq "1.0" -and $blockedError.collectionStatus -eq "FAILED") "차단 응답 계약이 올바르지 않습니다."
    Assert-True (-not [string]::IsNullOrWhiteSpace($blockedError.analysisId)) "차단 응답에 analysisId가 없습니다."

    Write-Host "[9/11] Gemini 설정 또는 503 대체 응답 확인"
    $multimodalHealth = Invoke-RestMethod -Uri "http://localhost:$multimodalPort/health" -TimeoutSec 15
    if (-not $multimodalHealth.gemini_api_key_configured) {
        $fallbackVerified = $false
        try {
            $pixel = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
            $multimodalBody = @{ url = "https://example.com"; screenshot_base64 = $pixel; html = "<html><body>safe fixture</body></html>" } | ConvertTo-Json
            Invoke-RestMethod -Uri "http://localhost:$multimodalPort/v1/analyze" -Method Post -ContentType "application/json" -Body $multimodalBody -TimeoutSec 15
        } catch {
            if ([int]$_.Exception.Response.StatusCode -eq 503) { $fallbackVerified = $true }
        }
        Assert-True $fallbackVerified "GEMINI_API_KEY 미설정 시 503 대체 응답을 확인하지 못했습니다."
    }

    Write-Host "[10/11] 사용자 제보 API 확인"
    $reportBody = @{ url = "https://example.com"; reason = "local integration smoke test" } | ConvertTo-Json
    $report = Invoke-RestMethod -Uri "$dbApiUrl/reports" -Method Post -ContentType "application/json" -Body $reportBody -TimeoutSec 15
    Assert-True ($null -ne $report.id) "제보 API가 저장 id를 반환하지 않았습니다."

    Write-Host "[11/11] 존재하지 않는 비동기 Job 오류 추적 ID 확인"
    $notFound = $null
    try {
        Invoke-RestMethod -Uri "$asyncApiUrl/00000000-0000-4000-8000-000000000000" -Method Get
    } catch {
        $notFound = Convert-ErrorBody $_
    }
    Assert-True ($null -ne $notFound) "존재하지 않는 Job 조회가 성공으로 처리되었습니다."
    Assert-True ($notFound.code -eq "ANALYSIS_NOT_FOUND") "예상하지 못한 조회 오류 코드: $($notFound.code)"
    Assert-True (-not [string]::IsNullOrWhiteSpace($notFound.requestId)) "조회 오류 응답에 requestId가 없습니다."

    Write-Host ""
    Write-Host "모든 통합 smoke test가 성공했습니다."
    Write-Host "실제 정상 분석 ID: $($normal.id)"
    Write-Host "실제 합성 의심 분석 ID: $($suspicious.id)"
    Write-Host "Sandbox 수집 ID: $($sandboxResult.analysisId)"
    Write-Host "비동기 분석 ID: $($job.analysisId)"
    Write-Host "실패 분석 ID: $($failureJob.analysisId)"
} finally {
    Pop-Location
}
