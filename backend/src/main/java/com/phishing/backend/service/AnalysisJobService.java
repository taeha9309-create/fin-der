package com.phishing.backend.service;

import com.phishing.backend.dto.AnalysisJobResponse;
import com.phishing.backend.dto.AnalysisStatus;
import com.phishing.backend.dto.ArtifactLinks;
import com.phishing.backend.dto.FinalAnalysisResponse;
import com.phishing.backend.dto.PageAnalysisResponse;
import com.phishing.backend.dto.SandboxResponse;
import com.phishing.backend.dto.SandboxResultSummary;
import com.phishing.backend.dto.UrlAnalysisResponse;
import com.phishing.backend.exception.AnalysisTimeoutException;
import com.phishing.backend.exception.AnalysisQueueFullException;
import com.phishing.backend.exception.PageAnalysisException;
import com.phishing.backend.exception.UrlAnalysisException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClientRequestException;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import reactor.core.Exceptions;
import reactor.core.publisher.Mono;
import reactor.util.retry.Retry;

import java.time.Duration;
import java.time.Instant;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.TimeoutException;

@Service
public class AnalysisJobService {

    private static final Logger log = LoggerFactory.getLogger(AnalysisJobService.class);

    private final SandboxService sandboxService;
    private final UrlAnalysisService urlAnalysisService;
    private final PageAnalysisService pageAnalysisService;
    private final AnalysisJobStore jobStore;
    private final FinalRiskPolicy finalRiskPolicy;
    private final ConcurrentMap<String, AnalysisJobResponse> jobs = new ConcurrentHashMap<>();
    private final ConcurrentLinkedQueue<QueuedAnalysis> queue = new ConcurrentLinkedQueue<>();
    private final int maxConcurrentAnalyses;
    private final int maxQueuedAnalyses;
    private final int sandboxRetryCount;
    private final int timeoutSeconds;
    private final int jobRetentionHours;
    private int activeAnalyses;

    public AnalysisJobService(
            SandboxService sandboxService,
            UrlAnalysisService urlAnalysisService,
            PageAnalysisService pageAnalysisService,
            AnalysisJobStore jobStore,
            FinalRiskPolicy finalRiskPolicy,
            @Value("${analysis.max-concurrent:2}") int maxConcurrentAnalyses,
            @Value("${analysis.max-queued:20}") int maxQueuedAnalyses,
            @Value("${analysis.sandbox-retry-count:1}") int sandboxRetryCount,
            @Value("${analysis.timeout-seconds:90}") int timeoutSeconds,
            @Value("${analysis.job-retention-hours:24}") int jobRetentionHours
    ) {
        this.sandboxService = sandboxService;
        this.urlAnalysisService = urlAnalysisService;
        this.pageAnalysisService = pageAnalysisService;
        this.jobStore = jobStore;
        this.finalRiskPolicy = finalRiskPolicy;
        this.maxConcurrentAnalyses = requirePositive(maxConcurrentAnalyses, "analysis.max-concurrent");
        this.maxQueuedAnalyses = requirePositive(maxQueuedAnalyses, "analysis.max-queued");
        this.sandboxRetryCount = requireNonNegative(sandboxRetryCount, "analysis.sandbox-retry-count");
        this.timeoutSeconds = requirePositive(timeoutSeconds, "analysis.timeout-seconds");
        this.jobRetentionHours = requirePositive(jobRetentionHours, "analysis.job-retention-hours");
    }

    public synchronized AnalysisJobResponse create(String url) {
        if (queue.size() >= maxQueuedAnalyses) {
            throw new AnalysisQueueFullException();
        }

        String analysisId = UUID.randomUUID().toString();
        Instant now = Instant.now();
        AnalysisJobResponse pending = new AnalysisJobResponse(
                analysisId,
                AnalysisStatus.PENDING,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                now,
                now
        );
        jobs.put(analysisId, pending);
        jobStore.save(pending);
        queue.add(new QueuedAnalysis(analysisId, url));
        dispatchNext();

        log.info("analysis_job_created analysisId={} queued={} active={}",
                analysisId, queue.size(), activeAnalyses);
        return pending;
    }

