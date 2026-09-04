package com.phishing.backend.service;

import com.phishing.backend.dto.UrlAnalysisResponse;
import com.phishing.backend.exception.UrlAnalysisException;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.time.Duration;
import java.util.Map;

@Service
public class UrlAnalysisService {
    private final WebClient urlAnalysisWebClient;

    public UrlAnalysisService(@Qualifier("urlAnalysisWebClient") WebClient urlAnalysisWebClient) {
        this.urlAnalysisWebClient = urlAnalysisWebClient;
    }

    public Mono<UrlAnalysisResponse> analyze(String url) {
        return urlAnalysisWebClient.post()
                .uri("/v1/analyze")
                .bodyValue(Map.of("url", url))
                .retrieve()
                .bodyToMono(UrlAnalysisResponse.class)
                .timeout(Duration.ofSeconds(10))
                .onErrorMap(error -> new UrlAnalysisException(error));
    }
}
