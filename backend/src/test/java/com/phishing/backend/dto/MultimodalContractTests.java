package com.phishing.backend.dto;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import java.util.List;
import java.util.Map;
import static org.assertj.core.api.Assertions.assertThat;

class MultimodalContractTests {
    private final ObjectMapper mapper = new ObjectMapper();
    @Test void serializesCanonicalInputContract() throws Exception {
        var request = new MultimodalRequest("a-1", "https://requested.test", "https://final.test", 200,
                new MultimodalRequest.Page("title", "visible", "<p>visible</p>"), List.of(Map.of("type", "password")),
                List.of(), List.of(Map.of("href", "/help")), Map.of("downloadDetected", false),
                List.of(Map.of("url", "https://final.test")), "base64", null);
        String json = mapper.writeValueAsString(request);
        assertThat(json).contains("\"analysisId\":\"a-1\"", "\"visibleText\":\"visible\"", "\"inputs\"", "\"network\"", "\"redirectChain\"", "\"screenshot\":\"base64\"");
    }
    @Test void deserializesCanonicalOutputContract() throws Exception {
        String json = """
                {"analysisId":"a-1","pageRiskScore":91,"verdict":"PHISHING","impersonation":{"detected":true,"brand":"KB","category":"FINANCIAL_INSTITUTION"},"credentialIntent":{"detected":true,"types":["PASSWORD","OTP"]},"domainAnalysis":{"currentDomain":"fake.test","officialDomains":["kbstar.com"],"domainBrandMismatch":true},"behaviorAnalysis":{"financialActionRequest":false,"externalContactRequest":false,"downloadRequest":false},"detectedSignals":["PASSWORD_FIELD"],"reasons":["reason"],"confidence":0.9}
                """;
        var response = mapper.readValue(json, MultimodalResponse.class);
        assertThat(response.analysisId()).isEqualTo("a-1");
        assertThat(response.pageRiskScore()).isEqualTo(91);
        assertThat(response.credentialIntent().types()).containsExactly("PASSWORD", "OTP");
    }
}
