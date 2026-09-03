package com.leveragy.service;

import com.leveragy.dto.AnalyzeRequest;
import com.leveragy.entity.UrlAnalysis;
import com.leveragy.repository.UrlAnalysisRepository;
import org.springframework.stereotype.Service;

import java.util.Arrays;
import java.util.List;

/**
 * backend(오케스트레이터)가 ml-service/sandbox 결과를 이미 계산해서 보내면
 * 그 값을 그대로 저장한다. riskScore/finalResult 등이 비어 있으면(단독 테스트 등)
 * 키워드 기반 목업 로직으로 대체한다.
 */
@Service
public class AnalysisService {

    private static final List<String> SUSPICIOUS_KEYWORDS = Arrays.asList(
            "login", "verify", "otp", "auth", "account", "secure",
            "국민", "신한", "우리", "하나", "토스", "카카오뱅크", "환급", "지원금"
    );

    private final UrlAnalysisRepository urlAnalysisRepository;

    public AnalysisService(UrlAnalysisRepository urlAnalysisRepository) {
        this.urlAnalysisRepository = urlAnalysisRepository;
    }

    public UrlAnalysis analyze(AnalyzeRequest request) {
        UrlAnalysis analysis = new UrlAnalysis();
        analysis.setUrl(request.getUrl());

        if (request.hasPrecomputedResult()) {
            analysis.setRiskScore(request.getRiskScore());
            analysis.setMlResult(request.getMlResult());
            analysis.setMultimodalResult(request.getMultimodalResult());
            analysis.setXaiResult(request.getXaiResult());
            analysis.setFinalResult(request.getFinalResult());
        } else {
            int riskScore = computeMockRiskScore(request.getUrl());
            String finalResult = riskScore >= 70 ? "PHISHING" : riskScore >= 40 ? "SUSPICIOUS" : "NORMAL";

            analysis.setRiskScore(riskScore);
            analysis.setMlResult("{\"note\":\"placeholder - XGBoost 연동 예정\"}");
            analysis.setMultimodalResult("{\"note\":\"placeholder - Multimodal 분석 연동 예정\"}");
            analysis.setXaiResult(buildMockXaiReasons(request.getUrl(), riskScore));
            analysis.setFinalResult(finalResult);
        }

        return urlAnalysisRepository.save(analysis);
    }

    private int computeMockRiskScore(String url) {
        String lower = url.toLowerCase();
        int score = 10;
        for (String keyword : SUSPICIOUS_KEYWORDS) {
            if (lower.contains(keyword.toLowerCase())) {
                score += 20;
            }
        }
        if (!lower.startsWith("https://")) {
            score += 15;
        }
        return Math.min(score, 100);
    }

    private String buildMockXaiReasons(String url, int riskScore) {
        StringBuilder sb = new StringBuilder("[");
        if (!url.toLowerCase().startsWith("https://")) {
            sb.append("\"HTTPS 미사용\",");
        }
        if (riskScore >= 40) {
            sb.append("\"금융기관 관련 키워드 포함\",");
        }
        sb.append("\"AI 파이프라인 연동 전 임시 결과\"]");
        return sb.toString();
    }
}
