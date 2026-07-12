import os
import json
import pytest
from src.logger import Logger
from src.mutation_planner import MutationPlan
from src.ir_validator import ValidationResult
from src.oracle import OracleResult

def test_logger_initialization(tmp_path):
    logger = Logger(base_dir=str(tmp_path))
    assert logger.run_dir.startswith(str(tmp_path))
    assert "run_" in logger.run_dir
    assert os.path.exists(logger.run_dir)
    assert logger.summary_file.endswith("run_summary.jsonl")

def test_log_iteration_full(tmp_path):
    logger = Logger(base_dir=str(tmp_path))
    
    plan = MutationPlan("desc", 1, "orig", "mut")
    val = ValidationResult(True, "")
    oracle = OracleResult("DIVERGENT", False, "diff")
    
    logger.log_iteration(
        iteration=1,
        seed_path="test.ll",
        seed_ir="seed content",
        prompt="prompt content",
        plan=plan,
        mutant_ir="mutant content",
        validation=val,
        oracle=oracle
    )
    
    iter_dir = os.path.join(logger.run_dir, "iter_001")
    assert os.path.exists(iter_dir)
    
    assert os.path.exists(os.path.join(iter_dir, "seed.ll"))
    assert os.path.exists(os.path.join(iter_dir, "prompt.txt"))
    assert os.path.exists(os.path.join(iter_dir, "mutation_plan.json"))
    assert os.path.exists(os.path.join(iter_dir, "mutant.ll"))
    assert os.path.exists(os.path.join(iter_dir, "validation.log"))
    assert os.path.exists(os.path.join(iter_dir, "oracle_result.json"))
    
    assert os.path.exists(logger.summary_file)
    with open(logger.summary_file, "r") as f:
        lines = f.readlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["iteration"] == 1
        assert data["seed_path"] == "test.ll"
        assert data["valid_mutant"] is True
        assert data["verdict"] == "DIVERGENT"
        assert data["is_bug_candidate"] is False

def test_log_iteration_partial(tmp_path):
    logger = Logger(base_dir=str(tmp_path))
    
    # Missing optional items
    logger.log_iteration(
        iteration=2,
        seed_path="test2.ll",
        seed_ir="seed"
    )
    
    iter_dir = os.path.join(logger.run_dir, "iter_002")
    assert os.path.exists(iter_dir)
    assert os.path.exists(os.path.join(iter_dir, "seed.ll"))
    assert not os.path.exists(os.path.join(iter_dir, "prompt.txt"))
    assert not os.path.exists(os.path.join(iter_dir, "oracle_result.json"))
    
    with open(logger.summary_file, "r") as f:
        data = json.loads(f.readline())
        assert data["verdict"] == "SKIPPED"

def test_logger_disk_failure(monkeypatch, tmp_path):
    # Simulate a failure during directory creation
    def mock_makedirs(*args, **kwargs):
        raise OSError("Mock disk full")
        
    monkeypatch.setattr(os, "makedirs", mock_makedirs)
    
    # Initialization should fail gracefully and not crash
    logger = Logger(base_dir=str(tmp_path))
    
    # log_iteration should also fail gracefully
    logger.log_iteration(1, "test.ll", "ir")

def test_log_iteration_records_timing(tmp_path):
    """Phase 9: iteration_time_seconds is recorded in the JSONL summary entry."""
    logger = Logger(base_dir=str(tmp_path))
    oracle = OracleResult("DIVERGENT", False, "diff")
    val = ValidationResult(True, "")

    logger.log_iteration(
        iteration=1,
        seed_path="seed.ll",
        seed_ir="ir",
        oracle=oracle,
        validation=val,
        iteration_time_seconds=3.14159,
    )

    with open(logger.summary_file, "r") as f:
        data = json.loads(f.readline())

    assert "iteration_time_seconds" in data
    assert abs(data["iteration_time_seconds"] - 3.142) < 0.001

def test_log_iteration_timing_none(tmp_path):
    """Phase 9: iteration_time_seconds is None when not provided."""
    logger = Logger(base_dir=str(tmp_path))
    logger.log_iteration(iteration=1, seed_path="s.ll", seed_ir="ir")

    with open(logger.summary_file, "r") as f:
        data = json.loads(f.readline())

    assert data["iteration_time_seconds"] is None

