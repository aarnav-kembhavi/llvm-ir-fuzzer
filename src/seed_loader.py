import os
from collections import namedtuple
from typing import List

Seed = namedtuple("Seed", ["path", "ir_text", "pattern_type"])

class SeedLoader:
    def __init__(self, seed_dir: str):
        self.seed_dir = seed_dir

    def load_all(self) -> List[Seed]:
        if not os.path.isdir(self.seed_dir):
            raise FileNotFoundError(f"Seed directory not found: {self.seed_dir}")
        
        seeds = []
        for filename in sorted(os.listdir(self.seed_dir)):
            if filename.endswith(".ll"):
                path = os.path.join(self.seed_dir, filename)
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # Extract pattern type from the first line comment
                pattern_type = "unknown"
                first_line = content.splitlines()[0] if content else ""
                if first_line.startswith("; Pattern:"):
                    pattern_type = first_line.replace("; Pattern:", "").strip()
                
                seeds.append(Seed(path=path, ir_text=content, pattern_type=pattern_type))
        
        if not seeds:
            raise ValueError(f"No .ll files found in {self.seed_dir}")
            
        return seeds
