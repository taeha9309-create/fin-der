package com.leveragy.dto;

import javax.validation.constraints.NotBlank;

public class AnalyzeRequest {

    @NotBlank(message = "url은 필수입니다.")
    private String url;

    // 아래 필드는 선택값이다. 오케스트레이터(backend)가 ml-service/sandbox
    // 결과를 이미 계산해서 보낼 때 채워지며, 없으면 목업 로직으로 계산한다.
    private Integer riskScore;
    private String mlResult;
    private String multimodalResult;
    private String xaiResult;
    private String finalResult;

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

    public boolean hasPrecomputedResult() {
        return finalResult != null && !finalResult.isBlank();
    }
}
