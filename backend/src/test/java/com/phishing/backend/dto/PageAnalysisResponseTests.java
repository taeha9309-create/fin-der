package com.phishing.backend.dto;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class PageAnalysisResponseTests {

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Test
    void deserializesCurrentMultimodalServiceContract() throws Exception {
        String json = """
                {
                  "analysisId": "analysis-123",
                  "pageRiskScore": 92,
                  "verdict": "PHISHING",
                  "impersonation": {
                    "detected": true,
                    "brand": "KB국민은행",
                    "category": "FINANCIAL_INSTITUTION"
                  },
                  "credentialIntent": {
                    "detected": true,
                    "types": ["PASSWORD", "OTP"]
                  },
                  "domainAnalysis": {
                    "currentDomain": "fake-bank.example",
                    "officialDomains": ["kbstar.com"],
                    "domainBrandMismatch": true
                  },
                  "behaviorAnalysis": {
                    "financialActionRequest": false,
                    "externalContactRequest": true,
                    "downloadRequest": false
                  },
                  "detectedSignals": ["BRAND_DOMAIN_MISMATCH", "PASSWORD_FIELD"],
                  "reasons": ["공식 도메인과 현재 도메인이 일치하지 않습니다."],
                  "confidence": 0.91
                }
                """;

        PageAnalysisResponse response = objectMapper.readValue(json, PageAnalysisResponse.class);

        assertThat(response.analysisId()).isEqualTo("analysis-123");
        assertThat(response.pageRiskScore()).isEqualTo(92);
        assertThat(response.impersonation().brand()).isEqualTo("KB국민은행");
        assertThat(response.credentialIntent().types()).containsExactly("PASSWORD", "OTP");
        assertThat(response.domainAnalysis().domainBrandMismatch()).isTrue();
        assertThat(response.detectedSignals()).contains("BRAND_DOMAIN_MISMATCH");
        assertThat(response.confidence()).isEqualTo(0.91);
    }
}
