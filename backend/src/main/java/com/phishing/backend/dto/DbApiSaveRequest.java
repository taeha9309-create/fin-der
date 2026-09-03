package com.phishing.backend.dto;

public record DbApiSaveRequest(
        String url,
        Integer riskScore,
        String mlResult,
        String multimodalResult,
        String xaiResult,
        String finalResult
) {
}
