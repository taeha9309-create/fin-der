package com.leveragy.repository;

import com.leveragy.entity.Report;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface ReportRepository extends JpaRepository<Report, Long> {
    List<Report> findAllByOrderByCreatedAtDesc();
    List<Report> findAllByStatusOrderByCreatedAtDesc(String status);
}
