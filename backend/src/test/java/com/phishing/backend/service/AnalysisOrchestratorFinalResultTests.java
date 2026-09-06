package com.phishing.backend.service;

import com.phishing.backend.dto.MlServiceResponse;
import com.phishing.backend.dto.MultimodalResponse;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * BUG-05 회귀 테스트: 2차(Sandbox+multimodal-service)가 실행되면 그 등급·점수가
 * 최종값이 되어야 한다 - 예전에는 2차가 PHISHING이라고 할 때만 등급을 올려주는
 * 편도(OR) 로직이라, 2차가 안전하다고 판단해도 1차의 오탐이 그대로 화면에 남았다.
 */
class AnalysisOrchestratorFinalResultTests {

    private final AnalysisOrchestrator orchestrator =
            new AnalysisOrchestrator(null, null, null, null, null);

    @Test
    void usesStageOneWhenStageTwoDidNotRun() {
        var combined = new AnalysisOrchestrator.CombinedResult(ml(90, "PHISHING"), null, "not_required", null, null);

        var result = orchestrator.resolveFinalResult(combined);

        assertThat(result.label()).isEqualTo("PHISHING");
        assertThat(result.riskScore()).isEqualTo(90);
    }

    @Test
    void stageTwoCanDowngradeAStageOneFalsePositive() {
        var combined = new AnalysisOrchestrator.CombinedResult(ml(100, "PHISHING"), null, null, multimodal(3, "NORMAL"), null);

        var result = orchestrator.resolveFinalResult(combined);

        assertThat(result.label()).isEqualTo("NORMAL");
        assertThat(result.riskScore()).isEqualTo(3);
    }

    @Test
    void stageTwoCanEscalateAStageOneNormal() {
        var combined = new AnalysisOrchestrator.CombinedResult(ml(10, "NORMAL"), null, null, multimodal(95, "PHISHING"), null);

        var result = orchestrator.resolveFinalResult(combined);

        assertThat(result.label()).isEqualTo("PHISHING");
        assertThat(result.riskScore()).isEqualTo(95);
    }

    @Test
    void unknownStageTwoVerdictFallsBackToStageOneInsteadOfTreatingItAsSafe() {
        var combined = new AnalysisOrchestrator.CombinedResult(ml(60, "SUSPICIOUS"), null, null, multimodal(0, "UNKNOWN"), null);

        var result = orchestrator.resolveFinalResult(combined);

        assertThat(result.label()).isEqualTo("SUSPICIOUS");
        assertThat(result.riskScore()).isEqualTo(60);
    }

    @Test
    void failedStageTwoCallFallsBackToStageOne() {
        var combined = new AnalysisOrchestrator.CombinedResult(ml(45, "SUSPICIOUS"), null, "timeout", null, "connection refused");

        var result = orchestrator.resolveFinalResult(combined);

        assertThat(result.label()).isEqualTo("SUSPICIOUS");
        assertThat(result.riskScore()).isEqualTo(45);
    }

    @Test
    void lowConfidenceDowngradeFallsBackToStageOneInsteadOfClearingAConfidentPhishingCall() {
        // Regression: PhishTank's allegro.01201290.beauty currently serves an empty
        // default web-server page (the kit isn't live / was taken down), so stage 2
        // has nothing to see and reports NORMAL at only 0.55 confidence -- that must
        // not erase stage 1's 0.999-probability domain-squatting call.
        var combined = new AnalysisOrchestrator.CombinedResult(ml(100, "PHISHING"), null, null, multimodal(0, "NORMAL", 0.55), null);

        var result = orchestrator.resolveFinalResult(combined);

        assertThat(result.label()).isEqualTo("PHISHING");
        assertThat(result.riskScore()).isEqualTo(100);
    }

    @Test
    void highConfidenceDowngradeIsStillTrusted() {
        var combined = new AnalysisOrchestrator.CombinedResult(ml(100, "PHISHING"), null, null, multimodal(3, "NORMAL", 0.76), null);

        var result = orchestrator.resolveFinalResult(combined);

        assertThat(result.label()).isEqualTo("NORMAL");
        assertThat(result.riskScore()).isEqualTo(3);
    }

    @Test
    void lowConfidenceEscalationIsStillAppliedRegardlessOfConfidence() {
        // Escalating (raising the alarm) is always applied even at low confidence --
        // missing a real threat is worse than a false alarm for a safety tool.
        var combined = new AnalysisOrchestrator.CombinedResult(ml(10, "NORMAL"), null, null, multimodal(95, "PHISHING", 0.4), null);

        var result = orchestrator.resolveFinalResult(combined);

        assertThat(result.label()).isEqualTo("PHISHING");
        assertThat(result.riskScore()).isEqualTo(95);
    }

    @Test
    void missingConfidenceIsTreatedAsTooLowToTrustADowngrade() {
        var combined = new AnalysisOrchestrator.CombinedResult(ml(100, "PHISHING"), null, null, multimodal(5, "NORMAL", null), null);

        var result = orchestrator.resolveFinalResult(combined);

        assertThat(result.label()).isEqualTo("PHISHING");
        assertThat(result.riskScore()).isEqualTo(100);
    }

    private MlServiceResponse ml(int riskScore, String label) {
        return new MlServiceResponse(
                "https://example.com", "stage1", riskScore / 100.0, riskScore, label,
                true, List.of(), Map.of(), "test"
        );
    }

    private MultimodalResponse multimodal(int pageRiskScore, String verdict) {
        return multimodal(pageRiskScore, verdict, 0.8);
    }

    private MultimodalResponse multimodal(int pageRiskScore, String verdict, Double confidence) {
        return new MultimodalResponse(
                "analysis-id", pageRiskScore, verdict,
                new MultimodalResponse.Impersonation(false, null, null),
                new MultimodalResponse.CredentialIntent(false, List.of()),
                new MultimodalResponse.DomainAnalysis(null, List.of(), false),
                new MultimodalResponse.BehaviorAnalysis(false, false, false),
                new MultimodalResponse.DomSummary(0, 0, 0, 0, null, null, 0, 0),
                List.of(), List.of(), confidence
        );
    }
}
