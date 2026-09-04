package com.phishing.backend.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.phishing.backend.dto.AnalysisResult;
import com.phishing.backend.dto.AnalyzeRequest;
import com.phishing.backend.dto.MlServiceResponse;
import com.phishing.backend.dto.MultimodalRequest;
import com.phishing.backend.dto.MultimodalResponse;
import com.phishing.backend.dto.SandboxResponse;
import com.phishing.backend.dto.UpdateAnalysisResultRequest;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;
import reactor.core.scheduler.Schedulers;

import java.util.Map;
import java.time.Duration;

/**
 * 비동기 분석 Job(보고서 5장): db-api에 PROCESSING 행을 즉시 만들어 id를 돌려주고,
 * 실제 파이프라인(ml-service → 필요시 sandbox → multimodal-service)은 백그라운드에서
 * 계속 실행한 뒤 db-api를 PATCH로 채운다. 프론트는 GET /api/analyze/{id}를 폴링한다.
 *
 * multimodal-service는 GEMINI_API_KEY가 없으면 503을 반환하는데, 이 경우에도
 * 파이프라인 전체가 죽지 않도록 하고 ml-service 판정만으로 finalResult를 정한다.
 * ml/multimodal을 합치는 규칙은 임시(OR 방식)이며, 정식 가중치 로직은 XAI 담당이 정하기로 되어 있다.
 *
 * multimodal-service 응답은 이미 impersonation/domainAnalysis/credentialIntent를
 * 직접 계산해서 내려주므로 backend에서 별도로 브랜드-도메인 매핑을 하지 않고
 * 그대로 저장한다.
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

    /**
     * db-api에 PROCESSING 행을 만들어 즉시 반환하고, 실제 분석은 별도 구독으로
     * 백그라운드에서 이어간다(fire-and-forget) - 호출자를 기다리게 하지 않는다.
     */
    public Mono<AnalysisResult> analyze(AnalyzeRequest request) {
        return dbApiWebClient.post()
                .uri("/api/analyze")
                .bodyValue(request)
                .retrieve()
                .bodyToMono(AnalysisResult.class)
                .timeout(Duration.ofSeconds(10))
                .doOnNext(pending -> runPipeline(pending.id(), request)
                        .subscribeOn(Schedulers.boundedElastic())
                        .subscribe());
    }

    private Mono<Void> runPipeline(Long id, AnalyzeRequest request) {
        return mlServiceWebClient.post()
                .uri("/v1/analyze")
                .bodyValue(request)
                .retrieve()
                .bodyToMono(MlServiceResponse.class)
                .timeout(Duration.ofSeconds(15))
                .flatMap(mlResult -> attachSandbox(request, mlResult))
                .flatMap(this::attachMultimodal)
                .flatMap(combined -> complete(id, combined))
                .onErrorResume(error -> markFailed(id, error))
                .then();
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

    private Mono<AnalysisResult> complete(Long id, CombinedResult combined) {
        String screenshotData = (combined.sandbox != null && combined.sandbox.screenshotBase64() != null)
                ? "data:image/png;base64," + combined.sandbox.screenshotBase64()
                : null;

        UpdateAnalysisResultRequest patch = new UpdateAnalysisResultRequest(
                combined.ml.riskScore(),
                writeJson(combined.ml),
                writeJson(buildMultimodalResult(combined)),
                writeJson(combined.ml.xaiReasons()),
                screenshotData,
                combineFinalResult(combined),
                "COMPLETED"
        );

        return patchDbApi(id, patch);
    }

    private Mono<AnalysisResult> markFailed(Long id, Throwable error) {
        UpdateAnalysisResultRequest patch = new UpdateAnalysisResultRequest(
                null, null, writeJson(Map.of("error", String.valueOf(error.getMessage()))), null, null,
                "UNKNOWN", "FAILED"
        );
        return patchDbApi(id, patch);
    }

    private Mono<AnalysisResult> patchDbApi(Long id, UpdateAnalysisResultRequest patch) {
        return dbApiWebClient.patch()
                .uri("/api/analyze/{id}", id)
                .bodyValue(patch)
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

    /**
     * multimodal-service가 응답했으면 그 결과를 그대로 저장한다 - impersonation,
     * credentialIntent, domainAnalysis, behaviorAnalysis, reasons를 이미 multimodal-service가
     * 직접 계산해서 내려주므로 backend에서 다시 가공하지 않는다.
     * Sandbox는 붙었지만 multimodal-service가 실패/미설정이면 수집 상태만 기록한다.
     */
    private Object buildMultimodalResult(CombinedResult combined) {
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
