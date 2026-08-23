package com.phishing.backend.service;

import com.phishing.backend.dto.AnalysisJobResponse;

import java.util.Optional;

public interface AnalysisJobStore {

    void save(AnalysisJobResponse job);

    Optional<AnalysisJobResponse> find(String analysisId);
}
