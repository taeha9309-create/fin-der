package com.phishing.backend.dto;

public record MultimodalRequest(
        String requestedUrl,
        String finalUrl,
        Integer statusCode,
        String title,
        String html,
        String screenshotBase64,
        String error
) {
}
