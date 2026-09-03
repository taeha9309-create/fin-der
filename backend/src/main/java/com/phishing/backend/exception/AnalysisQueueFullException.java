package com.phishing.backend.exception;

public class AnalysisQueueFullException extends RuntimeException {

    public AnalysisQueueFullException() {
        super("분석 대기열이 가득 찼습니다.");
    }
}
