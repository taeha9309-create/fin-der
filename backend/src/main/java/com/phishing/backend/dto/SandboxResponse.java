package com.phishing.backend.dto;

import java.util.List;
import java.util.Map;
import java.io.Serializable;

public record SandboxResponse(
        String schemaVersion,
        String analysisId,
        String collectionStatus,
        String requestedUrl,
        String finalUrl,
        List<Map<String, Object>> redirectChain,
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
        List<Map<String, Object>> inputs,
        List<Map<String, Object>> forms,
        List<Map<String, Object>> links,
        Map<String, Object> domMetadataTruncated,
        Map<String, Object> network,
        Long loadTimeMs,
        String error
) implements Serializable {
}
