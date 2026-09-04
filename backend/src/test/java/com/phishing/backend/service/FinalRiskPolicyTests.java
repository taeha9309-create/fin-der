package com.phishing.backend.service;

import com.phishing.backend.dto.FinalAnalysisResponse;
import com.phishing.backend.dto.PageAnalysisResponse;
import com.phishing.backend.dto.UrlAnalysisResponse;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class FinalRiskPolicyTests {

    private final FinalRiskPolicy policy = new FinalRiskPolicy();

    @Test
    void returnsStageOneDirectlyWhenPageAnalysisIsNotRequired() {
        FinalAnalysisResponse result = policy.combine(urlResult(85, "PHISHING"), null);

        assertThat(result.policyMode()).isEqualTo("STAGE1_DIRECT");
        assertThat(result.riskScore()).isEqualTo(85);
        assertThat(result.verdict()).isEqualTo("PHISHING");
        assertThat(result.pageRiskScore()).isNull();
        assertThat(result.reasons()).containsExactly("금융 브랜드명과 공식 도메인의 불일치");
    }

    @Test
    void ignoresUnknownPageScoreInsteadOfTreatingItAsSafe() {
        PageAnalysisResponse unknown = pageResult(0, "UNKNOWN", List.of(), List.of());

        FinalAnalysisResponse result = policy.combine(urlResult(55, "SUSPICIOUS"), unknown);

        assertThat(result.policyMode()).isEqualTo("STAGE1_FALLBACK");
        assertThat(result.riskScore()).isEqualTo(55);
        assertThat(result.verdict()).isEqualTo("SUSPICIOUS");
        assertThat(result.pageRiskScore()).isNull();
    }

    @Test
    void combinesScoresAndPlacesPageReasonsBeforeRiskIncreasingShapReasons() {
        PageAnalysisResponse page = pageResult(
                80, "PHISHING", List.of("PASSWORD_FIELD"),
                List.of("비밀번호 입력 필드가 확인되었습니다.")
        );

        FinalAnalysisResponse result = policy.combine(urlResult(50, "SUSPICIOUS"), page);

        assertThat(result.policyMode()).isEqualTo("STAGE1_STAGE2");
        assertThat(result.riskScore()).isEqualTo(68);
        assertThat(result.verdict()).isEqualTo("PHISHING");
        assertThat(result.reasons()).containsExactly(
                "비밀번호 입력 필드가 확인되었습니다.",
                "금융 브랜드명과 공식 도메인의 불일치"
        );
    }

    @Test
    void criticalMismatchAndCredentialCombinationCannotBeAveragedDown() {
        PageAnalysisResponse page = pageResult(
                65, "PHISHING", List.of("BRAND_DOMAIN_MISMATCH", "OTP_FIELD"),
                List.of("공식 도메인과 현재 도메인이 다릅니다.")
        );

        FinalAnalysisResponse result = policy.combine(urlResult(20, "NORMAL"), page);

        assertThat(result.riskScore()).isEqualTo(85);
        assertThat(result.verdict()).isEqualTo("PHISHING");
    }

    private UrlAnalysisResponse urlResult(int score, String label) {
        return new UrlAnalysisResponse(
                "https://example.com", "URL_XGBOOST", "MODEL", score / 100.0,
                score, label, "SUSPICIOUS".equals(label),
                List.of(
                        Map.of("reason", "금융 브랜드명과 공식 도메인의 불일치", "direction", "RISK_UP"),
                        Map.of("reason", "공식 금융 도메인에 가까움", "direction", "RISK_DOWN")
                ),
                "test"
        );
    }

    private PageAnalysisResponse pageResult(
            int score, String verdict, List<String> signals, List<String> reasons
    ) {
        return new PageAnalysisResponse(
                "analysis-id", "MODEL", score, verdict, null, false,
                List.of(), false, signals, reasons, 0.8
        );
    }
}
