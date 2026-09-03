package com.phishing.backend.controller;

import com.phishing.backend.dto.AnalysisJobResponse;
import com.phishing.backend.dto.AnalyzeRequest;
import com.phishing.backend.dto.ApiError;
import com.phishing.backend.config.RequestIdFilter;
import com.phishing.backend.service.AnalysisJobService;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ServerWebExchange;

@RestController
@RequestMapping({"/api/analyze", "/api/analyses"})
public class AnalysisJobController {

    private final AnalysisJobService analysisJobService;

    public AnalysisJobController(AnalysisJobService analysisJobService) {
        this.analysisJobService = analysisJobService;
    }

    @PostMapping
    public ResponseEntity<AnalysisJobResponse> create(
            @Valid @RequestBody AnalyzeRequest request
    ) {
        return ResponseEntity.accepted().body(analysisJobService.create(request.url()));
    }

    @GetMapping("/{analysisId}")
    public ResponseEntity<?> find(
            @PathVariable String analysisId,
            ServerWebExchange exchange
    ) {
        return analysisJobService.find(analysisId)
                .<ResponseEntity<?>>map(ResponseEntity::ok)
                .orElseGet(() -> ResponseEntity.status(404).body(new ApiError(
                        "ANALYSIS_NOT_FOUND",
                        "해당 분석 작업을 찾을 수 없습니다.",
                        RequestIdFilter.getRequestId(exchange)
                )));
    }

}
