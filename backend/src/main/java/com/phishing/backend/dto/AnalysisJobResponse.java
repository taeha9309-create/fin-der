package com.phishing.backend.dto;

import java.io.Serializable;
import java.time.Instant;

public record AnalysisJobResponse(
        String analysisId,
        AnalysisStatus status,
        SandboxResponse result,
        String errorCode,
        String errorMessage,
        Instant createdAt,
        Instant updatedAt
) implements Serializable {
}
