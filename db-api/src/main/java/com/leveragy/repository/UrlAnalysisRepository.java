package com.leveragy.repository;

import com.leveragy.entity.UrlAnalysis;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface UrlAnalysisRepository extends JpaRepository<UrlAnalysis, Long> {
    List<UrlAnalysis> findAllByOrderByCreatedAtDesc();
}
