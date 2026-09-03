package com.phishing.backend.service;

import com.phishing.backend.dto.FinalAnalysisResponse;
import com.phishing.backend.dto.PageAnalysisResponse;
import com.phishing.backend.dto.UrlAnalysisResponse;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;

@Component
public class FinalRiskPolicy {

    private static final double URL_WEIGHT = 0.4;
    private static final double PAGE_WEIGHT = 0.6;

    public FinalAnalysisResponse combine(
            UrlAnalysisResponse urlAnalysis,
            PageAnalysisResponse pageAnalysis
    ) {
        int urlScore = boundedScore(urlAnalysis.riskScore());
        int pageScore = boundedScore(pageAnalysis.pageRiskScore());
        int finalScore = (int) Math.round(urlScore * URL_WEIGHT + pageScore * PAGE_WEIGHT);
        String verdict = finalScore >= 70
                ? "PHISHING"
                : finalScore >= 40 ? "SUSPICIOUS" : "NORMAL";

        List<String> reasons = new ArrayList<>();
        if (urlAnalysis.xaiReasons() != null) {
            urlAnalysis.xaiReasons().stream()
                    .map(reason -> String.valueOf(reason.getOrDefault("reason", "URL 위험 신호")))
                    .limit(3)
                    .forEach(reasons::add);
        }
        if (pageAnalysis.reasons() != null) {
            pageAnalysis.reasons().stream().limit(3).forEach(reasons::add);
        }

        return new FinalAnalysisResponse(
                "TEMPORARY",
                "temporary-weighted-v1",
                finalScore,
                verdict,
                urlScore,
                pageScore,
                List.copyOf(reasons)
        );
    }

    private int boundedScore(Integer score) {
        if (score == null) {
            return 0;
        }
        return Math.max(0, Math.min(score, 100));
    }
}
