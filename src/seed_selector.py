import random
from typing import List
from src.seed_loader import Seed

class SeedSelector:
    def __init__(self, seeds: List[Seed], strategy: str = "round_robin"):
        if not seeds:
            raise ValueError("SeedSelector initialized with empty seed list.")
        self.seeds = seeds
        self.strategy = strategy
        self.index = 0
        
        # for least_mutated strategy
        self.mutation_counts = {seed.path: 0 for seed in seeds}

    def next(self) -> Seed:
        if self.strategy == "random":
            selected = random.choice(self.seeds)
        elif self.strategy == "least_mutated":
            min_count = min(self.mutation_counts.values())
            candidates = [s for s in self.seeds if self.mutation_counts[s.path] == min_count]
            selected = random.choice(candidates)
        else: # round_robin
            selected = self.seeds[self.index]
            self.index = (self.index + 1) % len(self.seeds)
            
        # Update mutation count
        self.mutation_counts[selected.path] += 1
        return selected
