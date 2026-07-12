import os
import json
import time
from datetime import datetime
from typing import Optional, Dict, Any
from src.mutation_planner import MutationPlan
from src.ir_validator import ValidationResult
from src.oracle import OracleResult

class Logger:
    def __init__(self, base_dir="artifacts"):
        self.base_dir = base_dir
        self.run_dir = ""
        self.summary_file = ""
        self._initialize_run()

    def _initialize_run(self):
        try:
            if not os.path.exists(self.base_dir):
                os.makedirs(self.base_dir, exist_ok=True)
                
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.run_dir = os.path.join(self.base_dir, f"run_{timestamp}")
            os.makedirs(self.run_dir, exist_ok=True)
            
            self.summary_file = os.path.join(self.run_dir, "run_summary.jsonl")
        except Exception as e:
            print(f"[Logger] Failed to initialize run directory: {e}")

    def log_iteration(self, 
                      iteration: int, 
                      seed_path: str, 
                      seed_ir: str, 
                      prompt: Optional[str] = None,
                      plan: Optional[MutationPlan] = None,
                      mutant_ir: Optional[str] = None,
                      validation: Optional[ValidationResult] = None,
                      oracle: Optional[OracleResult] = None,
                      iteration_time_seconds: Optional[float] = None,
                      mutant_hash: Optional[str] = None):
        try:
            if not self.run_dir:
                return

            iter_dir = os.path.join(self.run_dir, f"iter_{iteration:03d}")
            os.makedirs(iter_dir, exist_ok=True)
            
            # Save files
            with open(os.path.join(iter_dir, "seed.ll"), "w", encoding="utf-8") as f:
                f.write(seed_ir or "")
                
            if prompt:
                with open(os.path.join(iter_dir, "prompt.txt"), "w", encoding="utf-8") as f:
                    f.write(prompt)
                    
            if plan:
                with open(os.path.join(iter_dir, "mutation_plan.json"), "w", encoding="utf-8") as f:
                    json.dump(plan._asdict(), f, indent=2)
                    
            if mutant_ir:
                with open(os.path.join(iter_dir, "mutant.ll"), "w", encoding="utf-8") as f:
                    f.write(mutant_ir)
                    
            if validation:
                with open(os.path.join(iter_dir, "validation.log"), "w", encoding="utf-8") as f:
                    f.write(f"Valid: {validation.valid}\n")
                    if validation.error_message:
                        f.write(f"Error:\n{validation.error_message}\n")
                        
            if oracle:
                with open(os.path.join(iter_dir, "oracle_result.json"), "w", encoding="utf-8") as f:
                    json.dump(oracle._asdict(), f, indent=2)
            
            # Write to summary JSONL
            summary_entry: Dict[str, Any] = {
                "iteration": iteration,
                "timestamp": datetime.now().isoformat(),
                "seed_path": seed_path,
                "valid_mutant": validation.valid if validation else False,
                "verdict": oracle.verdict if oracle else "SKIPPED",
                "is_bug_candidate": oracle.is_bug_candidate if oracle else False,
                "iteration_time_seconds": round(iteration_time_seconds, 3) if iteration_time_seconds is not None else None,
                "mutant_hash": mutant_hash,
            }
            
            with open(self.summary_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(summary_entry) + "\n")
                
        except Exception as e:
            print(f"[Logger] Failed to log iteration {iteration}: {e}")

