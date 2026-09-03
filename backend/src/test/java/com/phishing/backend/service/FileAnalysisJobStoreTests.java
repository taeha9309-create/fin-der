package com.phishing.backend.service;

import com.phishing.backend.dto.AnalysisJobResponse;
import com.phishing.backend.dto.AnalysisStatus;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Path;
import java.time.Instant;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

class FileAnalysisJobStoreTests {

    @TempDir
    Path temporaryDirectory;

    @Test
    void savedJobsCanBeListedAndDeleted() {
        FileAnalysisJobStore store = new FileAnalysisJobStore(temporaryDirectory.toString());
        String analysisId = UUID.randomUUID().toString();
        Instant now = Instant.now();
        AnalysisJobResponse job = new AnalysisJobResponse(
                analysisId,
                AnalysisStatus.COMPLETED,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                now,
                now
        );

        store.save(job);

        assertThat(store.findAll()).containsExactly(job);

        store.delete(analysisId);

        assertThat(store.find(analysisId)).isEmpty();
        assertThat(store.findAll()).isEmpty();
    }
}