    public Optional<AnalysisJobResponse> find(String analysisId) {
        AnalysisJobResponse cached = jobs.get(analysisId);

        if (cached != null) {
            return Optional.of(cached);
        }

        return jobStore.find(analysisId).map(this::recoverAfterRestart);
    }

    @Scheduled(
            initialDelayString = "${analysis.job-cleanup-interval-ms:3600000}",
            fixedDelayString = "${analysis.job-cleanup-interval-ms:3600000}"
    )
    public void cleanupExpiredJobs() {
        Instant cutoff = Instant.now().minus(Duration.ofHours(jobRetentionHours));
        int deletedCount = 0;

        for (AnalysisJobResponse job : jobStore.findAll()) {
            if (!isTerminal(job.status()) || !job.updatedAt().isBefore(cutoff)) {
                continue;
            }

            try {
                jobStore.delete(job.analysisId());
                jobs.remove(job.analysisId());
                deletedCount += 1;
            } catch (RuntimeException exception) {
                log.warn("analysis_job_cleanup_failed analysisId={}", job.analysisId(), exception);
            }
        }

        if (deletedCount > 0) {
            log.info("analysis_job_cleanup_completed deleted={}", deletedCount);
        }
    }

    private void updateStatus(String analysisId, AnalysisStatus status) {
        AnalysisJobResponse updated = jobs.computeIfPresent(analysisId, (id, current) -> persist(new AnalysisJobResponse(
                    id,
                    status,
                    current.urlAnalysis(),
                    current.result(),
                    current.pageAnalysis(),
                    current.finalAnalysis(),
                    current.failedStage(),
                    current.errorCode(),
                    current.errorMessage(),
                    current.createdAt(),
                    Instant.now()
            )));

        if (updated != null) {
            log.info("analysis_job_stage analysisId={} stage={}", analysisId, status);
        }
    }

    private void complete(
            String analysisId,
            UrlAnalysisResponse urlAnalysis,
            SandboxResponse result,
            PageAnalysisResponse pageAnalysis
    ) {
        FinalAnalysisResponse finalAnalysis = finalRiskPolicy.combine(urlAnalysis, pageAnalysis);
        SandboxResultSummary resultSummary = result == null ? null : summarize(result);
        AnalysisJobResponse completed = jobs.computeIfPresent(analysisId, (id, current) -> persist(new AnalysisJobResponse(
                id,
                AnalysisStatus.COMPLETED,
                urlAnalysis,
                resultSummary,
                pageAnalysis,
                finalAnalysis,
                null,
                null,
                null,
                current.createdAt(),
                Instant.now()
        )));

        if (completed != null) {
            long durationMs = Duration.between(completed.createdAt(), completed.updatedAt()).toMillis();
            log.info("analysis_job_completed analysisId={} durationMs={} verdict={}",
                    analysisId, durationMs, finalAnalysis.verdict());
        }
    }

    private SandboxResultSummary summarize(SandboxResponse result) {
        String artifactBase = "/api/analyses/" + result.analysisId();
        return new SandboxResultSummary(
                result.schemaVersion(),
                result.analysisId(),
                result.collectionStatus(),
                result.requestedUrl(),
                result.finalUrl(),
                result.redirectChain(),
                result.statusCode(),
                result.title(),
                result.htmlSizeBytes(),
                result.text(),
                result.textSizeBytes(),
                result.screenshotSizeBytes(),
                result.inputs(),
                result.forms(),
                result.links(),
                result.domMetadataTruncated(),
                result.network(),
                result.loadTimeMs(),
                new ArtifactLinks(
                        artifactBase + "/html",
                        artifactBase + "/text",
                        artifactBase + "/screenshot",
                        artifactBase + "/metadata"
                ),
                result.error()
        );
    }

    private void recordUrlAnalysis(String analysisId, UrlAnalysisResponse urlAnalysis) {
        AnalysisStatus nextStatus = Boolean.TRUE.equals(urlAnalysis.requiresDeepAnalysis())
                ? AnalysisStatus.SANDBOX_COLLECTING
                : AnalysisStatus.FINALIZING;
        jobs.computeIfPresent(analysisId, (id, current) -> persist(new AnalysisJobResponse(
                id,
                nextStatus,
                urlAnalysis,
                current.result(),
                current.pageAnalysis(),
                current.finalAnalysis(),
                null,
                null,
                null,
                current.createdAt(),
                Instant.now()
        )));
    }

