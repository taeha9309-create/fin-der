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

import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.time.Duration;

/**
 * 비동기 분석 Job(보고서 5장): db-api에 PROCESSING 행을 즉시 만들어 id를 돌려주고,
 * 실제 파이프라인(ml-service → 필요시 sandbox → multimodal-service)은 백그라운드에서
 * 계속 실행한 뒤 db-api를 PATCH로 채운다. 프론트는 GET /api/analyze/{id}를 폴링한다.
 *
 * 2차(Sandbox+multimodal-service)가 실행되어 결론을 냈다면 그 등급·점수가 최종값이
 * 된다 - 1차보다 위험하다고 볼 때뿐 아니라 안전하다고 볼 때도 반영된다(resolveFinalResult
 * 참고). 2차가 생략됐거나(risk_score가 안전 임계치 이하), 호출이 실패했거나, 페이지를
 * 충분히 수집하지 못해 UNKNOWN이 나온 경우에는 1차(ml-service) 결과를 그대로 쓴다.
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

        FinalResult finalResult = resolveFinalResult(combined);

        UpdateAnalysisResultRequest patch = new UpdateAnalysisResultRequest(
                finalResult.riskScore(),
                writeJson(combined.ml),
                writeJson(buildMultimodalResult(combined)),
                writeJson(combined.ml.xaiReasons()),
                screenshotData,
                finalResult.label(),
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

    private static final List<String> SEVERITY_ORDER = List.of("NORMAL", "SUSPICIOUS", "PHISHING");

    /**
     * 2차가 1차보다 위험도를 낮추는(등급을 내리는) 경우, 그 판단을 얼마나 확신하는지
     * (multimodal의 confidence)가 이 값 미만이면 신뢰하지 않는다 - 예를 들어 PhishTank의
     * allegro.01201290.beauty처럼 피싱 페이지가 아직 안 올라갔거나 이미 내려가서 빈
     * 서버 기본 화면만 보이는 경우, 2차는 "지금 화면엔 위험한 게 없다"(confidence 0.55
     * 수준)고만 말할 뿐인데, 1차가 도메인 자체(브랜드명+숫자+저가 TLD 조합)로 이미 0.999
     * 확신을 갖고 PHISHING이라 판단한 걸 낮은 확신도의 2차 판단으로 뭉개면 안 된다.
     * 반대로 2차가 위험도를 올리는(에스컬레이션) 경우는 확신도와 무관하게 항상 반영한다 -
     * 위험 신호를 놓치는 것보다 과탐지가 안전 도구 입장에서 덜 위험하기 때문이다.
     */
    private static final double STAGE2_DOWNGRADE_CONFIDENCE_FLOOR = 0.6;

    private static int severityRank(String label) {
        int index = SEVERITY_ORDER.indexOf(label == null ? null : label.toUpperCase(Locale.ROOT));
        return Math.max(index, 0);
    }

    /**
     * 2차가 화면·DOM까지 보고 실제로 결론(NORMAL/SUSPICIOUS/PHISHING)을 냈다면, URL
     * 문자열만 본 1차보다 신뢰도가 높다고 보고 2차의 등급·점수를 그대로 최종값으로 쓴다.
     * 2차가 안전하다고 판단하면 1차가 이미 PHISHING이었어도 등급이 내려갈 수 있다 -
     * 예전에는 2차가 PHISHING이라고 할 때만 등급을 올려주는 편도(OR) 로직이었다(BUG-05).
     * 다만 등급을 내리는 판단은 2차 자신의 confidence가 낮으면 받아들이지 않고 1차를
     * 그대로 쓴다(STAGE2_DOWNGRADE_CONFIDENCE_FLOOR 참고) - 등급을 올리는 판단은 항상
     * 반영한다. 2차가 실행되지 않았거나(안전 임계치 이하라 스킵), 실패했거나, 수집
     * 실패로 UNKNOWN을 낸 경우에는 그 판단을 신뢰할 근거가 없으므로 1차 결과를 그대로 쓴다.
     */
    FinalResult resolveFinalResult(CombinedResult combined) {
        if (combined.multimodal == null || "UNKNOWN".equalsIgnoreCase(combined.multimodal.verdict())) {
            return new FinalResult(combined.ml.label(), combined.ml.riskScore());
        }

        boolean isDowngrade = severityRank(combined.multimodal.verdict()) < severityRank(combined.ml.label());
        Double confidence = combined.multimodal.confidence();
        boolean downgradeConfidenceTooLow = confidence == null || confidence < STAGE2_DOWNGRADE_CONFIDENCE_FLOOR;
        if (isDowngrade && downgradeConfidenceTooLow) {
            return new FinalResult(combined.ml.label(), combined.ml.riskScore());
        }

        return new FinalResult(combined.multimodal.verdict(), combined.multimodal.pageRiskScore());
    }

    record FinalResult(String label, Integer riskScore) {
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

    record CombinedResult(
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
