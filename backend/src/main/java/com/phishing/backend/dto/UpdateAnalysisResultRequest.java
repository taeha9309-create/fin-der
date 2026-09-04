package com.phishing.backend.dto;

/** db-api의 PATCH /api/analyze/{id}로 보내는 요청 본문. */
public record UpdateAnalysisResultRequest(
        Integer riskScore,
        String mlResult,
        String multimodalResult,
        String xaiResult,
        String screenshotData,
        String finalResult,
        String processingStatus
) {
}