    private void recordSandboxResult(String analysisId, SandboxResponse sandboxResponse) {
        jobs.computeIfPresent(analysisId, (id, current) -> persist(new AnalysisJobResponse(
                id,
                AnalysisStatus.PAGE_ANALYZING,
                current.urlAnalysis(),
                summarize(sandboxResponse),
                current.pageAnalysis(),
                current.finalAnalysis(),
                null,
                null,
                null,
                current.createdAt(),
                Instant.now()
        )));
    }

    private void recordPageAnalysis(String analysisId, PageAnalysisResponse pageAnalysis) {
        jobs.computeIfPresent(analysisId, (id, current) -> persist(new AnalysisJobResponse(
                id,
                AnalysisStatus.FINALIZING,
                current.urlAnalysis(),
                current.result(),
                pageAnalysis,
                current.finalAnalysis(),
                null,
                null,
                null,
                current.createdAt(),
                Instant.now()
        )));
    }

    private void fail(String analysisId, Throwable throwable) {
        Throwable error = Exceptions.unwrap(throwable);

        if (Exceptions.isRetryExhausted(error) && error.getCause() != null) {
            error = Exceptions.unwrap(error.getCause());
        }

        String code = "ANALYSIS_FAILED";
        String message = "분석 처리 중 오류가 발생했습니다.";

        if (error instanceof AnalysisTimeoutException) {
            code = "ANALYSIS_TIMEOUT";
            message = "전체 분석 제한시간을 초과했습니다.";
        } else if (error instanceof UrlAnalysisException) {
            code = "URL_ANALYSIS_FAILED";
            message = "URL 분석 AI가 요청을 처리하지 못했습니다.";
        } else if (error instanceof PageAnalysisException) {
            code = "PAGE_ANALYSIS_FAILED";
            message = "페이지 분석 AI가 요청을 처리하지 못했습니다.";
        } else if (error instanceof TimeoutException) {
            code = "SANDBOX_TIMEOUT";
            message = "Sandbox 응답 대기 시간을 초과했습니다.";
        } else if (error instanceof WebClientRequestException) {
            code = "SANDBOX_UNAVAILABLE";
            message = "Sandbox 서버에 연결할 수 없습니다.";
        } else if (error instanceof WebClientResponseException responseException) {
            code = "SANDBOX_ERROR";
            message = "Sandbox가 분석 요청을 처리하지 못했습니다. HTTP "
                    + responseException.getStatusCode().value();
        }

        String finalCode = code;
        String finalMessage = message;
        AnalysisJobResponse failed = jobs.computeIfPresent(analysisId, (id, current) -> persist(new AnalysisJobResponse(
                id,
                AnalysisStatus.FAILED,
                current.urlAnalysis(),
                current.result(),
                current.pageAnalysis(),
                current.finalAnalysis(),
                current.status().name(),
                finalCode,
                finalMessage,
                current.createdAt(),
                Instant.now()
        )));

        if (failed != null) {
            long durationMs = Duration.between(failed.createdAt(), failed.updatedAt()).toMillis();
            log.error("analysis_job_failed analysisId={} failedStage={} code={} durationMs={}",
                    analysisId, failed.failedStage(), code, durationMs, error);
        }
    }

    private AnalysisJobResponse persist(AnalysisJobResponse job) {
        try {
            jobStore.save(job);
        } catch (RuntimeException exception) {
            log.error("analysis_job_persist_failed analysisId={}", job.analysisId(), exception);
        }
        return job;
    }

    private AnalysisJobResponse recoverAfterRestart(AnalysisJobResponse stored) {
        AnalysisJobResponse recovered = stored;

        if (isInProgress(stored.status())) {
            recovered = new AnalysisJobResponse(
                    stored.analysisId(),
                    AnalysisStatus.FAILED,
                    stored.urlAnalysis(),
                    stored.result(),
                    stored.pageAnalysis(),
                    stored.finalAnalysis(),
                    stored.status().name(),
                    "ANALYSIS_INTERRUPTED",
                    "백엔드 재시작으로 분석 작업이 중단되었습니다.",
                    stored.createdAt(),
                    Instant.now()
            );
            jobStore.save(recovered);
        }

        jobs.put(recovered.analysisId(), recovered);
        return recovered;
    }

