package com.phishing.backend.dto;

import java.util.List;
import java.util.Map;

public record MultimodalRequest(
        String analysisId,
        String requestedUrl,
        String finalUrl,
        Integer statusCode,
        Page page,
        List<Map<String, Object>> inputs,
        List<Map<String, Object>> forms,
        List<Map<String, Object>> links,
        Map<String, Object> network,
        List<Map<String, Object>> redirectChain,
        String screenshot,
        String error
) {
    public record Page(String title, String visibleText, String html) {}
}
