import os
import tempfile
import subprocess
import shutil
from collections import namedtuple

ValidationResult = namedtuple("ValidationResult", ["valid", "error_message"])

class IRValidator:
    def __init__(self, llvm_as_path="llvm-as", timeout_seconds=30):
        self.llvm_as_path = llvm_as_path
        self.timeout_seconds = timeout_seconds
        self._check_tool_exists()

    def _check_tool_exists(self):
        if not shutil.which(self.llvm_as_path):
            raise FileNotFoundError(
                f"Error: '{self.llvm_as_path}' not found in PATH or specified location.\n"
                "Please ensure LLVM is installed and the tool is available."
            )

    def validate(self, ir_text: str) -> ValidationResult:
        if not ir_text or not ir_text.strip():
            return ValidationResult(valid=False, error_message="Empty IR text")

        fd, temp_path = tempfile.mkstemp(suffix=".ll")
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(ir_text)

            # We output to NUL to discard the bitcode since we only care if it parses
            devnull = "NUL" if os.name == "nt" else "/dev/null"
            
            process = subprocess.run(
                [self.llvm_as_path, temp_path, "-o", devnull],
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds
            )
            
            if process.returncode == 0:
                return ValidationResult(valid=True, error_message="")
            else:
                return ValidationResult(valid=False, error_message=process.stderr.strip())
                
        except subprocess.TimeoutExpired:
            return ValidationResult(valid=False, error_message=f"Timeout: llvm-as took longer than {self.timeout_seconds}s")
        except Exception as e:
            return ValidationResult(valid=False, error_message=str(e))
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
