package com.phishing.backend.config;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import org.springframework.web.server.WebFilter;
import org.springframework.web.server.WebFilterChain;
import reactor.core.publisher.Mono;

import java.util.UUID;
import java.util.regex.Pattern;

@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class RequestIdFilter implements WebFilter {

    public static final String HEADER_NAME = "X-Request-Id";
    private static final String ATTRIBUTE_NAME = RequestIdFilter.class.getName() + ".requestId";
    private static final Pattern VALID_REQUEST_ID = Pattern.compile("^[A-Za-z0-9._-]{1,64}$");
    private static final Logger log = LoggerFactory.getLogger(RequestIdFilter.class);

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, WebFilterChain chain) {
        String requestId = resolveRequestId(exchange);
        long startedAt = System.nanoTime();
        exchange.getAttributes().put(ATTRIBUTE_NAME, requestId);
        exchange.getResponse().getHeaders().set(HEADER_NAME, requestId);

        return chain.filter(exchange).doFinally(signalType -> {
            if ("/health".equals(exchange.getRequest().getPath().value())) {
                return;
            }

            long durationMs = (System.nanoTime() - startedAt) / 1_000_000;
            int status = exchange.getResponse().getStatusCode() == null
                    ? 200
                    : exchange.getResponse().getStatusCode().value();
            log.info("http_request requestId={} method={} path={} status={} durationMs={}",
                    requestId,
                    exchange.getRequest().getMethod(),
                    exchange.getRequest().getPath().value(),
                    status,
                    durationMs);
        });
    }

    public static String getRequestId(ServerWebExchange exchange) {
        Object requestId = exchange.getAttribute(ATTRIBUTE_NAME);
        return requestId == null ? "unknown" : requestId.toString();
    }

    private String resolveRequestId(ServerWebExchange exchange) {
        String supplied = exchange.getRequest().getHeaders().getFirst(HEADER_NAME);

        if (supplied != null && VALID_REQUEST_ID.matcher(supplied).matches()) {
            return supplied;
        }

        return UUID.randomUUID().toString();
    }
}
