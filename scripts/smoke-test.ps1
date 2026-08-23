$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
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

Push-Location $repoRoot

try {
    Write-Host "[1/7] Docker 컨테이너 상태 확인"
    $containers = @(docker compose ps --status running --services)
    Assert-True ($containers -contains "backend") "backend 컨테이너가 실행 중이 아닙니다."
    Assert-True ($containers -contains "sandbox") "sandbox 컨테이너가 실행 중이 아닙니다."

    Write-Host "[2/7] 동기 URL 분석 결과 확인"
    $normalBody = @{ url = "https://example.com" } | ConvertTo-Json
    $normalResult = Invoke-RestMethod -Uri $syncApiUrl -Method Post -ContentType "application/json" -Body $normalBody

    Assert-True (-not [string]::IsNullOrWhiteSpace($normalResult.analysisId)) "analysisId가 반환되지 않았습니다."
    Assert-True ($normalResult.statusCode -eq 200) "예상하지 못한 대상 페이지 상태: $($normalResult.statusCode)"
    Assert-True (-not [string]::IsNullOrWhiteSpace($normalResult.html)) "HTML이 반환되지 않았습니다."
    Assert-True (-not [string]::IsNullOrWhiteSpace($normalResult.text)) "Text가 반환되지 않았습니다."
    Assert-True (-not [string]::IsNullOrWhiteSpace($normalResult.screenshotBase64)) "Screenshot이 반환되지 않았습니다."
    Assert-True ($normalResult.redirectChain.Count -ge 1) "Redirect 경로가 반환되지 않았습니다."
    Assert-True ($normalResult.textSizeBytes -gt 0) "Text 크기가 올바르지 않습니다."

    Write-Host "[3/7] Sandbox 결과 파일 저장 확인"
    Assert-ContainerFile "sandbox" $normalResult.htmlPath "HTML"
    Assert-ContainerFile "sandbox" $normalResult.textPath "Text"
    Assert-ContainerFile "sandbox" $normalResult.screenshotPath "Screenshot"
    $metadataPath = "/data/analyses/$($normalResult.analysisId)/metadata.json"
    Assert-ContainerFile "sandbox" $metadataPath "Metadata"

    Write-Host "[4/7] 비동기 분석 Job 생성 및 완료 확인"
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
    Assert-True ($jobResult.result.analysisId -eq $job.analysisId) "Backend와 Sandbox의 analysisId가 일치하지 않습니다."
    Assert-True (-not [string]::IsNullOrWhiteSpace($jobResult.result.text)) "비동기 분석 Text가 비어 있습니다."

    Write-Host "[5/7] Backend Job 영속 파일 확인"
    $jobPath = "/data/jobs/$($job.analysisId).job"
    Assert-ContainerFile "backend" $jobPath "Job"

    Write-Host "[6/7] 내부 주소 차단 및 오류 추적 ID 확인"
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
    Assert-True (-not [string]::IsNullOrWhiteSpace($blockedError.analysisId)) "차단 응답에 analysisId가 없습니다."

    Write-Host "[7/7] 존재하지 않는 Job 조회 오류 확인"
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

    Write-Host ""
    Write-Host "모든 통합 smoke test가 성공했습니다."
    Write-Host "동기 분석 ID: $($normalResult.analysisId)"
    Write-Host "비동기 분석 ID: $($job.analysisId)"
} finally {
    Pop-Location
}
