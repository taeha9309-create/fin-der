package com.leveragy.controller;

import com.leveragy.dto.AdminLoginRequest;
import com.leveragy.service.AdminTokenService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import javax.validation.Valid;
import java.util.Map;

@RestController
@RequestMapping("/api/admin")
public class AdminAuthController {

    private final AdminTokenService adminTokenService;

    public AdminAuthController(AdminTokenService adminTokenService) {
        this.adminTokenService = adminTokenService;
    }

    @PostMapping("/login")
    public ResponseEntity<Map<String, String>> login(@Valid @RequestBody AdminLoginRequest request) {
        String token = adminTokenService.login(request.getUsername(), request.getPassword());
        if (token == null) {
            return ResponseEntity.status(401).body(Map.of("message", "아이디 또는 비밀번호가 올바르지 않습니다."));
        }
        return ResponseEntity.ok(Map.of("token", token));
    }

    @PostMapping("/logout")
    public ResponseEntity<Void> logout(@RequestHeader(value = "Authorization", required = false) String authorization) {
        adminTokenService.logout(AdminTokenService.extractBearerToken(authorization));
        return ResponseEntity.noContent().build();
    }
}
