import hashlib
import os
import subprocess
import tempfile
from collections import namedtuple
from src.diff_tester import DiffResult
from src.ir_validator import IRValidator

OracleResult = namedtuple("OracleResult", ["verdict", "is_bug_candidate", "diff_summary"])

class Oracle:
    def __init__(self, validator: IRValidator, execution_mode: bool = False, compiler_path: str = "clang", timeout_seconds: int = 5):
        self.validator = validator
        self.execution_mode = execution_mode
        self.compiler_path = compiler_path
        self.timeout_seconds = timeout_seconds

    def _hash(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _compile_and_run(self, ir_text: str) -> tuple[int, str]:
        """Compile IR to executable and run it. Returns (return_code, stdout_or_error_msg). (-1, err) for build/run failures."""
        with tempfile.TemporaryDirectory() as temp_dir:
            ir_path = os.path.join(temp_dir, "temp.ll")
            exe_path = os.path.join(temp_dir, "temp.exe")
            with open(ir_path, "w", encoding="utf-8") as f:
                f.write(ir_text)
                
            # Compile using clang
            try:
                compile_res = subprocess.run([self.compiler_path, ir_path, "-o", exe_path], capture_output=True, text=True, timeout=self.timeout_seconds)
                if compile_res.returncode != 0:
                    return -1, f"Compile failed: {compile_res.stderr.strip()[:50]}"
            except FileNotFoundError:
                return -1, "Compiler not found"
            except subprocess.TimeoutExpired:
                return -1, "Compile timeout"
            except Exception as e:
                return -1, f"Compile error: {e}"
                
            # Execute
            try:
                run_res = subprocess.run([exe_path], capture_output=True, text=True, timeout=self.timeout_seconds)
                return run_res.returncode, run_res.stdout
            except subprocess.TimeoutExpired:
                return -1, "Execution timeout"
            except Exception as e:
                return -1, f"Execution error: {e}"

    def classify(self, diff_result: DiffResult) -> OracleResult:
        # 1. Structural Checks (Mode A defaults)
        if diff_result.error:
            return OracleResult(verdict="INCONCLUSIVE", is_bug_candidate=False, diff_summary=diff_result.error)
            
        if diff_result.o0_rc != 0 or diff_result.o3_rc != 0:
            summary = f"O0 rc: {diff_result.o0_rc}, O3 rc: {diff_result.o3_rc}"
            return OracleResult(verdict="CRASH", is_bug_candidate=True, diff_summary=summary)

        if not diff_result.o0_ir.strip() and not diff_result.o3_ir.strip():
            return OracleResult(verdict="INCONCLUSIVE", is_bug_candidate=False, diff_summary="Both outputs empty")

        val_result = self.validator.validate(diff_result.o3_ir)
        if not val_result.valid:
            summary = f"O3 output is invalid IR: {val_result.error_message[:100]}"
            return OracleResult(verdict="INVALID", is_bug_candidate=True, diff_summary=summary)

        h0 = self._hash(diff_result.o0_ir)
        h3 = self._hash(diff_result.o3_ir)
        is_structurally_identical = (h0 == h3)
        structural_verdict = "IDENTICAL" if is_structurally_identical else "DIVERGENT"

        if not self.execution_mode:
            return OracleResult(
                verdict=structural_verdict, 
                is_bug_candidate=False, 
                diff_summary="Expected optimization difference" if not is_structurally_identical else ""
            )

        # 2. Execution Checks (Mode B)
        # Require 'main' function existence to consider execution
        has_main = "@main(" in diff_result.o0_ir or "@main " in diff_result.o0_ir
        if not has_main:
            return OracleResult(
                verdict=structural_verdict, 
                is_bug_candidate=False, 
                diff_summary="Exec skipped (no main); structurally " + structural_verdict
            )

        # Execute both
        rc0, out0 = self._compile_and_run(diff_result.o0_ir)
        if rc0 == -1:
            return OracleResult(
                verdict=structural_verdict, 
                is_bug_candidate=False, 
                diff_summary=f"O0 exec failed: {out0}; fallback to {structural_verdict}"
            )
            
        rc3, out3 = self._compile_and_run(diff_result.o3_ir)
        if rc3 == -1:
            # If O3 compilation/execution fails but O0 succeeded, this is a compiler bug in O3
            return OracleResult(
                verdict="SEMANTIC_BUG",
                is_bug_candidate=True,
                diff_summary=f"O3 exec failed ({out3}) while O0 succeeded"
            )
            
        # Semantic diffing
        if rc0 != rc3 or out0 != out3:
            return OracleResult(
                verdict="SEMANTIC_BUG",
                is_bug_candidate=True,
                diff_summary=f"Exec mismatch: O0(rc={rc0}, out='{out0.strip()[:20]}') vs O3(rc={rc3}, out='{out3.strip()[:20]}')"
            )
            
        # Semantic identical
        return OracleResult(
            verdict="EXEC_MATCH", 
            is_bug_candidate=False, 
            diff_summary=f"Execution outputs match. Structural: {structural_verdict}"
        )
