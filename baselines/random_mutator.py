import random
import re
from typing import Optional
from src.mutation_planner import MutationPlan

class RandomMutator:
    def __init__(self):
        self.opcodes = ["add", "sub", "mul", "sdiv", "udiv", "shl", "lshr", "ashr", "and", "or", "xor"]
        
    def generate_plan(self, seed_ir: str) -> Optional[MutationPlan]:
        lines = seed_ir.splitlines()
        
        # Find lines with instructions
        # A simple heuristic: lines containing an '=' or starting with an instruction keyword
        instruction_lines = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            # Ignore labels, comments, braces, declarations
            if not stripped or stripped.startswith(";") or stripped.startswith("define") \
               or stripped.startswith("declare") or stripped.endswith(":") or stripped in ["{", "}"]:
                continue
            instruction_lines.append((i, line))
            
        if not instruction_lines:
            return None
            
        # Pick a random instruction
        line_idx, orig_line = random.choice(instruction_lines)
        
        # Try mutations:
        mutated_line = orig_line
        desc = ""
        
        # 1. Flip a constant (e.g., 5 -> 6)
        constants = re.findall(r'\b\d+\b', orig_line)
        if constants and random.random() < 0.33:
            target = random.choice(constants)
            new_val = str(int(target) + 1)
            # Replace exactly the first occurrence of that constant (naive but simple)
            mutated_line = re.sub(r'\b' + target + r'\b', new_val, orig_line, count=1)
            desc = f"Random Baseline: Flipped constant {target} to {new_val}"
            
        # 2. Swap an opcode
        elif any(op in orig_line for op in self.opcodes) and random.random() < 0.5:
            for op in self.opcodes:
                if f" {op} " in orig_line or f"={op} " in orig_line or f"= {op} " in orig_line:
                    new_op = random.choice([o for o in self.opcodes if o != op])
                    mutated_line = orig_line.replace(op, new_op, 1)
                    desc = f"Random Baseline: Swapped opcode {op} with {new_op}"
                    break
                    
        # 3. If neither worked (or skipped), delete the line (empty replacement)
        if mutated_line == orig_line:
            mutated_line = ""
            desc = "Random Baseline: Deleted line"
            
        return MutationPlan(
            description=desc,
            line_number=line_idx + 1,
            original_line=orig_line,
            mutated_line=mutated_line
        )
