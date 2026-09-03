package com.phishing.backend.dto;

import java.io.Serializable;
import java.util.List;

public record FinalAnalysisResponse(
        String policyMode,
        String policyVersion,
        Integer riskScore,
        String verdict,
        Integer urlRiskScore,
        Integer pageRiskScore,
        List<String> reasons
) implements Serializable {
}
