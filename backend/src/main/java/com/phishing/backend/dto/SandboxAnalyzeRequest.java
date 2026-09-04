package com.phishing.backend.dto;

public record SandboxAnalyzeRequest(
        String url,
        String analysisId
) {
}
