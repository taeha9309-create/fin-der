package com.phishing.backend.service;

import com.phishing.backend.dto.AnalysisJobResponse;

import java.util.List;
import java.util.Optional;

public interface AnalysisJobStore {

    void save(AnalysisJobResponse job);

    Optional<AnalysisJobResponse> find(String analysisId);

    List<AnalysisJobResponse> findAll();

    void delete(String analysisId);
}
