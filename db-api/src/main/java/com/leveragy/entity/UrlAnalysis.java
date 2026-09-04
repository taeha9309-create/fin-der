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

    @Column(name = "final_result", length = 32)
    private String finalResult;

    /**
     * Sandbox가 캡처한 분석 당시 화면. data URI(예: "data:image/png;base64,...")
     * 형태로 저장한다. 지금은 orchestrator(backend)가 이 값을 보내지 않아 항상 null이고,
     * 프론트는 null이면 예시 화면을 대신 보여준다 - backend가 screenshot을 db-api 저장
     * 요청(DbApiSaveRequest)에 포함해서 보내주면 이 컬럼이 채워지도록 미리 준비만 해둔다.
     */
    @Lob
    @Column(name = "screenshot_data")
    private String screenshotData;

    @Column(name = "created_at", updatable = false)
    private LocalDateTime createdAt;

    @PrePersist
    protected void onCreate() {
        this.createdAt = LocalDateTime.now();
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

    public String getFinalResult() { return finalResult; }
    public void setFinalResult(String finalResult) { this.finalResult = finalResult; }

    public String getScreenshotData() { return screenshotData; }
    public void setScreenshotData(String screenshotData) { this.screenshotData = screenshotData; }

    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }
}
