package com.phishing.backend.dto;

import com.fasterxml.jackson.annotation.JsonAlias;
import java.io.Serializable;
import java.util.List;
import java.util.Map;

public record UrlAnalysisResponse(
        String url,
        String stage,
        @JsonAlias("service_mode")
        String serviceMode,
        @JsonAlias("risk_probability")
        Double riskProbability,
        @JsonAlias("risk_score")
        Integer riskScore,
        String label,
        @JsonAlias("requires_deep_analysis")
        Boolean requiresDeepAnalysis,
        @JsonAlias("xai_reasons")
        List<Map<String, Object>> xaiReasons,
        @JsonAlias("model_version")
        String modelVersion
) implements Serializable {
}
