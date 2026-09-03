package com.phishing.backend.dto;

import java.io.Serializable;

public record ArtifactLinks(
        String html,
        String text,
        String screenshot,
        String metadata
) implements Serializable {
}
