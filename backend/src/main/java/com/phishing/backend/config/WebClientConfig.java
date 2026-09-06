package com.phishing.backend.config;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.reactive.function.client.ExchangeStrategies;
import org.springframework.web.reactive.function.client.WebClient;

@Configuration
public class WebClientConfig {

    @Bean
    public ObjectMapper objectMapper() {
        return new ObjectMapper();
    }

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

    @Bean
    public WebClient mlServiceWebClient(
            @Value("${ml-service.base-url}") String mlServiceBaseUrl
    ) {
        return WebClient.builder()
                .baseUrl(mlServiceBaseUrl)
                .build();
    }

    @Bean
    public WebClient dbApiWebClient(
            @Value("${db-api.base-url}") String dbApiBaseUrl
    ) {
        // PATCH/GET responses echo back the stored record, which includes the
        // base64 screenshotData (can exceed Spring's 256KB default buffer).
        ExchangeStrategies strategies = ExchangeStrategies.builder()
                .codecs(configurer ->
                        configurer.defaultCodecs().maxInMemorySize(25 * 1024 * 1024)
                )
                .build();

        return WebClient.builder()
                .baseUrl(dbApiBaseUrl)
                .exchangeStrategies(strategies)
                .build();
    }

    @Bean
    public WebClient multimodalWebClient(
            @Value("${multimodal-service.base-url}") String multimodalBaseUrl
    ) {
        ExchangeStrategies strategies = ExchangeStrategies.builder()
                .codecs(configurer ->
                        configurer.defaultCodecs().maxInMemorySize(25 * 1024 * 1024)
                )
                .build();

        return WebClient.builder()
                .baseUrl(multimodalBaseUrl)
                .exchangeStrategies(strategies)
                .build();
    }
}
