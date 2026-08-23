package com.phishing.backend.service;

import com.phishing.backend.dto.AnalysisJobResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.io.ObjectInputStream;
import java.io.ObjectOutputStream;
import java.nio.file.AtomicMoveNotSupportedException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.Optional;
import java.util.regex.Pattern;

@Component
public class FileAnalysisJobStore implements AnalysisJobStore {

    private static final Logger log = LoggerFactory.getLogger(FileAnalysisJobStore.class);
    private static final Pattern ANALYSIS_ID_PATTERN = Pattern.compile(
            "^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
            Pattern.CASE_INSENSITIVE
    );

    private final Path storageDirectory;

    public FileAnalysisJobStore(
            @Value("${analysis.job-storage-dir:/data/jobs}") String storageDirectory
    ) {
        this.storageDirectory = Path.of(storageDirectory).toAbsolutePath().normalize();

        try {
            Files.createDirectories(this.storageDirectory);
        } catch (IOException exception) {
            throw new IllegalStateException("분석 Job 저장 디렉터리를 생성할 수 없습니다.", exception);
        }
    }

    @Override
    public synchronized void save(AnalysisJobResponse job) {
        validateAnalysisId(job.analysisId());
        Path target = resolveJobPath(job.analysisId());
        Path temporary = storageDirectory.resolve(job.analysisId() + ".tmp");

        try {
            try (ObjectOutputStream output = new ObjectOutputStream(Files.newOutputStream(temporary))) {
                output.writeObject(job);
                output.flush();
            }

            try {
                Files.move(
                        temporary,
                        target,
                        StandardCopyOption.ATOMIC_MOVE,
                        StandardCopyOption.REPLACE_EXISTING
                );
            } catch (AtomicMoveNotSupportedException ignored) {
                Files.move(temporary, target, StandardCopyOption.REPLACE_EXISTING);
            }
        } catch (IOException exception) {
            try {
                Files.deleteIfExists(temporary);
            } catch (IOException cleanupException) {
                log.warn("Temporary Job file cleanup failed: analysisId={}", job.analysisId());
            }
            throw new IllegalStateException("분석 Job을 저장할 수 없습니다.", exception);
        }
    }

    @Override
    public synchronized Optional<AnalysisJobResponse> find(String analysisId) {
        if (!ANALYSIS_ID_PATTERN.matcher(analysisId).matches()) {
            return Optional.empty();
        }

        Path target = resolveJobPath(analysisId);

        if (!Files.isRegularFile(target)) {
            return Optional.empty();
        }

        try (ObjectInputStream input = new ObjectInputStream(Files.newInputStream(target))) {
            Object value = input.readObject();

            if (value instanceof AnalysisJobResponse job) {
                return Optional.of(job);
            }

            log.error("Invalid Job file content: analysisId={}", analysisId);
            return Optional.empty();
        } catch (IOException | ClassNotFoundException exception) {
            log.error("Job file read failed: analysisId={}", analysisId, exception);
            return Optional.empty();
        }
    }

    private Path resolveJobPath(String analysisId) {
        Path target = storageDirectory.resolve(analysisId + ".job").normalize();

        if (!target.startsWith(storageDirectory)) {
            throw new IllegalArgumentException("허용되지 않은 분석 Job 경로입니다.");
        }

        return target;
    }

    private void validateAnalysisId(String analysisId) {
        if (!ANALYSIS_ID_PATTERN.matcher(analysisId).matches()) {
            throw new IllegalArgumentException("analysisId 형식이 올바르지 않습니다.");
        }
    }
}
