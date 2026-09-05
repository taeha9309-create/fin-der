package com.phishing.backend.dto;

import jakarta.validation.constraints.NotBlank;

public record AnalyzeRequest(
        @NotBlank(message = "url을 입력해주세요.")
        String url
) {
    private static final String EXPLICIT_SCHEME_PATTERN = "^[A-Za-z][A-Za-z0-9+.-]*://.*$";

    public AnalyzeRequest {
        if (url != null) {
            url = url.trim();
            if (!url.isEmpty() && !url.matches(EXPLICIT_SCHEME_PATTERN)) {
                url = "https://" + url;
            }
        }
    }
}
