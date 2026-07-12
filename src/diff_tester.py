import subprocess
from collections import namedtuple
from typing import Optional

DiffResult = namedtuple("DiffResult", ["o0_ir", "o0_rc", "o3_ir", "o3_rc", "error"])

class DiffTester:
    def __init__(self, opt_path="opt", timeout_seconds=30):
        self.opt_path = opt_path
        self.timeout_seconds = timeout_seconds

    def _run_opt(self, ir_file_path: str, opt_level: str) -> tuple[str, int, Optional[str]]:
        try:
            process = subprocess.run(
                [self.opt_path, opt_level, "-S", ir_file_path],
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds
            )
            return process.stdout, process.returncode, None
        except subprocess.TimeoutExpired:
            return "", -1, f"Timeout after {self.timeout_seconds}s"
        except Exception as e:
            return "", -1, str(e)

    def test(self, ir_file_path: str) -> DiffResult:
        o0_ir, o0_rc, err0 = self._run_opt(ir_file_path, "-O0")
        if err0:
            return DiffResult("", o0_rc, "", -1, err0)
            
        o3_ir, o3_rc, err3 = self._run_opt(ir_file_path, "-O3")
        if err3:
            return DiffResult(o0_ir, o0_rc, "", o3_rc, err3)
            
        return DiffResult(o0_ir, o0_rc, o3_ir, o3_rc, None)
