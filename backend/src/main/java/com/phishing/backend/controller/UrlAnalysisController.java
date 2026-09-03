package com.phishing.backend.controller;

import com.phishing.backend.dto.AnalysisResult;
import com.phishing.backend.dto.AnalyzeRequest;
import com.phishing.backend.service.AnalysisOrchestrator;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Mono;

@RestController
@RequestMapping("/api/v1/url-analysis")
public class UrlAnalysisController {

    private final AnalysisOrchestrator analysisOrchestrator;

    public UrlAnalysisController(AnalysisOrchestrator analysisOrchestrator) {
        this.analysisOrchestrator = analysisOrchestrator;
    }

    @PostMapping
    public Mono<AnalysisResult> analyze(
            @Valid @RequestBody AnalyzeRequest request
    ) {
        return analysisOrchestrator.analyze(request);
    }
}