package com.phishing.backend.dto;

import java.util.List;
import java.util.Map;

/**
 * multimodal-service(v1, 상세 계약)의 응답을 팀 보고서 7장 "권장 핵심 JSON 필드"
 * (페이지 분석 AI → Backend) 평탄화 계약으로 변환한 모양. db-api의
 * url_analysis.multimodal_result에 이 모양 그대로 저장한다.
 *
 * 계약 필드: pageRiskScore, impersonatedBrand, credentialIntent, domainBrandMismatch, reasons.
 * 나머지는 결과 화면(DOM 분석·공식기관 비교 카드)을 채우기 위한 계약 밖 보조 필드다.
 */
public record PageAnalysisV2(
        Integer pageRiskScore,
        String impersonatedBrand,
        boolean credentialIntent,
        boolean domainBrandMismatch,
        List<String> reasons,
        String currentDomain,
        String officialDomain,
        List<String> credentialTypes,
        List<String> detectedSignals,
        Map<String, Object> domSummary
) {
}
