package com.leveragy.controller;

import com.leveragy.dto.AnalyzeRequest;
import com.leveragy.dto.UpdateAnalysisResultRequest;
import com.leveragy.entity.UrlAnalysis;
import com.leveragy.repository.UrlAnalysisRepository;
import com.leveragy.service.AnalysisService;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import javax.validation.Valid;
import java.util.List;

@RestController
@RequestMapping("/api/analyze")
public class AnalysisController {

    private final AnalysisService analysisService;
    private final UrlAnalysisRepository urlAnalysisRepository;

    public AnalysisController(AnalysisService analysisService, UrlAnalysisRepository urlAnalysisRepository) {
        this.analysisService = analysisService;
        this.urlAnalysisRepository = urlAnalysisRepository;
    }

    /**
     * 비동기 Job 1단계: backend 오케스트레이터가 분석을 시작할 때 호출한다.
     * PROCESSING 행을 즉시 만들어 id를 돌려주고, 실제 분석은 backend가
     * ml-service/sandbox/multimodal-service를 호출한 뒤 PATCH로 채운다.
     */
    @PostMapping
    public ResponseEntity<UrlAnalysis> createPending(@Valid @RequestBody AnalyzeRequest request) {
        UrlAnalysis pending = analysisService.createPendingAnalysis(request.getUrl());
        return ResponseEntity.status(HttpStatus.ACCEPTED).body(pending);
    }

    /**
     * 비동기 Job 2단계: backend가 실제 분석을 끝내면 이 엔드포인트로 결과를 채운다.
     */
    @PatchMapping("/{id}")
    public ResponseEntity<UrlAnalysis> complete(
            @PathVariable Long id,
            @Valid @RequestBody UpdateAnalysisResultRequest request
    ) {
        try {
            return ResponseEntity.ok(analysisService.completeAnalysis(id, request));
        } catch (AnalysisService.AnalysisNotFoundException e) {
            return ResponseEntity.notFound().build();
        }
    }

    @GetMapping
    public ResponseEntity<List<UrlAnalysis>> listAnalyses() {
        return ResponseEntity.ok(urlAnalysisRepository.findAllByOrderByCreatedAtDesc());
    }

    @GetMapping("/{id}")
    public ResponseEntity<UrlAnalysis> getAnalysis(@PathVariable Long id) {
        return urlAnalysisRepository.findById(id)
                .map(ResponseEntity::ok)
                .orElse(ResponseEntity.notFound().build());
    }
}
