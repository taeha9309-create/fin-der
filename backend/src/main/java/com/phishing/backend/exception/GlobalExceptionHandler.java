package com.phishing.backend.exception;

import com.phishing.backend.config.RequestIdFilter;
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
import org.springframework.web.reactive.resource.NoResourceFoundException;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.web.server.ServerWebExchange;

import java.util.concurrent.TimeoutException;

@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    @ExceptionHandler(NoResourceFoundException.class)
    public ResponseEntity<ApiError> handleNotFound(
            NoResourceFoundException exception,
            ServerWebExchange exchange
    ) {
        return ResponseEntity
                .status(HttpStatus.NOT_FOUND)
                .body(error("API_NOT_FOUND", "요청 경로를 찾을 수 없습니다.", exchange));
    }

    @ExceptionHandler(ResponseStatusException.class)
    public ResponseEntity<ApiError> handleResponseStatus(
            ResponseStatusException exception,
            ServerWebExchange exchange
    ) {
        String reason = exception.getReason() == null
                ? "요청을 처리할 수 없습니다."
                : exception.getReason();

        return ResponseEntity
                .status(exception.getStatusCode())
                .body(error("ARTIFACT_REQUEST_ERROR", reason, exchange));
    }

    @ExceptionHandler(AnalysisQueueFullException.class)
    public ResponseEntity<ApiError> handleAnalysisQueueFull(
            AnalysisQueueFullException exception,
            ServerWebExchange exchange
    ) {
        log.warn("Analysis queue is full: requestId={}", RequestIdFilter.getRequestId(exchange));
        return ResponseEntity
                .status(HttpStatus.TOO_MANY_REQUESTS)
                .body(error(
                        "ANALYSIS_QUEUE_FULL",
                        "분석 요청이 많습니다. 잠시 후 다시 시도해주세요.",
                        exchange
                ));
    }

    @ExceptionHandler(WebClientResponseException.class)
    public ResponseEntity<String> handleSandboxResponse(
            WebClientResponseException exception,
            ServerWebExchange exchange
    ) {
        String requestId = RequestIdFilter.getRequestId(exchange);
        log.warn("Sandbox returned an error: requestId={}, status={}",
                requestId, exception.getStatusCode().value());
        String responseBody = exception.getResponseBodyAsString();

        responseBody = addRequestId(responseBody, requestId);

        return ResponseEntity
                .status(exception.getStatusCode())
                .contentType(MediaType.APPLICATION_JSON)
                .body(responseBody);
    }

    @ExceptionHandler(WebClientRequestException.class)
    public ResponseEntity<ApiError> handleSandboxConnection(
            WebClientRequestException exception,
            ServerWebExchange exchange
    ) {
        log.error("Unable to connect to Sandbox: requestId={}",
                RequestIdFilter.getRequestId(exchange), exception);
        return ResponseEntity
                .status(HttpStatus.BAD_GATEWAY)
                .body(error(
                        "SANDBOX_UNAVAILABLE",
                        "Sandbox 서버에 연결할 수 없습니다.",
                        exchange
                ));
    }

    @ExceptionHandler(TimeoutException.class)
    public ResponseEntity<ApiError> handleTimeout(
            TimeoutException exception,
            ServerWebExchange exchange
    ) {
        log.warn("Sandbox request timed out: requestId={}",
                RequestIdFilter.getRequestId(exchange), exception);
        return ResponseEntity
                .status(HttpStatus.GATEWAY_TIMEOUT)
                .body(error(
                        "SANDBOX_TIMEOUT",
                        "Sandbox 응답 대기 시간을 초과했습니다.",
                        exchange
                ));
    }

    @ExceptionHandler(WebExchangeBindException.class)
    public ResponseEntity<ApiError> handleValidation(
            WebExchangeBindException exception,
            ServerWebExchange exchange
    ) {
        String message = exception.getFieldErrors().isEmpty()
                ? "요청값이 올바르지 않습니다."
                : exception.getFieldErrors().getFirst().getDefaultMessage();

        return ResponseEntity
                .badRequest()
                .body(error(
                        "INVALID_REQUEST",
                        message,
                        exchange
                ));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ApiError> handleUnexpected(
            Exception exception,
            ServerWebExchange exchange
    ) {
        log.error("Unhandled backend error: requestId={}",
                RequestIdFilter.getRequestId(exchange), exception);

        return ResponseEntity
                .status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(error(
                        "INTERNAL_ERROR",
                        "요청 처리 중 내부 오류가 발생했습니다.",
                        exchange
                ));
    }

    private ApiError error(String code, String message, ServerWebExchange exchange) {
        return new ApiError(code, message, RequestIdFilter.getRequestId(exchange));
    }

    private String addRequestId(String responseBody, String requestId) {
        if (responseBody != null) {
            String trimmed = responseBody.trim();

            if (trimmed.startsWith("{") && trimmed.endsWith("}")) {
                String content = trimmed.substring(0, trimmed.length() - 1).trim();
                String separator = content.length() > 1 ? "," : "";
                return content + separator + "\"requestId\":\"" + requestId + "\"}";
            }
        }

        return "{\"code\":\"SANDBOX_ERROR\","
                + "\"message\":\"Sandbox가 오류를 반환했습니다.\","
                + "\"requestId\":\"" + requestId + "\"}";
    }
}
