package com.leveragy.entity;

import javax.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "reports")
public class Report {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, length = 2048)
    private String url;

    @Lob
    private String reason;

    @Column(name = "analysis_id")
    private Long analysisId;

    /** 신고된 URL의 호스트. 같은 도메인 제보를 한눈에 모아 보기 위한 보조 필드다. */
    @Column(length = 255)
    private String domain;

    /**
     * 동일 URL 제보 중복 통합: 같은 URL이 또 제보되면 새 행을 만들지 않고
     * 이 카운트만 올린다("동일 URL/도메인 제보 중복 통합 및 조회" - 보고서 2.4절).
     */
    @Column(name = "report_count", nullable = false)
    private Integer reportCount = 1;

    @Column(length = 32)
    private String status;

    @Column(name = "created_at", updatable = false)
    private LocalDateTime createdAt;

    @PrePersist
    protected void onCreate() {
        this.createdAt = LocalDateTime.now();
        if (this.status == null) {
            this.status = "PENDING";
        }
        if (this.reportCount == null) {
            this.reportCount = 1;
        }
    }

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public String getUrl() { return url; }
    public void setUrl(String url) { this.url = url; }

    public String getReason() { return reason; }
    public void setReason(String reason) { this.reason = reason; }

    public Long getAnalysisId() { return analysisId; }
    public void setAnalysisId(Long analysisId) { this.analysisId = analysisId; }

    public String getDomain() { return domain; }
    public void setDomain(String domain) { this.domain = domain; }

    public Integer getReportCount() { return reportCount; }
    public void setReportCount(Integer reportCount) { this.reportCount = reportCount; }

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }

    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }
}
