package com.leveragy.service;

import com.leveragy.dto.UpdateAnalysisResultRequest;
import com.leveragy.entity.UrlAnalysis;
import com.leveragy.repository.UrlAnalysisRepository;
import org.springframework.stereotype.Service;

/**
 * 저장만 담당한다("4번 - Frontend·DB·제보"). 실제 URL/페이지 판정은
 * backend 오케스트레이터가 ml-service/sandbox/multimodal-service를 호출해서
 * 계산하고, 이 서비스는 그 결과를 받아 저장만 한다(보고서 5장 비동기 Job 흐름).
 *
 * 1. createPendingAnalysis: backend가 분석을 시작할 때 즉시 id를 돌려주기 위해
 *    PROCESSING 행부터 만든다.
 * 2. completeAnalysis: backend가 실제 분석을 끝내면 같은 행에 결과를 채운다.
 */
@Service
public class AnalysisService {

    private final UrlAnalysisRepository urlAnalysisRepository;

    public AnalysisService(UrlAnalysisRepository urlAnalysisRepository) {
        this.urlAnalysisRepository = urlAnalysisRepository;
    }

    public UrlAnalysis createPendingAnalysis(String url) {
        UrlAnalysis analysis = new UrlAnalysis();
        analysis.setUrl(url);
        analysis.setProcessingStatus("PROCESSING");
        return urlAnalysisRepository.save(analysis);
    }

    public UrlAnalysis completeAnalysis(Long id, UpdateAnalysisResultRequest request) {
        UrlAnalysis analysis = urlAnalysisRepository.findById(id)
                .orElseThrow(() -> new AnalysisNotFoundException(id));

        analysis.setRiskScore(request.getRiskScore());
        analysis.setMlResult(request.getMlResult());
        analysis.setMultimodalResult(request.getMultimodalResult());
        analysis.setXaiResult(request.getXaiResult());
        analysis.setScreenshotData(request.getScreenshotData());
        analysis.setFinalResult(request.getFinalResult());
        analysis.setProcessingStatus(request.getProcessingStatus());

        return urlAnalysisRepository.save(analysis);
    }

    public static class AnalysisNotFoundException extends RuntimeException {
        public AnalysisNotFoundException(Long id) {
            super("분석 id " + id + "를 찾을 수 없습니다.");
        }
    }
}
