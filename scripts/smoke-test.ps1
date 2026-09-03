$ErrorActionPreference = "Stop"
$OutputEncoding = [System.Text.UTF8Encoding]::new()

$repoRoot = Split-Path -Parent $PSScriptRoot
$syncApiUrl = "http://localhost:8080/api/v1/url-analysis"
$asyncApiUrl = "http://localhost:8080/api/analyze"
$pollTimeoutSeconds = 45

function Assert-True {
    param([bool]$Condition, [string]$Message)

    if (-not $Condition) {
        throw $Message
    }
}

function Assert-ContainerFile {
    param([string]$Service, [string]$Path, [string]$Description)

    docker compose exec -T $Service test -f $Path
    Assert-True ($LASTEXITCODE -eq 0) "$Description 파일을 찾을 수 없습니다: $Path"
}

function Wait-BackendReady {
    param([int]$TimeoutSeconds = 30)

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $probeUrl = "http://localhost:8080/health"

    do {
        try {
            $health = Invoke-RestMethod -Uri $probeUrl -Method Get -TimeoutSec 2
            if ($health.status -eq "UP") {
                return
            }
        } catch {
        }

        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)

    throw "Backend가 ${TimeoutSeconds}초 안에 HTTP 요청 준비를 완료하지 못했습니다."
}

Push-Location $repoRoot

