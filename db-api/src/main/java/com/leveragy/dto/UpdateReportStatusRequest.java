package com.leveragy.dto;

import javax.validation.constraints.NotBlank;
import javax.validation.constraints.Pattern;

public class UpdateReportStatusRequest {

    @NotBlank(message = "status는 필수입니다.")
    @Pattern(
            regexp = "PENDING|CONFIRMED_PHISHING|FALSE_POSITIVE",
            message = "status는 PENDING, CONFIRMED_PHISHING, FALSE_POSITIVE 중 하나여야 합니다."
    )
    private String status;

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
}
