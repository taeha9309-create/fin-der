package com.phishing.backend.dto;

public record ApiError(
        String code,
        String message,
        String requestId
) {
}
