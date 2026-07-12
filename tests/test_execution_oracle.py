import pytest
from unittest.mock import patch, MagicMock
import subprocess
from src.oracle import Oracle, OracleResult
from src.diff_tester import DiffResult

# Dummy validator that accepts everything
class DummyValidator:
    def validate(self, ir: str):
        result = MagicMock()
        result.valid = True
        return result

@pytest.fixture
def dummy_validator():
    return DummyValidator()

def test_execution_oracle_fallback_no_main(dummy_validator):
    """If no @main is present, should fallback to structural checks."""
    oracle = Oracle(dummy_validator, execution_mode=True)
    
    # Text differs, but no main
    diff = DiffResult(o0_ir="define void @foo() { ret void }", o0_rc=0,
                      o3_ir="define void @foo() { ret void }  ; changed", o3_rc=0, error=None)
    
    result = oracle.classify(diff)
    assert result.verdict == "DIVERGENT"
    assert "Exec skipped (no main)" in result.diff_summary

@patch("src.oracle.subprocess.run")
def test_execution_oracle_exec_match(mock_run, dummy_validator):
    """If execution mode is enabled and outputs match, return EXEC_MATCH."""
    oracle = Oracle(dummy_validator, execution_mode=True)
    
    # Setup mock for compile and run (O0 compile, O0 run, O3 compile, O3 run)
    compile_mock = MagicMock()
    compile_mock.returncode = 0
    run_mock = MagicMock()
    run_mock.returncode = 0
    run_mock.stdout = "hello\n"
    
    mock_run.side_effect = [compile_mock, run_mock, compile_mock, run_mock]
    
    diff = DiffResult(o0_ir="define i32 @main() { ret i32 0 }", o0_rc=0,
                      o3_ir="define i32 @main() { ret i32 0 } ; changed", o3_rc=0, error=None)
    
    result = oracle.classify(diff)
    assert result.verdict == "EXEC_MATCH"
    assert not result.is_bug_candidate
    assert "Execution outputs match" in result.diff_summary

@patch("src.oracle.subprocess.run")
def test_execution_oracle_semantic_bug(mock_run, dummy_validator):
    """If outputs differ, return SEMANTIC_BUG."""
    oracle = Oracle(dummy_validator, execution_mode=True)
    
    compile_mock = MagicMock()
    compile_mock.returncode = 0
    
    run_o0_mock = MagicMock()
    run_o0_mock.returncode = 0
    run_o0_mock.stdout = "hello\n"
    
    run_o3_mock = MagicMock()
    run_o3_mock.returncode = 0
    run_o3_mock.stdout = "world\n"
    
    mock_run.side_effect = [compile_mock, run_o0_mock, compile_mock, run_o3_mock]
    
    diff = DiffResult(o0_ir="define i32 @main() { ret i32 0 }", o0_rc=0,
                      o3_ir="define i32 @main() { ret i32 0 } ; diff", o3_rc=0, error=None)
    
    result = oracle.classify(diff)
    assert result.verdict == "SEMANTIC_BUG"
    assert result.is_bug_candidate
    assert "Exec mismatch" in result.diff_summary

@patch("src.oracle.subprocess.run")
def test_execution_oracle_o3_compile_fails(mock_run, dummy_validator):
    """If O3 fails to compile but O0 succeeded, return SEMANTIC_BUG."""
    oracle = Oracle(dummy_validator, execution_mode=True)
    
    compile_o0_mock = MagicMock()
    compile_o0_mock.returncode = 0
    run_o0_mock = MagicMock()
    run_o0_mock.returncode = 0
    
    compile_o3_mock = MagicMock()
    compile_o3_mock.returncode = 1
    compile_o3_mock.stderr = "error"
    
    mock_run.side_effect = [compile_o0_mock, run_o0_mock, compile_o3_mock]
    
    diff = DiffResult(o0_ir="define i32 @main() { ret i32 0 }", o0_rc=0,
                      o3_ir="define i32 @main() { ret i32 0 } ; diff", o3_rc=0, error=None)
    
    result = oracle.classify(diff)
    assert result.verdict == "SEMANTIC_BUG"
    assert result.is_bug_candidate
    assert "O3 exec failed" in result.diff_summary

@patch("src.oracle.subprocess.run")
def test_execution_oracle_timeout(mock_run, dummy_validator):
    """If execution times out on O0, it should fallback safely."""
    oracle = Oracle(dummy_validator, execution_mode=True)
    
    compile_o0_mock = MagicMock()
    compile_o0_mock.returncode = 0
    
    # O0 run times out
    def side_effect(*args, **kwargs):
        if "-o" in args[0]: # compile
            return compile_o0_mock
        raise subprocess.TimeoutExpired(cmd="exe", timeout=5)
        
    mock_run.side_effect = side_effect
    
    diff = DiffResult(o0_ir="define i32 @main() { ret i32 0 }", o0_rc=0,
                      o3_ir="define i32 @main() { ret i32 0 } ; diff", o3_rc=0, error=None)
    
    result = oracle.classify(diff)
    # Falls back to structural DIVERGENT since O0 failed
    assert result.verdict == "DIVERGENT"
    assert not result.is_bug_candidate
    assert "O0 exec failed: Execution timeout" in result.diff_summary
