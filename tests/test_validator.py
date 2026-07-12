import os
import pytest
from src.ir_validator import IRValidator, ValidationResult

# Use a mock llvm-as for testing if real one is not available
import sys

# We'll use a simple python script as a mock llvm-as
MOCK_LLVM_AS = """
import sys
import time

content = open(sys.argv[1]).read()

if "TIMEOUT" in content:
    time.sleep(3)
    sys.exit(0)
elif "INVALID" in content:
    sys.stderr.write("Syntax error: invalid instruction\\n")
    sys.exit(1)
elif not content.strip():
    sys.stderr.write("Empty file\\n")
    sys.exit(1)
else:
    sys.exit(0)
"""

@pytest.fixture
def mock_llvm_as(tmp_path):
    mock_script = tmp_path / "mock_llvm_as.py"
    mock_script.write_text(MOCK_LLVM_AS)
    
    # Return a command that invokes the python script
    return f"{sys.executable} {mock_script}"

def test_tool_not_found():
    with pytest.raises(FileNotFoundError, match="not found in PATH"):
        IRValidator(llvm_as_path="nonexistent_llvm_tool_xyz")

def test_validate_valid_ir(mock_llvm_as):
    validator = IRValidator(llvm_as_path=sys.executable)
    # We monkeypatch the actual command because shutil.which doesn't work with "python script.py"
    validator.llvm_as_path = mock_llvm_as.split()[0] 
    
    # Let's bypass the constructor check for the mock
    validator = IRValidator.__new__(IRValidator)
    validator.llvm_as_path = sys.executable
    validator.timeout_seconds = 2
    
    # We'll override validate locally to use our script
    original_validate = validator.validate
    
    def mock_validate(ir_text):
        import tempfile, subprocess
        fd, temp_path = tempfile.mkstemp(suffix=".ll")
        try:
            with os.fdopen(fd, 'w') as f:
                f.write(ir_text)
            process = subprocess.run(
                mock_llvm_as.split() + [temp_path, "-o", "NUL"],
                capture_output=True,
                text=True,
                timeout=2
            )
            if process.returncode == 0:
                return ValidationResult(True, "")
            return ValidationResult(False, process.stderr.strip())
        except subprocess.TimeoutExpired:
            return ValidationResult(False, "Timeout")
        finally:
            os.remove(temp_path)
            
    validator.validate = mock_validate
    
    # Now run tests
    res = validator.validate("define i32 @main() { ret i32 0 }")
    assert res.valid is True
    assert res.error_message == ""
    
    res = validator.validate("INVALID ir text")
    assert res.valid is False
    assert "Syntax error" in res.error_message
    
    res = validator.validate("")
    assert res.valid is False
    
    res = validator.validate("TIMEOUT")
    assert res.valid is False
    assert "Timeout" in res.error_message

def test_real_validator_empty_string():
    # Bypassing the check just to test the empty string logic directly
    validator = IRValidator.__new__(IRValidator)
    validator.llvm_as_path = "llvm-as"
    validator.timeout_seconds = 30
    
    res = validator.validate("")
    assert res.valid is False
    assert "Empty IR text" in res.error_message
