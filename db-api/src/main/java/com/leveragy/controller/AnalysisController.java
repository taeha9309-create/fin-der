package com.leveragy.controller;

import com.leveragy.dto.AnalyzeRequest;
import com.leveragy.entity.UrlAnalysis;
import com.leveragy.repository.UrlAnalysisRepository;
import com.leveragy.service.AnalysisService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import javax.validation.Valid;

@RestController
@RequestMapping("/api/analyze")
public class AnalysisController {

    private final AnalysisService analysisService;
    private final UrlAnalysisRepository urlAnalysisRepository;

    public AnalysisController(AnalysisService analysisService, UrlAnalysisRepository urlAnalysisRepository) {
        this.analysisService = analysisService;
        this.urlAnalysisRepository = urlAnalysisRepository;
    }

    @PostMapping
    public ResponseEntity<UrlAnalysis> analyze(@Valid @RequestBody AnalyzeRequest request) {
        UrlAnalysis result = analysisService.analyze(request);
        return ResponseEntity.ok(result);
    }

    @GetMapping("/{id}")
    public ResponseEntity<UrlAnalysis> getAnalysis(@PathVariable Long id) {
        return urlAnalysisRepository.findById(id)
                .map(ResponseEntity::ok)
                .orElse(ResponseEntity.notFound().build());
    }
}
