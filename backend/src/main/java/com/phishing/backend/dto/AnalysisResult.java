package com.phishing.backend.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

@JsonIgnoreProperties(ignoreUnknown = true)
public record AnalysisResult(
        Long id,
        String url,
        Integer riskScore,
        String mlResult,
        String multimodalResult,
        String xaiResult,
        String finalResult,
        String createdAt
) {
}
