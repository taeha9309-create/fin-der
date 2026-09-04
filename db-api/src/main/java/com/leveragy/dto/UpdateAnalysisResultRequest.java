package com.leveragy.dto;

import javax.validation.constraints.NotBlank;
import javax.validation.constraints.Pattern;

/**
 * backend 오케스트레이터가 ml-service/sandbox/multimodal-service 호출을 끝낸 뒤
 * PROCESSING 상태였던 분석 행을 채우기 위해 보내는 요청.
 */
public class UpdateAnalysisResultRequest {

    private Integer riskScore;
    private String mlResult;
    private String multimodalResult;
    private String xaiResult;
    private String screenshotData;

    @NotBlank(message = "finalResult는 필수입니다.")
    @Pattern(
            regexp = "NORMAL|SUSPICIOUS|PHISHING|UNKNOWN",
            message = "finalResult는 NORMAL, SUSPICIOUS, PHISHING, UNKNOWN 중 하나여야 합니다."
    )
    private String finalResult;

    @NotBlank(message = "processingStatus는 필수입니다.")
    @Pattern(
            regexp = "COMPLETED|FAILED",
            message = "processingStatus는 COMPLETED 또는 FAILED여야 합니다."
    )
    private String processingStatus;

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
}
