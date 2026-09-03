package com.phishing.backend.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.reactive.function.client.ExchangeStrategies;
import org.springframework.web.reactive.function.client.WebClient;

@Configuration
public class WebClientConfig {

    @Bean
    public WebClient sandboxWebClient(
            @Value("${sandbox.base-url}") String sandboxBaseUrl
    ) {
        ExchangeStrategies strategies = ExchangeStrategies.builder()
                .codecs(configurer ->
                        configurer.defaultCodecs().maxInMemorySize(25 * 1024 * 1024)
                )
                .build();

        return WebClient.builder()
                .baseUrl(sandboxBaseUrl)
                .exchangeStrategies(strategies)
                .build();
    }

    @Bean
    public WebClient pageAnalysisWebClient(
            @Value("${page-analysis.base-url}") String pageAnalysisBaseUrl
    ) {
        ExchangeStrategies strategies = ExchangeStrategies.builder()
                .codecs(configurer ->
                        configurer.defaultCodecs().maxInMemorySize(30 * 1024 * 1024)
                )
                .build();

        return WebClient.builder()
                .baseUrl(pageAnalysisBaseUrl)
                .exchangeStrategies(strategies)
                .build();
    }

    @Bean
    public WebClient urlAnalysisWebClient(
            @Value("${url-analysis.base-url}") String urlAnalysisBaseUrl
    ) {
        return WebClient.builder()
                .baseUrl(urlAnalysisBaseUrl)
                .build();
    }
}
