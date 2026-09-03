package com.phishing.backend.dto;

public enum AnalysisStatus {
    PENDING,
    RUNNING,
    URL_ANALYZING,
    SANDBOX_COLLECTING,
    PAGE_ANALYZING,
    FINALIZING,
    COMPLETED,
    FAILED
}
