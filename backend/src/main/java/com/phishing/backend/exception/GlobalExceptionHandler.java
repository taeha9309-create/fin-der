package com.phishing.backend.exception;

import com.phishing.backend.dto.ApiError;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.support.WebExchangeBindException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.reactive.function.client.WebClientRequestException;
import org.springframework.web.reactive.function.client.WebClientResponseException;

import java.util.concurrent.TimeoutException;

@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    @ExceptionHandler(AnalysisQueueFullException.class)
    public ResponseEntity<ApiError> handleAnalysisQueueFull(
            AnalysisQueueFullException exception
    ) {
        log.warn("Analysis queue is full");
        return ResponseEntity
                .status(HttpStatus.TOO_MANY_REQUESTS)
                .body(new ApiError(
                        "ANALYSIS_QUEUE_FULL",
                        "분석 요청이 많습니다. 잠시 후 다시 시도해주세요."
                ));
    }

    @ExceptionHandler(WebClientResponseException.class)
    public ResponseEntity<String> handleSandboxResponse(
            WebClientResponseException exception
    ) {
        log.warn("Sandbox returned an error: status={}, response={}",
                exception.getStatusCode().value(), exception.getResponseBodyAsString());
        String responseBody = exception.getResponseBodyAsString();

        if (responseBody == null || responseBody.isBlank()) {
            responseBody = """
                    {
                      "code": "SANDBOX_ERROR",
                      "message": "Sandbox가 오류를 반환했습니다."
                    }
                    """;
        }

        return ResponseEntity
                .status(exception.getStatusCode())
                .contentType(MediaType.APPLICATION_JSON)
                .body(responseBody);
    }

    @ExceptionHandler(WebClientRequestException.class)
    public ResponseEntity<ApiError> handleSandboxConnection(
            WebClientRequestException exception
    ) {
        log.error("Unable to connect to Sandbox", exception);
        return ResponseEntity
                .status(HttpStatus.BAD_GATEWAY)
                .body(new ApiError(
                        "SANDBOX_UNAVAILABLE",
                        "Sandbox 서버에 연결할 수 없습니다."
                ));
    }

    @ExceptionHandler(TimeoutException.class)
    public ResponseEntity<ApiError> handleTimeout(
            TimeoutException exception
    ) {
        log.warn("Sandbox request timed out", exception);
        return ResponseEntity
                .status(HttpStatus.GATEWAY_TIMEOUT)
                .body(new ApiError(
                        "SANDBOX_TIMEOUT",
                        "Sandbox 응답 대기 시간을 초과했습니다."
                ));
    }

    @ExceptionHandler(WebExchangeBindException.class)
    public ResponseEntity<ApiError> handleValidation(
            WebExchangeBindException exception
    ) {
        String message = exception.getFieldErrors().isEmpty()
                ? "요청값이 올바르지 않습니다."
                : exception.getFieldErrors().getFirst().getDefaultMessage();

        return ResponseEntity
                .badRequest()
                .body(new ApiError(
                        "INVALID_REQUEST",
                        message
                ));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ApiError> handleUnexpected(Exception exception) {
        log.error("Unhandled backend error", exception);

        return ResponseEntity
                .status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(new ApiError(
                        "INTERNAL_ERROR",
                        "요청 처리 중 내부 오류가 발생했습니다."
                ));
    }
}
