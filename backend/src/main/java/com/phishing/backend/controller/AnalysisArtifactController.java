package com.phishing.backend.controller;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;
import java.util.UUID;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.CacheControl;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import static org.springframework.http.HttpStatus.BAD_REQUEST;
import static org.springframework.http.HttpStatus.NOT_FOUND;

@RestController
@RequestMapping("/api/analyses/{analysisId}")
public class AnalysisArtifactController {

    private static final Map<String, ArtifactDefinition> ARTIFACTS = Map.of(
            "html", new ArtifactDefinition("page.html", MediaType.TEXT_PLAIN),
            "text", new ArtifactDefinition("page.txt", MediaType.TEXT_PLAIN),
            "screenshot", new ArtifactDefinition("screenshot.png", MediaType.IMAGE_PNG),
            "metadata", new ArtifactDefinition("metadata.json", MediaType.APPLICATION_JSON)
    );

    private final Path storageRoot;

    public AnalysisArtifactController(
            @Value("${sandbox.artifact-storage-dir:/data/analyses}") String storageDirectory
    ) {
        this.storageRoot = Path.of(storageDirectory).toAbsolutePath().normalize();
    }

    @GetMapping("/{artifactType}")
    public ResponseEntity<byte[]> getArtifact(
            @PathVariable String analysisId,
            @PathVariable String artifactType
    ) throws IOException {
        validateAnalysisId(analysisId);

        ArtifactDefinition definition = ARTIFACTS.get(artifactType);
        if (definition == null) {
            throw new ResponseStatusException(NOT_FOUND, "지원하지 않는 분석 파일입니다.");
        }

        Path analysisDirectory = storageRoot.resolve(analysisId).normalize();
        Path artifactPath = analysisDirectory.resolve(definition.fileName()).normalize();

        if (!analysisDirectory.getParent().equals(storageRoot)
                || !artifactPath.getParent().equals(analysisDirectory)) {
            throw new ResponseStatusException(BAD_REQUEST, "분석 파일 경로가 올바르지 않습니다.");
        }

        if (!Files.isRegularFile(artifactPath)) {
            throw new ResponseStatusException(NOT_FOUND, "분석 파일을 찾을 수 없습니다.");
        }

        byte[] content = Files.readAllBytes(artifactPath);
        return ResponseEntity.ok()
                .contentType(definition.mediaType())
                .contentLength(content.length)
                .cacheControl(CacheControl.noStore())
                .header("X-Content-Type-Options", "nosniff")
                .body(content);
    }

    private void validateAnalysisId(String analysisId) {
        try {
            UUID.fromString(analysisId);
        } catch (IllegalArgumentException error) {
            throw new ResponseStatusException(BAD_REQUEST, "analysisId 형식이 올바르지 않습니다.");
        }
    }

    private record ArtifactDefinition(String fileName, MediaType mediaType) {
    }
}
