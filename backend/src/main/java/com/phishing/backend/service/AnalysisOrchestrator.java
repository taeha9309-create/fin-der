package com.phishing.backend.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.phishing.backend.dto.AnalysisResult;
import com.phishing.backend.dto.AnalyzeRequest;
import com.phishing.backend.dto.MlServiceResponse;
import com.phishing.backend.dto.MultimodalRequest;
import com.phishing.backend.dto.MultimodalResponse;
import com.phishing.backend.dto.PageAnalysisV2;
import com.phishing.backend.dto.SandboxResponse;
import com.phishing.backend.dto.UpdateAnalysisResultRequest;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;
import reactor.core.scheduler.Schedulers;

import java.util.ArrayList;
import java.util.List;
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
 * multimodal-service 응답(v1, 상세 계약)은 팀 보고서 7장의 평탄화 계약(v2)으로
 * 변환해서 저장한다 - db/CONTRACT_HISTORY.md의 v1→v2 매핑을 그대로 따른다.
 */
@Service
public class AnalysisOrchestrator {

    private final WebClient mlServiceWebClient;
    private final WebClient dbApiWebClient;
    private final WebClient multimodalWebClient;
    private final SandboxService sandboxService;
    private final ObjectMapper objectMapper;

    public AnalysisOrchestrator(
            WebClient mlServiceWebClient,
            WebClient dbApiWebClient,
            WebClient multimodalWebClient,
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
                combined.sandbox.requestedUrl(),
                combined.sandbox.finalUrl(),
                combined.sandbox.statusCode(),
                combined.sandbox.title(),
                combined.sandbox.html(),
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
     * multimodal-service가 응답했으면 팀 보고서 7장 계약(v2)으로 변환해서 반환한다.
     * Sandbox는 붙었지만 multimodal-service가 실패/미설정이면 수집 상태만 기록한다.
     */
    private Object buildMultimodalResult(CombinedResult combined) {
        if (combined.multimodal != null) {
            return toPageAnalysis(combined.multimodal, combined.sandbox);
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

    /**
     * multimodal-service는 사칭 브랜드명만 알려주고 공식 도메인과의 비교는 하지 않는다
     * ("공식기관 Reference DB"는 3번 AI가 관리하기로 되어 있었지만 현재 구현엔 없음).
     * 그래서 브랜드명 → 공식 도메인 매핑은 ml-service/data/financial_brands.csv와
     * 같은 목록을 여기서도 참고해 backend에서 직접 비교한다.
     */
    private static final Map<String, String> OFFICIAL_DOMAINS = Map.ofEntries(
            Map.entry("KB국민은행", "kbstar.com"),
            Map.entry("신한은행", "shinhan.com"),
            Map.entry("우리은행", "wooribank.com"),
            Map.entry("하나은행", "kebhana.com"),
            Map.entry("NH농협은행", "nhbank.com"),
            Map.entry("IBK기업은행", "ibk.co.kr"),
            Map.entry("카카오뱅크", "kakaobank.com"),
            Map.entry("케이뱅크", "kbanknow.com"),
            Map.entry("토스뱅크", "tossbank.com"),
            Map.entry("우체국예금보험", "epostbank.go.kr"),
            Map.entry("서민금융진흥원", "kinfa.or.kr"),
            Map.entry("소상공인시장진흥공단", "semas.or.kr"),
            Map.entry("정부24", "gov.kr")
    );

    private PageAnalysisV2 toPageAnalysis(MultimodalResponse response, SandboxResponse sandbox) {
        String impersonatedBrand = response.impersonatedBrand();
        boolean credentialIntent = response.credentialRequest();
        String currentDomain = extractHost(sandbox != null ? sandbox.finalUrl() : null);
        String officialDomain = impersonatedBrand != null ? OFFICIAL_DOMAINS.get(impersonatedBrand) : null;
        boolean domainBrandMismatch = officialDomain != null
                && currentDomain != null
                && !currentDomain.toLowerCase().contains(officialDomain.toLowerCase());

        List<String> credentialTypes = credentialIntent ? List.of("CREDENTIAL") : List.of();
        List<String> detectedSignals = buildDetectedSignals(response, domainBrandMismatch);
        Map<String, Object> domSummary = buildApproximateDomSummary(response);

        return new PageAnalysisV2(
                response.riskScore(),
                impersonatedBrand,
                credentialIntent,
                domainBrandMismatch,
                response.evidence(),
                currentDomain,
                officialDomain,
                credentialTypes,
                detectedSignals,
                domSummary
        );
    }

    private List<String> buildDetectedSignals(MultimodalResponse response, boolean domainBrandMismatch) {
        List<String> signals = new ArrayList<>();
        if (response.credentialRequest()) signals.add("CREDENTIAL_REQUEST");
        if (response.financialActionRequest()) signals.add("FINANCIAL_ACTION_REQUEST");
        if (response.appInstallRequest()) signals.add("DOWNLOAD_REQUEST");
        if (response.externalContactRequest()) signals.add("EXTERNAL_CONTACT");
        if (response.impersonatedBrand() != null) signals.add("BRAND_IMPERSONATION");
        if (domainBrandMismatch) signals.add("BRAND_DOMAIN_MISMATCH");
        return signals;
    }

    private Map<String, Object> buildApproximateDomSummary(MultimodalResponse response) {
        // multimodal-service 응답에는 원시 DOM 필드 개수가 없어 boolean 신호 기반으로
        // 최소한만 채운다. Sandbox가 입력 필드 통계를 직접 넘겨주면 실측값으로 교체한다.
        boolean hasForm = response.credentialRequest();

        java.util.LinkedHashMap<String, Object> summary = new java.util.LinkedHashMap<>();
        summary.put("passwordFields", hasForm ? 1 : 0);
        summary.put("otpFields", 0);
        summary.put("textFields", 0);
        summary.put("formCount", hasForm ? 1 : 0);
        summary.put("formMethod", hasForm ? "POST" : null);
        summary.put("formAction", null);
        summary.put("externalDomainLinks", response.externalContactRequest() ? 1 : 0);
        summary.put("externalContactLinks", response.externalContactRequest() ? 1 : 0);
        return summary;
    }

    private String extractHost(String url) {
        if (url == null) return null;
        try {
            String host = java.net.URI.create(url).getHost();
            return host != null ? host : url;
        } catch (Exception e) {
            return url;
        }
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
