package com.phishing.backend.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;

@JsonIgnoreProperties(ignoreUnknown = true)
public record MultimodalResponse(
        String verdict,
        @JsonProperty("risk_score") Integer riskScore,
        @JsonProperty("impersonation_type") String impersonationType,
        @JsonProperty("impersonated_brand") String impersonatedBrand,
        @JsonProperty("credential_request") boolean credentialRequest,
        @JsonProperty("financial_action_request") boolean financialActionRequest,
        @JsonProperty("app_install_request") boolean appInstallRequest,
        @JsonProperty("external_contact_request") boolean externalContactRequest,
        List<String> evidence
) {
}
