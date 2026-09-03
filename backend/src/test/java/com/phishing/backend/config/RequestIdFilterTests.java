package com.phishing.backend.config;

import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.mock.http.server.reactive.MockServerHttpRequest;
import org.springframework.mock.web.server.MockServerWebExchange;

import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

class RequestIdFilterTests {

    private final RequestIdFilter filter = new RequestIdFilter();

    @Test
    void validClientRequestIdIsReturned() {
        MockServerWebExchange exchange = MockServerWebExchange.from(
                MockServerHttpRequest.get("/api/test")
                        .header(RequestIdFilter.HEADER_NAME, "finder-test_123")
                        .build()
        );

        filter.filter(exchange, currentExchange -> {
            currentExchange.getResponse().setStatusCode(HttpStatus.NO_CONTENT);
            return currentExchange.getResponse().setComplete();
        }).block();

        assertThat(exchange.getResponse().getHeaders().getFirst(RequestIdFilter.HEADER_NAME))
                .isEqualTo("finder-test_123");
    }

    @Test
    void invalidClientRequestIdIsReplacedWithUuid() {
        MockServerWebExchange exchange = MockServerWebExchange.from(
                MockServerHttpRequest.get("/api/test")
                        .header(RequestIdFilter.HEADER_NAME, "잘못된 ID")
                        .build()
        );

        filter.filter(exchange, currentExchange -> currentExchange.getResponse().setComplete())
                .block();

        String requestId = exchange.getResponse().getHeaders()
                .getFirst(RequestIdFilter.HEADER_NAME);
        assertThat(requestId).isNotBlank();
        assertThatCodeIsUuid(requestId);
    }

    private void assertThatCodeIsUuid(String requestId) {
        assertThat(UUID.fromString(requestId)).isNotNull();
    }
}
