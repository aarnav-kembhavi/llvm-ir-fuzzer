import hashlib
from typing import Optional
from src.mutation_planner import MutationPlan

class MutationExecutor:
    @staticmethod
    def compute_hash(ir_text: str) -> str:
        """Return a SHA-256 hex digest of the mutant IR text for deduplication."""
        return hashlib.sha256(ir_text.encode("utf-8")).hexdigest()

    def apply(self, seed_ir: str, plan: MutationPlan) -> Optional[str]:
        lines = seed_ir.splitlines()
        
        if not lines:
            return None
            
        # Target index is line_number - 1
        target_idx = plan.line_number - 1
        
        # Primary Path: Line-number-indexed replacement
        if 0 <= target_idx < len(lines):
            # Check if the line matches (stripping whitespace to be safe)
            if lines[target_idx].strip() == plan.original_line.strip():
                if plan.mutated_line.strip() == "":
                    # Empty replacement -> Delete
                    del lines[target_idx]
                else:
                    lines[target_idx] = plan.mutated_line
                return "\n".join(lines) + "\n"
        
        # Fallback Path: Exact string search
        for i, line in enumerate(lines):
            if line.strip() == plan.original_line.strip():
                if plan.mutated_line.strip() == "":
                    del lines[i]
                else:
                    lines[i] = plan.mutated_line
                return "\n".join(lines) + "\n"
                
        # If neither path succeeds, the mutation fails
        return None

