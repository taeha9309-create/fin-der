package com.phishing.backend.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import java.util.List;

@JsonIgnoreProperties(ignoreUnknown = true)
public record MultimodalResponse(
        String analysisId, Integer pageRiskScore, String verdict,
        Impersonation impersonation, CredentialIntent credentialIntent,
        DomainAnalysis domainAnalysis, BehaviorAnalysis behaviorAnalysis,
        List<String> detectedSignals, List<String> reasons, Double confidence
) {
    public record Impersonation(Boolean detected, String brand, String category) {}
    public record CredentialIntent(Boolean detected, List<String> types) {}
    public record DomainAnalysis(String currentDomain, List<String> officialDomains, Boolean domainBrandMismatch) {}
    public record BehaviorAnalysis(Boolean financialActionRequest, Boolean externalContactRequest, Boolean downloadRequest) {}
}