try {
    Write-Host "[1/8] Docker 컨테이너 상태 확인"
    $containers = @(docker compose ps --status running --services)
    Assert-True ($containers -contains "backend") "backend 컨테이너가 실행 중이 아닙니다."
    Assert-True ($containers -contains "sandbox") "sandbox 컨테이너가 실행 중이 아닙니다."
    Assert-True ($containers -contains "page-ai-mock") "page-ai-mock 컨테이너가 실행 중이 아닙니다."
    Assert-True ($containers -contains "url-ai-mock") "url-ai-mock 컨테이너가 실행 중이 아닙니다."
    $backendContainerId = docker compose ps -q backend
    $backendLogConfig = docker inspect --format '{{json .HostConfig.LogConfig}}' $backendContainerId | ConvertFrom-Json
    Assert-True ($backendLogConfig.Type -eq "json-file") "Backend Docker 로그 드라이버가 json-file이 아닙니다."
    Assert-True (-not [string]::IsNullOrWhiteSpace($backendLogConfig.Config.'max-size')) "Backend Docker 로그 크기 제한이 없습니다."
    Assert-True (-not [string]::IsNullOrWhiteSpace($backendLogConfig.Config.'max-file')) "Backend Docker 로그 보관 개수 제한이 없습니다."
    Wait-BackendReady
    $smokeRequestId = "finder-smoke-$([Guid]::NewGuid().ToString('N'))"
    $healthResponse = Invoke-WebRequest -UseBasicParsing -Uri "http://localhost:8080/health" -Method Get -Headers @{ "X-Request-Id" = $smokeRequestId }
    $responseRequestId = @($healthResponse.Headers["X-Request-Id"])[0]
    Assert-True (-not [string]::IsNullOrWhiteSpace($responseRequestId)) "X-Request-Id가 없습니다. 새 Backend 이미지를 빌드하고 컨테이너를 다시 생성해주세요."
    Assert-True ($responseRequestId -eq $smokeRequestId) "X-Request-Id 응답 헤더가 요청값과 일치하지 않습니다. 실제 값: $responseRequestId"

    Write-Host "[2/8] 동기 URL 분석 결과 확인"
    $normalBody = @{ url = "https://example.com" } | ConvertTo-Json
    $normalResult = Invoke-RestMethod -Uri $syncApiUrl -Method Post -ContentType "application/json" -Body $normalBody

    Assert-True (-not [string]::IsNullOrWhiteSpace($normalResult.analysisId)) "analysisId가 반환되지 않았습니다."
    Assert-True ($normalResult.statusCode -eq 200) "예상하지 못한 대상 페이지 상태: $($normalResult.statusCode)"
    Assert-True (-not [string]::IsNullOrWhiteSpace($normalResult.html)) "HTML이 반환되지 않았습니다."
    Assert-True (-not [string]::IsNullOrWhiteSpace($normalResult.text)) "Text가 반환되지 않았습니다."
    Assert-True (-not [string]::IsNullOrWhiteSpace($normalResult.screenshotBase64)) "Screenshot이 반환되지 않았습니다."
    Assert-True ($normalResult.redirectChain.Count -ge 1) "Redirect 경로가 반환되지 않았습니다."
    Assert-True ($normalResult.textSizeBytes -gt 0) "Text 크기가 올바르지 않습니다."
    Assert-True ($normalResult.schemaVersion -eq "1.0") "Sandbox 계약 버전이 올바르지 않습니다."
    Assert-True ($normalResult.collectionStatus -eq "COMPLETED") "Sandbox 수집 상태가 완료가 아닙니다."
    Assert-True ($null -ne $normalResult.inputs) "입력 필드 목록이 반환되지 않았습니다."
    Assert-True ($null -ne $normalResult.forms) "Form 목록이 반환되지 않았습니다."
    Assert-True ($null -ne $normalResult.links) "링크 목록이 반환되지 않았습니다."
    Assert-True ($null -ne $normalResult.network.requests) "Network 요청 목록이 반환되지 않았습니다."
    Assert-True ($normalResult.network.requests.Count -gt 0) "Network 요청이 수집되지 않았습니다."

    Write-Host "[3/8] Sandbox 결과 파일 저장 및 Backend 조회 API 확인"
    Assert-ContainerFile "sandbox" $normalResult.htmlPath "HTML"
    Assert-ContainerFile "sandbox" $normalResult.textPath "Text"
    Assert-ContainerFile "sandbox" $normalResult.screenshotPath "Screenshot"
    $metadataPath = "/data/analyses/$($normalResult.analysisId)/metadata.json"
    Assert-ContainerFile "sandbox" $metadataPath "Metadata"
    $artifactBaseUrl = "http://localhost:8080/api/analyses/$($normalResult.analysisId)"
    $artifactHtml = Invoke-WebRequest -UseBasicParsing -Uri "$artifactBaseUrl/html" -Method Get
    $artifactText = Invoke-WebRequest -UseBasicParsing -Uri "$artifactBaseUrl/text" -Method Get
    $artifactScreenshot = Invoke-WebRequest -UseBasicParsing -Uri "$artifactBaseUrl/screenshot" -Method Get
    $artifactMetadata = Invoke-RestMethod -Uri "$artifactBaseUrl/metadata" -Method Get
    Assert-True ($artifactHtml.StatusCode -eq 200) "HTML 조회 API가 실패했습니다."
    Assert-True ($artifactText.StatusCode -eq 200) "Text 조회 API가 실패했습니다."
    Assert-True ($artifactScreenshot.StatusCode -eq 200) "Screenshot 조회 API가 실패했습니다."
    Assert-True ($artifactMetadata.analysisId -eq $normalResult.analysisId) "Metadata의 analysisId가 일치하지 않습니다."

    Write-Host "[4/8] 비동기 분석 Job 생성 및 완료 확인"
    $job = Invoke-RestMethod -Uri $asyncApiUrl -Method Post -ContentType "application/json" -Body $normalBody
    Assert-True (-not [string]::IsNullOrWhiteSpace($job.analysisId)) "비동기 analysisId가 반환되지 않았습니다."

    $deadline = (Get-Date).AddSeconds($pollTimeoutSeconds)
    $jobResult = $null

    do {
        Start-Sleep -Milliseconds 500
        $jobResult = Invoke-RestMethod -Uri "$asyncApiUrl/$($job.analysisId)" -Method Get

        if ($jobResult.status -eq "FAILED") {
            throw "비동기 분석 실패: $($jobResult.errorCode) - $($jobResult.errorMessage)"
        }
    } while ($jobResult.status -ne "COMPLETED" -and (Get-Date) -lt $deadline)

    Assert-True ($jobResult.status -eq "COMPLETED") "비동기 분석이 ${pollTimeoutSeconds}초 안에 완료되지 않았습니다."
    Assert-True ($null -eq $jobResult.failedStage) "완료된 분석에 failedStage가 포함되어 있습니다."
    Assert-True ($jobResult.result.analysisId -eq $job.analysisId) "Backend와 Sandbox의 analysisId가 일치하지 않습니다."
    Assert-True ($jobResult.urlAnalysis.stage -eq "URL_RULE_MOCK") "URL AI 모의 서비스 결과가 아닙니다. 실제 stage: $($jobResult.urlAnalysis.stage)"
    Assert-True ($null -ne $jobResult.urlAnalysis.riskScore) "URL 위험 점수가 반환되지 않았습니다."
    Assert-True (-not [string]::IsNullOrWhiteSpace($jobResult.result.text)) "비동기 분석 Text가 비어 있습니다."
    Assert-True ($null -eq $jobResult.result.html) "비동기 결과에 원본 HTML이 포함되어 있습니다."
    Assert-True ($null -eq $jobResult.result.screenshotBase64) "비동기 결과에 Screenshot Base64가 포함되어 있습니다."
    Assert-True ($jobResult.result.artifacts.html -eq "/api/analyses/$($job.analysisId)/html") "HTML 조회 URL이 올바르지 않습니다."
    Assert-True ($jobResult.result.artifacts.screenshot -eq "/api/analyses/$($job.analysisId)/screenshot") "Screenshot 조회 URL이 올바르지 않습니다."
    Assert-True ($jobResult.pageAnalysis.analysisId -eq $job.analysisId) "Backend와 페이지 AI의 analysisId가 일치하지 않습니다."
    Assert-True ($jobResult.pageAnalysis.serviceMode -eq "MOCK") "페이지 AI 모의 서비스 결과가 아닙니다."
    Assert-True ($null -ne $jobResult.pageAnalysis.detectedSignals) "페이지 AI 신호 목록이 반환되지 않았습니다."
    Assert-True ($jobResult.finalAnalysis.policyMode -eq "TEMPORARY") "임시 최종 점수 정책이 적용되지 않았습니다."
    Assert-True ($jobResult.finalAnalysis.riskScore -ge 0 -and $jobResult.finalAnalysis.riskScore -le 100) "최종 위험 점수 범위가 올바르지 않습니다."
    Assert-True (@("NORMAL", "SUSPICIOUS", "PHISHING") -contains $jobResult.finalAnalysis.verdict) "최종 판정값이 올바르지 않습니다."

    Write-Host "[5/8] Backend Job 영속 파일 확인"
    $jobPath = "/data/jobs/$($job.analysisId).job"
    Assert-ContainerFile "backend" $jobPath "Job"

    Write-Host "[6/8] 페이지 AI 실패 시 중간 결과 보존 확인"
    $failureBody = @{ url = "https://example.com/?finder_page_ai_fail=1" } | ConvertTo-Json
    $failureJob = Invoke-RestMethod -Uri $asyncApiUrl -Method Post -ContentType "application/json" -Body $failureBody
    Assert-True (-not [string]::IsNullOrWhiteSpace($failureJob.analysisId)) "실패 테스트 analysisId가 반환되지 않았습니다."

    $failureDeadline = (Get-Date).AddSeconds($pollTimeoutSeconds)
    $failureResult = $null

    do {
        Start-Sleep -Milliseconds 500
        $failureResult = Invoke-RestMethod -Uri "$asyncApiUrl/$($failureJob.analysisId)" -Method Get
    } while (@("COMPLETED", "FAILED") -notcontains $failureResult.status -and (Get-Date) -lt $failureDeadline)

    Assert-True ($failureResult.status -eq "FAILED") "페이지 AI 실패 테스트가 FAILED로 종료되지 않았습니다. 실제 상태: $($failureResult.status)"
    Assert-True ($failureResult.errorCode -eq "PAGE_ANALYSIS_FAILED") "예상하지 못한 페이지 AI 오류 코드: $($failureResult.errorCode)"
    Assert-True ($failureResult.failedStage -eq "PAGE_ANALYZING") "실패 단계가 PAGE_ANALYZING이 아닙니다. 실제 단계: $($failureResult.failedStage)"
    Assert-True ($null -ne $failureResult.urlAnalysis) "페이지 AI 실패 후 URL 분석 결과가 보존되지 않았습니다."
    Assert-True ($null -ne $failureResult.result) "페이지 AI 실패 후 Sandbox 결과가 보존되지 않았습니다."
    Assert-True ($failureResult.result.collectionStatus -eq "COMPLETED") "보존된 Sandbox 결과가 완료 상태가 아닙니다."
    Assert-True ($null -eq $failureResult.pageAnalysis) "실패한 페이지 AI 결과가 저장되어 있습니다."
    Assert-True ($null -eq $failureResult.finalAnalysis) "페이지 AI 실패 후 최종 판정이 생성되었습니다."

    Write-Host "[7/8] 내부 주소 차단 및 오류 추적 ID 확인"
    $blockedBody = @{ url = "http://127.0.0.1" } | ConvertTo-Json
    $blockedError = $null

    try {
        Invoke-RestMethod -Uri $syncApiUrl -Method Post -ContentType "application/json" -Body $blockedBody
    } catch {
        if (-not [string]::IsNullOrWhiteSpace($_.ErrorDetails.Message)) {
            $blockedError = $_.ErrorDetails.Message | ConvertFrom-Json
        }
    }

    Assert-True ($null -ne $blockedError) "내부 주소가 오류 응답 없이 처리되었습니다."
    Assert-True ($blockedError.code -eq "PRIVATE_ADDRESS_BLOCKED") "예상하지 못한 차단 코드: $($blockedError.code)"
    Assert-True ($blockedError.schemaVersion -eq "1.0") "차단 응답의 계약 버전이 올바르지 않습니다."
    Assert-True ($blockedError.collectionStatus -eq "FAILED") "차단 응답의 수집 상태가 FAILED가 아닙니다."
    Assert-True (-not [string]::IsNullOrWhiteSpace($blockedError.analysisId)) "차단 응답에 analysisId가 없습니다."
    Assert-True (-not [string]::IsNullOrWhiteSpace($blockedError.requestId)) "차단 응답에 requestId가 없습니다."

    Write-Host "[8/8] 존재하지 않는 Job 조회 오류 확인"
    $notFound = $null

    try {
        Invoke-RestMethod -Uri "$asyncApiUrl/00000000-0000-4000-8000-000000000000" -Method Get
    } catch {
        if (-not [string]::IsNullOrWhiteSpace($_.ErrorDetails.Message)) {
            $notFound = $_.ErrorDetails.Message | ConvertFrom-Json
        }
    }

    Assert-True ($null -ne $notFound) "존재하지 않는 Job 조회가 성공으로 처리되었습니다."
    Assert-True ($notFound.code -eq "ANALYSIS_NOT_FOUND") "예상하지 못한 조회 오류 코드: $($notFound.code)"
    Assert-True (-not [string]::IsNullOrWhiteSpace($notFound.requestId)) "조회 오류 응답에 requestId가 없습니다."

    Write-Host ""
    Write-Host "모든 통합 smoke test가 성공했습니다."
    Write-Host "동기 분석 ID: $($normalResult.analysisId)"
    Write-Host "비동기 분석 ID: $($job.analysisId)"
    Write-Host "실패 분석 ID: $($failureJob.analysisId)"
} finally {
    Pop-Location
}
