package com.phishing.backend.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;
import java.util.Map;

@JsonIgnoreProperties(ignoreUnknown = true)
public record MlServiceResponse(
        String url,
        String stage,
        @JsonProperty("risk_probability") Double riskProbability,
        @JsonProperty("risk_score") Integer riskScore,
        String label,
        @JsonProperty("requires_deep_analysis") boolean requiresDeepAnalysis,
        @JsonProperty("xai_reasons") List<XaiReason> xaiReasons,
        Map<String, Double> features,
        @JsonProperty("model_version") String modelVersion
) {
    @JsonIgnoreProperties(ignoreUnknown = true)
    public record XaiReason(
            String feature,
            String reason,
            Double contribution,
            String direction
    ) {
    }
}
