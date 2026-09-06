package com.phishing.backend.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import java.util.List;

@JsonIgnoreProperties(ignoreUnknown = true)
public record MultimodalResponse(
        String analysisId, Integer pageRiskScore, String verdict,
        Impersonation impersonation, CredentialIntent credentialIntent,
        DomainAnalysis domainAnalysis, BehaviorAnalysis behaviorAnalysis,
        DomSummary domSummary,
        List<String> detectedSignals, List<String> reasons, Double confidence
) {
    public record Impersonation(Boolean detected, String brand, String category) {}
    public record CredentialIntent(Boolean detected, List<String> types) {}
    public record DomainAnalysis(String currentDomain, List<String> officialDomains, Boolean domainBrandMismatch) {}
    public record BehaviorAnalysis(Boolean financialActionRequest, Boolean externalContactRequest, Boolean downloadRequest) {}
    public record DomSummary(
            Integer passwordFields, Integer otpFields, Integer textFields,
            Integer formCount, String formMethod, String formAction,
            Integer externalDomainLinks, Integer externalContactLinks
    ) {}
}
