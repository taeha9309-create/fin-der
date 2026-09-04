package com.phishing.backend.service;

import com.phishing.backend.dto.FinalAnalysisResponse;
import com.phishing.backend.dto.PageAnalysisResponse;
import com.phishing.backend.dto.UrlAnalysisResponse;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

@Component
public class FinalRiskPolicy {

    private static final double URL_WEIGHT = 0.4;
    private static final double PAGE_WEIGHT = 0.6;
    private static final String POLICY_VERSION = "final-fusion-v1";
    private static final Set<String> CRITICAL_CREDENTIAL_SIGNALS = Set.of(
            "PASSWORD_FIELD", "OTP_FIELD", "RESIDENT_NUMBER_FIELD",
            "ACCOUNT_FIELD", "CARD_FIELD", "PIN_FIELD"
    );

    public FinalAnalysisResponse combine(
            UrlAnalysisResponse urlAnalysis,
            PageAnalysisResponse pageAnalysis
    ) {
        int urlScore = boundedScore(urlAnalysis.riskScore());

        if (pageAnalysis == null || "UNKNOWN".equalsIgnoreCase(pageAnalysis.verdict())) {
            String mode = pageAnalysis == null ? "STAGE1_DIRECT" : "STAGE1_FALLBACK";
            return new FinalAnalysisResponse(
                    mode,
                    POLICY_VERSION,
                    urlScore,
                    normalizedVerdict(urlAnalysis.label(), urlScore),
                    urlScore,
                    null,
                    urlReasons(urlAnalysis, 3)
            );
        }

        int pageScore = boundedScore(pageAnalysis.pageRiskScore());
        int finalScore = (int) Math.round(urlScore * URL_WEIGHT + pageScore * PAGE_WEIGHT);
        Set<String> signals = pageAnalysis.detectedSignals() == null
                ? Set.of()
                : Set.copyOf(pageAnalysis.detectedSignals());

        if (signals.contains("BRAND_DOMAIN_MISMATCH")
                && signals.stream().anyMatch(CRITICAL_CREDENTIAL_SIGNALS::contains)) {
            finalScore = Math.max(finalScore, 85);
        } else if (signals.contains("EXTERNAL_FORM_ACTION")
                && signals.stream().anyMatch(CRITICAL_CREDENTIAL_SIGNALS::contains)) {
            finalScore = Math.max(finalScore, 80);
        } else if (urlScore >= 60 && pageScore >= 60) {
            finalScore = Math.min(100, finalScore + 10);
        }

        String verdict = finalScore >= 60
                ? "PHISHING"
                : finalScore >= 30 ? "SUSPICIOUS" : "NORMAL";

        LinkedHashSet<String> reasons = new LinkedHashSet<>();
        if (pageAnalysis.reasons() != null) {
            pageAnalysis.reasons().stream().limit(3).forEach(reasons::add);
        }
        reasons.addAll(urlReasons(urlAnalysis, 2));

        return new FinalAnalysisResponse(
                "STAGE1_STAGE2",
                POLICY_VERSION,
                finalScore,
                verdict,
                urlScore,
                pageScore,
                reasons.stream().limit(5).toList()
        );
    }

    private List<String> urlReasons(UrlAnalysisResponse analysis, int limit) {
        if (analysis.xaiReasons() == null) {
            return List.of();
        }
        List<String> reasons = new ArrayList<>();
        for (Map<String, Object> reason : analysis.xaiReasons()) {
            if (!"RISK_UP".equals(String.valueOf(reason.get("direction")))) {
                continue;
            }
            String message = String.valueOf(reason.getOrDefault("reason", "URL 위험 신호"));
            if (!message.isBlank() && !reasons.contains(message)) {
                reasons.add(message);
            }
            if (reasons.size() >= limit) {
                break;
            }
        }
        return List.copyOf(reasons);
    }

    private String normalizedVerdict(String label, int score) {
        if ("NORMAL".equalsIgnoreCase(label)
                || "SUSPICIOUS".equalsIgnoreCase(label)
                || "PHISHING".equalsIgnoreCase(label)) {
            return label.toUpperCase();
        }
        return score >= 70 ? "PHISHING" : score >= 40 ? "SUSPICIOUS" : "NORMAL";
    }

    private int boundedScore(Integer score) {
        if (score == null) {
            return 0;
        }
        return Math.max(0, Math.min(score, 100));
    }
}
