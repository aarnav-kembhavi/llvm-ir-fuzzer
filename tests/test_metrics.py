import json
import pytest
from evaluate.metrics import MetricsEngine

def test_metrics_empty(tmp_path):
    engine = MetricsEngine()
    
    # Missing file
    metrics = engine.compute("nonexistent.jsonl")
    assert metrics.total == 0
    
    # Empty file
    empty_path = tmp_path / "empty.jsonl"
    empty_path.write_text("")
    metrics = engine.compute(str(empty_path))
    assert metrics.total == 0

def test_metrics_computation(tmp_path):
    jsonl_path = tmp_path / "summary.jsonl"
    
    entries = [
        {"iteration": 1, "valid_mutant": True, "verdict": "DIVERGENT"},
        {"iteration": 2, "valid_mutant": True, "verdict": "IDENTICAL"},
        {"iteration": 3, "valid_mutant": True, "verdict": "CRASH"},
        {"iteration": 4, "valid_mutant": True, "verdict": "INVALID"},
        {"iteration": 5, "valid_mutant": False, "verdict": "SKIPPED"},
        {"iteration": 6, "valid_mutant": False, "verdict": "SKIPPED"}
    ]
    
    with open(jsonl_path, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")
            
    engine = MetricsEngine()
    metrics = engine.compute(str(jsonl_path))
    
    assert metrics.total == 6
    assert metrics.valid_mutants == 4
    assert metrics.crashes == 1
    assert metrics.post_opt_invalid == 1
    assert metrics.divergent == 1
    assert metrics.identical == 1
    assert metrics.parse_failures == 2
    
    assert metrics.valid_mutant_rate == 4/6
    assert metrics.crash_rate == 1/4
    assert metrics.invalid_after_opt_rate == 1/4
    assert metrics.bug_candidate_rate == 2/4
    assert metrics.divergence_rate == 1/4
    assert metrics.discard_rate == 2/6

def test_metrics_timing_fields(tmp_path):
    """Phase 9: timing fields are computed correctly from JSONL entries."""
    jsonl_path = tmp_path / "timed.jsonl"
    entries = [
        {"iteration": 1, "valid_mutant": True, "verdict": "DIVERGENT", "iteration_time_seconds": 2.0},
        {"iteration": 2, "valid_mutant": True, "verdict": "DIVERGENT", "iteration_time_seconds": 4.0},
        {"iteration": 3, "valid_mutant": False, "verdict": "SKIPPED"},  # missing time — treated as 0
    ]
    with open(jsonl_path, "w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")

    engine = MetricsEngine()
    metrics = engine.compute(str(jsonl_path))

    assert metrics.total_time_seconds == pytest.approx(6.0, abs=0.01)
    assert metrics.avg_time_per_iteration == pytest.approx(2.0, abs=0.01)

def test_metrics_timing_all_missing(tmp_path):
    """Phase 9: timing is 0 when no entry has the field."""
    jsonl_path = tmp_path / "notimed.jsonl"
    entries = [
        {"iteration": 1, "valid_mutant": True, "verdict": "DIVERGENT"},
    ]
    with open(jsonl_path, "w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")

    metrics = MetricsEngine().compute(str(jsonl_path))
    assert metrics.total_time_seconds == 0.0
    assert metrics.avg_time_per_iteration == 0.0
