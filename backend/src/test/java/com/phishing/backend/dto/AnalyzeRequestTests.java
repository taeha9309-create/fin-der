package com.phishing.backend.dto;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class AnalyzeRequestTests {

    @Test
    void addsHttpsWhenSchemeIsMissing() {
        AnalyzeRequest request = new AnalyzeRequest("op.gg");

        assertThat(request.url()).isEqualTo("https://op.gg");
    }

    @Test
    void preservesExplicitHttpOrHttpsScheme() {
        assertThat(new AnalyzeRequest("https://example.com").url())
                .isEqualTo("https://example.com");
        assertThat(new AnalyzeRequest("http://example.com").url())
                .isEqualTo("http://example.com");
    }

    @Test
    void trimsSurroundingWhitespaceBeforeNormalizing() {
        AnalyzeRequest request = new AnalyzeRequest("  example.org/path  ");

        assertThat(request.url()).isEqualTo("https://example.org/path");
    }
}
