package com.phishing.backend.service;

import com.phishing.backend.dto.AnalysisJobResponse;
import com.phishing.backend.dto.AnalysisStatus;
import com.phishing.backend.dto.SandboxResponse;
import com.phishing.backend.exception.AnalysisQueueFullException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
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
    private final AnalysisJobStore jobStore;
    private final ConcurrentMap<String, AnalysisJobResponse> jobs = new ConcurrentHashMap<>();
    private final ConcurrentLinkedQueue<QueuedAnalysis> queue = new ConcurrentLinkedQueue<>();
    private final int maxConcurrentAnalyses;
    private final int maxQueuedAnalyses;
    private final int sandboxRetryCount;
    private int activeAnalyses;

    public AnalysisJobService(
            SandboxService sandboxService,
            AnalysisJobStore jobStore,
            @Value("${analysis.max-concurrent:2}") int maxConcurrentAnalyses,
            @Value("${analysis.max-queued:20}") int maxQueuedAnalyses,
            @Value("${analysis.sandbox-retry-count:1}") int sandboxRetryCount
    ) {
        this.sandboxService = sandboxService;
        this.jobStore = jobStore;
        this.maxConcurrentAnalyses = requirePositive(maxConcurrentAnalyses, "analysis.max-concurrent");
        this.maxQueuedAnalyses = requirePositive(maxQueuedAnalyses, "analysis.max-queued");
        this.sandboxRetryCount = requireNonNegative(sandboxRetryCount, "analysis.sandbox-retry-count");
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

    private void updateStatus(String analysisId, AnalysisStatus status) {
        jobs.computeIfPresent(analysisId, (id, current) -> persist(new AnalysisJobResponse(
                    id,
                    status,
                    current.result(),
                    current.errorCode(),
                    current.errorMessage(),
                    current.createdAt(),
                    Instant.now()
            )));
    }

    private void complete(String analysisId, SandboxResponse result) {
        jobs.computeIfPresent(analysisId, (id, current) -> persist(new AnalysisJobResponse(
                id,
                AnalysisStatus.COMPLETED,
                result,
                null,
                null,
                current.createdAt(),
                Instant.now()
        )));
        log.info("analysis_job_completed analysisId={}", analysisId);
    }

    private void fail(String analysisId, Throwable throwable) {
        Throwable error = Exceptions.unwrap(throwable);

        if (Exceptions.isRetryExhausted(error) && error.getCause() != null) {
            error = Exceptions.unwrap(error.getCause());
        }

        String code = "ANALYSIS_FAILED";
        String message = "분석 처리 중 오류가 발생했습니다.";

        if (error instanceof TimeoutException) {
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
        jobs.computeIfPresent(analysisId, (id, current) -> persist(new AnalysisJobResponse(
                id,
                AnalysisStatus.FAILED,
                null,
                finalCode,
                finalMessage,
                current.createdAt(),
                Instant.now()
        )));
        log.error("analysis_job_failed analysisId={} code={}", analysisId, code, error);
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

        if (stored.status() == AnalysisStatus.PENDING || stored.status() == AnalysisStatus.RUNNING) {
            recovered = new AnalysisJobResponse(
                    stored.analysisId(),
                    AnalysisStatus.FAILED,
                    null,
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
            updateStatus(queued.analysisId(), AnalysisStatus.RUNNING);
            execute(queued);
        }
    }

    private void execute(QueuedAnalysis queued) {
        Mono<SandboxResponse> analysis = sandboxService.analyze(
                queued.url(),
                queued.analysisId()
        );

        if (sandboxRetryCount > 0) {
            analysis = analysis.retryWhen(
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

        analysis
                .doFinally(ignored -> analysisFinished())
                .subscribe(
                        result -> complete(queued.analysisId(), result),
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
}
