package com.leveragy.entity;

import javax.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "url_analysis")
public class UrlAnalysis {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, length = 2048)
    private String url;

    @Column(name = "risk_score")
    private Integer riskScore;

    @Lob
    @Column(name = "ml_result")
    private String mlResult;

    @Lob
    @Column(name = "multimodal_result")
    private String multimodalResult;

    @Lob
    @Column(name = "xai_result")
    private String xaiResult;

    /**
     * Sandbox가 캡처한 분석 당시 화면. data URI(예: "data:image/png;base64,...")
     * 형태로 저장하며, 없으면 프론트에서 예시 화면을 대신 보여준다.
     */
    @Lob
    @Column(name = "screenshot_data")
    private String screenshotData;

    @Column(name = "final_result", length = 32)
    private String finalResult;

    /**
     * 비동기 분석 Job 상태: PROCESSING → COMPLETED(또는 FAILED).
     * backend 오케스트레이터가 행을 먼저 PROCESSING으로 만들어 id를 즉시 돌려주고,
     * ml-service/sandbox/multimodal-service 호출이 끝나면 PATCH로 채운다.
     */
    @Column(name = "processing_status", length = 32)
    private String processingStatus;

    @Column(name = "created_at", updatable = false)
    private LocalDateTime createdAt;

    @PrePersist
    protected void onCreate() {
        this.createdAt = LocalDateTime.now();
        if (this.processingStatus == null) {
            this.processingStatus = "PROCESSING";
        }
    }

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public String getUrl() { return url; }
    public void setUrl(String url) { this.url = url; }

    public Integer getRiskScore() { return riskScore; }
    public void setRiskScore(Integer riskScore) { this.riskScore = riskScore; }

    public String getMlResult() { return mlResult; }
    public void setMlResult(String mlResult) { this.mlResult = mlResult; }

    public String getMultimodalResult() { return multimodalResult; }
    public void setMultimodalResult(String multimodalResult) { this.multimodalResult = multimodalResult; }

    public String getXaiResult() { return xaiResult; }
    public void setXaiResult(String xaiResult) { this.xaiResult = xaiResult; }

    public String getScreenshotData() { return screenshotData; }
    public void setScreenshotData(String screenshotData) { this.screenshotData = screenshotData; }

    public String getFinalResult() { return finalResult; }
    public void setFinalResult(String finalResult) { this.finalResult = finalResult; }

    public String getProcessingStatus() { return processingStatus; }
    public void setProcessingStatus(String processingStatus) { this.processingStatus = processingStatus; }

    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }
}
