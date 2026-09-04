package com.leveragy.controller;

import com.leveragy.dto.ReportRequest;
import com.leveragy.dto.UpdateReportStatusRequest;
import com.leveragy.entity.Report;
import com.leveragy.repository.ReportRepository;
import com.leveragy.service.AdminTokenService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import javax.validation.Valid;
import java.net.URI;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/reports")
public class ReportController {

    private final ReportRepository reportRepository;
    private final AdminTokenService adminTokenService;

    public ReportController(ReportRepository reportRepository, AdminTokenService adminTokenService) {
        this.reportRepository = reportRepository;
        this.adminTokenService = adminTokenService;
    }

    /**
     * 동일 URL 제보 중복 통합: 같은 URL로 이미 접수된 제보가 있으면 새 행을
     * 만드는 대신 그 행의 reportCount를 올리고 새 의견을 이어붙인다.
     */
    @PostMapping
    public ResponseEntity<Report> createReport(@Valid @RequestBody ReportRequest request) {
        String url = request.getUrl();
        String reason = request.getReason();

        Report report = reportRepository.findFirstByUrlOrderByCreatedAtDesc(url)
                .map(existing -> {
                    existing.setReportCount(existing.getReportCount() + 1);
                    if (reason != null && !reason.isBlank()) {
                        String merged = (existing.getReason() == null || existing.getReason().isBlank())
                                ? reason
                                : existing.getReason() + "\n" + reason;
                        existing.setReason(merged);
                    }
                    if (existing.getAnalysisId() == null && request.getAnalysisId() != null) {
                        existing.setAnalysisId(request.getAnalysisId());
                    }
                    return existing;
                })
                .orElseGet(() -> {
                    Report created = new Report();
                    created.setUrl(url);
                    created.setReason(reason);
                    created.setAnalysisId(request.getAnalysisId());
                    created.setDomain(extractDomain(url));
                    return created;
                });

        return ResponseEntity.ok(reportRepository.save(report));
    }

    /**
     * status 필터 없이 전체 목록을 요청하는 건 관리자 Dashboard뿐이라 그 경우만
     * 로그인을 요구한다. Threat Intelligence처럼 status로 걸러서 보는 공개 조회는
     * 로그인 없이 그대로 둔다.
     */
    @GetMapping
    public ResponseEntity<?> listReports(
            @RequestParam(required = false) String status,
            @RequestHeader(value = "Authorization", required = false) String authorization) {
        if ((status == null || status.isBlank()) && !isAuthorized(authorization)) {
            return unauthorized();
        }
        List<Report> reports = (status == null || status.isBlank())
                ? reportRepository.findAllByOrderByCreatedAtDesc()
                : reportRepository.findAllByStatusOrderByCreatedAtDesc(status);
        return ResponseEntity.ok(reports);
    }

    @PatchMapping("/{id}")
    public ResponseEntity<?> updateStatus(
            @PathVariable Long id,
            @Valid @RequestBody UpdateReportStatusRequest request,
            @RequestHeader(value = "Authorization", required = false) String authorization) {
        if (!isAuthorized(authorization)) {
            return unauthorized();
        }
        return reportRepository.findById(id)
                .map(report -> {
                    report.setStatus(request.getStatus());
                    return ResponseEntity.ok(reportRepository.save(report));
                })
                .orElse(ResponseEntity.notFound().build());
    }

    private boolean isAuthorized(String authorizationHeader) {
        return adminTokenService.isValid(AdminTokenService.extractBearerToken(authorizationHeader));
    }

    private ResponseEntity<Map<String, String>> unauthorized() {
        return ResponseEntity.status(401).body(Map.of("message", "관리자 로그인이 필요합니다."));
    }

    private String extractDomain(String url) {
        try {
            String host = URI.create(url).getHost();
            return host != null ? host : url;
        } catch (Exception e) {
            return url;
        }
    }
}
