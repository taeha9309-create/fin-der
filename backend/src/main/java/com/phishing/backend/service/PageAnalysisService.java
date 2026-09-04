package com.phishing.backend.service;

import com.phishing.backend.dto.PageAnalysisResponse;
import com.phishing.backend.dto.SandboxResponse;
import com.phishing.backend.exception.PageAnalysisException;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.time.Duration;

@Service
public class PageAnalysisService {

    private final WebClient pageAnalysisWebClient;

    public PageAnalysisService(
            @Qualifier("pageAnalysisWebClient") WebClient pageAnalysisWebClient
    ) {
        this.pageAnalysisWebClient = pageAnalysisWebClient;
    }

    public Mono<PageAnalysisResponse> analyze(SandboxResponse sandboxResponse) {
        return pageAnalysisWebClient.post()
                .uri("/v1/analyze")
                .bodyValue(sandboxResponse)
                .retrieve()
                .bodyToMono(PageAnalysisResponse.class)
                .timeout(Duration.ofSeconds(20))
                .onErrorMap(error -> new PageAnalysisException(error));
    }
}
