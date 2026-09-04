package com.leveragy.dto;

import javax.validation.constraints.NotBlank;

public class AnalyzeRequest {

    @NotBlank(message = "url은 필수입니다.")
    private String url;

    public String getUrl() { return url; }
    public void setUrl(String url) { this.url = url; }
}
