package com.phishing.backend.dto;

import java.util.List;
import java.io.Serializable;

public record SandboxResponse(
        String analysisId,
        String requestedUrl,
        String finalUrl,
        List<String> redirectChain,
        Integer statusCode,
        String title,
        String html,
        Integer htmlSizeBytes,
        String text,
        Integer textSizeBytes,
        String screenshotBase64,
        Integer screenshotSizeBytes,
        String htmlPath,
        String textPath,
        String screenshotPath,
        Long loadTimeMs,
        String error
) implements Serializable {
}
