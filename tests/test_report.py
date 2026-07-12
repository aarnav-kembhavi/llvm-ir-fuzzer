import json
import os
import pytest
from evaluate.metrics import PipelineMetrics
from evaluate.report import ReportGenerator

def test_save_report(tmp_path):
    report_path = tmp_path / "summary_report.json"
    generator = ReportGenerator()
    
    llm_metrics = PipelineMetrics(
        total=10, valid_mutants=10, crashes=0, post_opt_invalid=0,
        divergent=10, identical=0, inconclusive=0, parse_failures=0,
        valid_mutant_rate=1.0, crash_rate=0.0, invalid_after_opt_rate=0.0,
        bug_candidate_rate=0.0, divergence_rate=1.0, discard_rate=0.0,
        total_time_seconds=15.0, avg_time_per_iteration=1.5, unique_mutants=10,
        semantic_bugs=0, exec_matches=0
    )
    
    baseline_metrics = PipelineMetrics(
        total=10, valid_mutants=6, crashes=0, post_opt_invalid=0,
        divergent=6, identical=0, inconclusive=0, parse_failures=0,
        valid_mutant_rate=0.6, crash_rate=0.0, invalid_after_opt_rate=0.0,
        bug_candidate_rate=0.0, divergence_rate=1.0, discard_rate=0.4,
        total_time_seconds=2.0, avg_time_per_iteration=0.2, unique_mutants=6,
        semantic_bugs=0, exec_matches=0
    )
    
    generator.save_report(str(report_path), llm_metrics, baseline_metrics)
    
    assert report_path.exists()
    
    with open(report_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    assert "timestamp" in data
    assert "llm_metrics" in data
    assert "baseline_metrics" in data
    
    assert data["llm_metrics"]["total"] == 10
    assert data["baseline_metrics"]["valid_mutants"] == 6
