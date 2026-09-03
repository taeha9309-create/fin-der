package com.phishing.backend.dto;

import java.io.Serializable;
import java.util.List;

public record PageAnalysisResponse(
        String analysisId,
        String serviceMode,
        Integer pageRiskScore,
        String verdict,
        String impersonatedBrand,
        Boolean credentialIntent,
        List<String> credentialTypes,
        Boolean domainBrandMismatch,
        List<String> detectedSignals,
        List<String> reasons,
        Double confidence
) implements Serializable {
}