    private synchronized void dispatchNext() {
        while (activeAnalyses < maxConcurrentAnalyses) {
            QueuedAnalysis queued = queue.poll();

            if (queued == null) {
                return;
            }

            activeAnalyses += 1;
            updateStatus(queued.analysisId(), AnalysisStatus.URL_ANALYZING);
            execute(queued);
        }
    }

    private void execute(QueuedAnalysis queued) {
        Mono<SandboxResponse> sandboxAnalysis = sandboxService.analyze(
                queued.url(),
                queued.analysisId()
        );

        if (sandboxRetryCount > 0) {
            sandboxAnalysis = sandboxAnalysis.retryWhen(
                    Retry.backoff(sandboxRetryCount, Duration.ofSeconds(1))
                            .maxBackoff(Duration.ofSeconds(3))
                            .filter(this::isTransientFailure)
                            .doBeforeRetry(signal -> log.warn(
                                    "analysis_job_retry analysisId={} attempt={} cause={}",
                                    queued.analysisId(),
                                    signal.totalRetries() + 1,
                                    signal.failure().getClass().getSimpleName()
                            ))
            );
        }

        Mono<SandboxResponse> sandboxPipeline = sandboxAnalysis;
        Mono<PipelineResult> analysis = urlAnalysisService.analyze(queued.url())
                .doOnNext(urlResult -> recordUrlAnalysis(queued.analysisId(), urlResult))
                .flatMap(urlResult -> {
                    if (!Boolean.TRUE.equals(urlResult.requiresDeepAnalysis())) {
                        return Mono.just(new PipelineResult(urlResult, null, null));
                    }
                    return sandboxPipeline
                        .doOnNext(sandboxResult -> recordSandboxResult(
                                queued.analysisId(), sandboxResult
                        ))
                        .flatMap(sandboxResult -> pageAnalysisService.analyze(sandboxResult)
                                .doOnNext(pageResult -> recordPageAnalysis(
                                        queued.analysisId(), pageResult
                                ))
                                .map(pageResult -> new PipelineResult(
                                        urlResult, sandboxResult, pageResult
                                ))
                        );
                });

        analysis
                .timeout(
                        Duration.ofSeconds(timeoutSeconds),
                        Mono.error(new AnalysisTimeoutException(timeoutSeconds))
                )
                .doFinally(ignored -> analysisFinished())
                .subscribe(
                        result -> complete(
                                queued.analysisId(),
                                result.urlAnalysisResponse(),
                                result.sandboxResponse(),
                                result.pageAnalysisResponse()
                        ),
                        error -> fail(queued.analysisId(), error)
                );
    }

    private synchronized void analysisFinished() {
        activeAnalyses = Math.max(activeAnalyses - 1, 0);
        dispatchNext();
    }

    private boolean isTransientFailure(Throwable throwable) {
        Throwable error = Exceptions.unwrap(throwable);
        return error instanceof TimeoutException
                || error instanceof WebClientRequestException
                || error instanceof WebClientResponseException responseException
                && responseException.getStatusCode().is5xxServerError();
    }

    private boolean isInProgress(AnalysisStatus status) {
        return status == AnalysisStatus.PENDING
                || status == AnalysisStatus.RUNNING
                || status == AnalysisStatus.URL_ANALYZING
                || status == AnalysisStatus.SANDBOX_COLLECTING
                || status == AnalysisStatus.PAGE_ANALYZING
                || status == AnalysisStatus.FINALIZING;
    }

    private boolean isTerminal(AnalysisStatus status) {
        return status == AnalysisStatus.COMPLETED || status == AnalysisStatus.FAILED;
    }

    private int requirePositive(int value, String name) {
        if (value <= 0) {
            throw new IllegalArgumentException(name + "은(는) 0보다 커야 합니다.");
        }
        return value;
    }

    private int requireNonNegative(int value, String name) {
        if (value < 0) {
            throw new IllegalArgumentException(name + "은(는) 0 이상이어야 합니다.");
        }
        return value;
    }

    private record QueuedAnalysis(String analysisId, String url) {
    }

    private record PipelineResult(
            UrlAnalysisResponse urlAnalysisResponse,
            SandboxResponse sandboxResponse,
            PageAnalysisResponse pageAnalysisResponse
    ) {
    }
}
