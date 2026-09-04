package com.phishing.backend.dto;

import java.io.Serializable;
import java.util.List;
import java.util.Map;

public record SandboxResultSummary(
        String schemaVersion,
        String analysisId,
        String collectionStatus,
        String requestedUrl,
        String finalUrl,
        List<Map<String, Object>> redirectChain,
        Integer statusCode,
        String title,
        Integer htmlSizeBytes,
        String text,
        Integer textSizeBytes,
        Integer screenshotSizeBytes,
        List<Map<String, Object>> inputs,
        List<Map<String, Object>> forms,
        List<Map<String, Object>> links,
        Map<String, Object> domMetadataTruncated,
        Map<String, Object> network,
        Long loadTimeMs,
        ArtifactLinks artifacts,
        String error
) implements Serializable {
}
