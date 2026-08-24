package com.leveragy.controller;

import com.leveragy.dto.ReportRequest;
import com.leveragy.dto.UpdateReportStatusRequest;
import com.leveragy.entity.Report;
import com.leveragy.repository.ReportRepository;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import javax.validation.Valid;
import java.util.List;

@RestController
@RequestMapping("/api/reports")
public class ReportController {

    private final ReportRepository reportRepository;

    public ReportController(ReportRepository reportRepository) {
        this.reportRepository = reportRepository;
    }

    @PostMapping
    public ResponseEntity<Report> createReport(@Valid @RequestBody ReportRequest request) {
        Report report = new Report();
        report.setUrl(request.getUrl());
        report.setReason(request.getReason());
        Report saved = reportRepository.save(report);
        return ResponseEntity.ok(saved);
    }

    @GetMapping
    public ResponseEntity<List<Report>> listReports(
            @RequestParam(required = false) String status
    ) {
        List<Report> reports = status == null
                ? reportRepository.findAllByOrderByCreatedAtDesc()
                : reportRepository.findAllByStatusOrderByCreatedAtDesc(status);
        return ResponseEntity.ok(reports);
    }

    @PatchMapping("/{id}")
    public ResponseEntity<Report> updateStatus(
            @PathVariable Long id,
            @Valid @RequestBody UpdateReportStatusRequest request
    ) {
        return reportRepository.findById(id)
                .map(report -> {
                    report.setStatus(request.getStatus());
                    return ResponseEntity.ok(reportRepository.save(report));
                })
                .orElse(ResponseEntity.notFound().build());
    }
}
