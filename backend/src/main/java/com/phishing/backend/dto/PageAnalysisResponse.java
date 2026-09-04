package com.phishing.backend.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonAlias;

import java.io.Serializable;
import java.util.List;

@JsonIgnoreProperties(ignoreUnknown = true)
public record PageAnalysisResponse(
        String analysisId,
        @JsonAlias("risk_score")
        Integer pageRiskScore,
        String verdict,
        Impersonation impersonation,
        CredentialIntent credentialIntent,
        DomainAnalysis domainAnalysis,
        BehaviorAnalysis behaviorAnalysis,
        List<String> detectedSignals,
        @JsonAlias("evidence")
        List<String> reasons,
        Double confidence
) implements Serializable {

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record Impersonation(
            Boolean detected,
            String brand,
            String category
    ) implements Serializable {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record CredentialIntent(
            Boolean detected,
            List<String> types
    ) implements Serializable {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record DomainAnalysis(
            String currentDomain,
            List<String> officialDomains,
            Boolean domainBrandMismatch
    ) implements Serializable {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record BehaviorAnalysis(
            Boolean financialActionRequest,
            Boolean externalContactRequest,
            Boolean downloadRequest
    ) implements Serializable {
    }
}
