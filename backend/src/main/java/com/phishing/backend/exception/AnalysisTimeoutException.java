package com.phishing.backend.exception;

public class AnalysisTimeoutException extends RuntimeException {

    public AnalysisTimeoutException(int timeoutSeconds) {
        super("전체 분석 제한시간 " + timeoutSeconds + "초를 초과했습니다.");
    }
}
