import pytest
from src.diff_tester import DiffResult
from src.ir_validator import IRValidator, ValidationResult
from src.oracle import Oracle

class MockValidator(IRValidator):
    def __init__(self, mock_results=None):
        self.mock_results = mock_results or {}

    def validate(self, ir_text: str) -> ValidationResult:
        if ir_text in self.mock_results:
            return self.mock_results[ir_text]
        return ValidationResult(valid=True, error_message="")

def test_oracle_identical():
    validator = MockValidator()
    oracle = Oracle(validator)
    
    diff = DiffResult(o0_ir="same", o0_rc=0, o3_ir="same", o3_rc=0, error=None)
    result = oracle.classify(diff)
    
    assert result.verdict == "IDENTICAL"
    assert result.is_bug_candidate is False

def test_oracle_divergent():
    validator = MockValidator()
    oracle = Oracle(validator)
    
    diff = DiffResult(o0_ir="original", o0_rc=0, o3_ir="optimized", o3_rc=0, error=None)
    result = oracle.classify(diff)
    
    assert result.verdict == "DIVERGENT"
    assert result.is_bug_candidate is False

def test_oracle_crash_o0():
    validator = MockValidator()
    oracle = Oracle(validator)
    
    diff = DiffResult(o0_ir="", o0_rc=139, o3_ir="valid", o3_rc=0, error=None)
    result = oracle.classify(diff)
    
    assert result.verdict == "CRASH"
    assert result.is_bug_candidate is True

def test_oracle_crash_o3():
    validator = MockValidator()
    oracle = Oracle(validator)
    
    diff = DiffResult(o0_ir="valid", o0_rc=0, o3_ir="", o3_rc=1, error=None)
    result = oracle.classify(diff)
    
    assert result.verdict == "CRASH"
    assert result.is_bug_candidate is True

def test_oracle_crash_both():
    validator = MockValidator()
    oracle = Oracle(validator)
    
    diff = DiffResult(o0_ir="", o0_rc=1, o3_ir="", o3_rc=1, error=None)
    result = oracle.classify(diff)
    
    assert result.verdict == "CRASH"
    assert result.is_bug_candidate is True

def test_oracle_invalid_o3():
    validator = MockValidator({
        "bad_opt_ir": ValidationResult(valid=False, error_message="mock error")
    })
    oracle = Oracle(validator)
    
    diff = DiffResult(o0_ir="good_ir", o0_rc=0, o3_ir="bad_opt_ir", o3_rc=0, error=None)
    result = oracle.classify(diff)
    
    assert result.verdict == "INVALID"
    assert result.is_bug_candidate is True

def test_oracle_inconclusive_error():
    validator = MockValidator()
    oracle = Oracle(validator)
    
    diff = DiffResult(o0_ir="", o0_rc=-1, o3_ir="", o3_rc=-1, error="Timeout")
    result = oracle.classify(diff)
    
    assert result.verdict == "INCONCLUSIVE"
    assert result.is_bug_candidate is False

def test_oracle_inconclusive_empty():
    validator = MockValidator()
    oracle = Oracle(validator)
    
    diff = DiffResult(o0_ir="  \n ", o0_rc=0, o3_ir="", o3_rc=0, error=None)
    result = oracle.classify(diff)
    
    assert result.verdict == "INCONCLUSIVE"
    assert result.is_bug_candidate is False
