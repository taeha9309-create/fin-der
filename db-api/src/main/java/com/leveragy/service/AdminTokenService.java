package com.leveragy.service;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 관리자 로그인 세션을 메모리에 보관하는 아주 단순한 토큰 저장소.
 * 계정이 하나뿐인 내부 관리자 도구용이라 DB 대신 메모리로 충분하다 —
 * 백엔드를 재시작하면 세션이 풀려서 다시 로그인해야 한다.
 */
@Service
public class AdminTokenService {

    private static final long TOKEN_TTL_HOURS = 8;

    private final Map<String, Instant> tokenExpiry = new ConcurrentHashMap<>();

    @Value("${app.admin.username}")
    private String adminUsername;

    @Value("${app.admin.password}")
    private String adminPassword;

    public String login(String username, String password) {
        if (adminUsername.equals(username) && adminPassword.equals(password)) {
            String token = UUID.randomUUID().toString();
            tokenExpiry.put(token, Instant.now().plusSeconds(TOKEN_TTL_HOURS * 3600));
            return token;
        }
        return null;
    }

    public boolean isValid(String token) {
        if (token == null) return false;
        Instant expiry = tokenExpiry.get(token);
        if (expiry == null) return false;
        if (Instant.now().isAfter(expiry)) {
            tokenExpiry.remove(token);
            return false;
        }
        return true;
    }

    public void logout(String token) {
        if (token != null) {
            tokenExpiry.remove(token);
        }
    }

    public static String extractBearerToken(String authorizationHeader) {
        if (authorizationHeader == null || !authorizationHeader.startsWith("Bearer ")) {
            return null;
        }
        return authorizationHeader.substring("Bearer ".length()).trim();
    }
}
