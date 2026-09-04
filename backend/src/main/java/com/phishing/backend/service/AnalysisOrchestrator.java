package com.phishing.backend.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.phishing.backend.dto.AnalysisResult;
import com.phishing.backend.dto.AnalyzeRequest;
import com.phishing.backend.dto.DbApiSaveRequest;
import com.phishing.backend.dto.MlServiceResponse;
import com.phishing.backend.dto.MultimodalRequest;
import com.phishing.backend.dto.MultimodalResponse;
import com.phishing.backend.dto.SandboxResponse;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.time.Duration;

/**
 * 1차 ML(ml-service)로 위험도를 계산하고, 정밀 분석이 필요한 URL만
 * Sandbox에서 Screenshot/HTML을 수집한 뒤 Multimodal(Gemini)로 사칭 여부를
 * 판단하고, db-api에 최종 결과를 저장한다.
 *
 * multimodal-service는 GEMINI_API_KEY가 없으면 503을 반환하는데, 이 경우에도
 * 파이프라인 전체가 죽지 않도록 하고 ml-service 판정만으로 finalResult를 정한다.
 * ml/multimodal을 합치는 규칙은 임시(OR 방식)이며, 정식 가중치 로직은
 * 3주차에 XAI 담당이 정하기로 되어 있다.
 */
@Service
public class AnalysisOrchestrator {

    private final WebClient mlServiceWebClient;
    private final WebClient dbApiWebClient;
    private final WebClient multimodalWebClient;
    private final SandboxService sandboxService;
    private final ObjectMapper objectMapper;

    public AnalysisOrchestrator(
            @Qualifier("mlServiceWebClient") WebClient mlServiceWebClient,
            @Qualifier("dbApiWebClient") WebClient dbApiWebClient,
            @Qualifier("multimodalWebClient") WebClient multimodalWebClient,
            SandboxService sandboxService,
            ObjectMapper objectMapper
    ) {
        this.mlServiceWebClient = mlServiceWebClient;
        this.dbApiWebClient = dbApiWebClient;
        this.multimodalWebClient = multimodalWebClient;
        this.sandboxService = sandboxService;
        this.objectMapper = objectMapper;
    }

    public Mono<AnalysisResult> analyze(AnalyzeRequest request) {
        return mlServiceWebClient.post()
                .uri("/v1/analyze")
                .bodyValue(request)
                .retrieve()
                .bodyToMono(MlServiceResponse.class)
                .timeout(Duration.ofSeconds(15))
                .flatMap(mlResult -> attachSandbox(request, mlResult))
                .flatMap(this::attachMultimodal)
                .flatMap(this::persist);
    }

    private Mono<CombinedResult> attachSandbox(AnalyzeRequest request, MlServiceResponse mlResult) {
        if (!mlResult.requiresDeepAnalysis()) {
            return Mono.just(new CombinedResult(mlResult, null, "not_required", null, null));
        }

        return sandboxService.analyze(request)
                .map(sandbox -> new CombinedResult(mlResult, sandbox, null, null, null))
                .onErrorResume(error -> Mono.just(new CombinedResult(mlResult, null, error.getMessage(), null, null)));
    }

    private Mono<CombinedResult> attachMultimodal(CombinedResult combined) {
        if (combined.sandbox == null) {
            return Mono.just(combined);
        }

        MultimodalRequest multimodalRequest = new MultimodalRequest(
                combined.sandbox.analysisId(),
                combined.sandbox.requestedUrl(),
                combined.sandbox.finalUrl(),
                combined.sandbox.statusCode(),
                new MultimodalRequest.Page(combined.sandbox.title(), combined.sandbox.text(), combined.sandbox.html()),
                combined.sandbox.inputs(),
                combined.sandbox.forms(),
                combined.sandbox.links(),
                combined.sandbox.network(),
                combined.sandbox.redirectChain(),
                combined.sandbox.screenshotBase64(),
                combined.sandbox.error()
        );

        return multimodalWebClient.post()
                .uri("/v1/analyze")
                .bodyValue(multimodalRequest)
                .retrieve()
                .bodyToMono(MultimodalResponse.class)
                .timeout(Duration.ofSeconds(30))
                .map(multimodal -> combined.withMultimodal(multimodal, null))
                .onErrorResume(error -> Mono.just(combined.withMultimodal(null, error.getMessage())));
    }

    private Mono<AnalysisResult> persist(CombinedResult combined) {
        DbApiSaveRequest saveRequest = new DbApiSaveRequest(
                combined.ml.url(),
                combined.ml.riskScore(),
                writeJson(combined.ml),
                writeJson(multimodalSummary(combined)),
                writeJson(combined.ml.xaiReasons()),
                combineFinalResult(combined)
        );

        return dbApiWebClient.post()
                .uri("/api/analyze")
                .bodyValue(saveRequest)
                .retrieve()
                .bodyToMono(AnalysisResult.class)
                .timeout(Duration.ofSeconds(10));
    }

    private String combineFinalResult(CombinedResult combined) {
        if (combined.multimodal == null) {
            return combined.ml.label();
        }

        boolean multimodalHighRisk = "PHISHING".equalsIgnoreCase(combined.multimodal.verdict());

        return multimodalHighRisk ? "PHISHING" : combined.ml.label();
    }

    private Object multimodalSummary(CombinedResult combined) {
        if (combined.multimodal != null) {
            return combined.multimodal;
        }
        if (combined.sandbox == null) {
            return new SandboxSummary(false, null, null, combined.sandboxError);
        }
        return new SandboxSummary(
                true,
                combined.sandbox.htmlSizeBytes(),
                combined.sandbox.screenshotSizeBytes(),
                combined.multimodalError != null ? combined.multimodalError : combined.sandbox.error()
        );
    }

    private String writeJson(Object value) {
        try {
            return objectMapper.writeValueAsString(value);
        } catch (Exception exception) {
            return "{}";
        }
    }

    private record CombinedResult(
            MlServiceResponse ml,
            SandboxResponse sandbox,
            String sandboxError,
            MultimodalResponse multimodal,
            String multimodalError
    ) {
        CombinedResult withMultimodal(MultimodalResponse multimodal, String multimodalError) {
            return new CombinedResult(ml, sandbox, sandboxError, multimodal, multimodalError);
        }
    }

    private record SandboxSummary(
            boolean collected,
            Integer htmlSizeBytes,
            Integer screenshotSizeBytes,
            String note
    ) {
    }
}
