import pytest
from baselines.random_mutator import RandomMutator
from src.mutation_executor import MutationExecutor

def test_random_mutator_produces_plan():
    mutator = RandomMutator()
    seed_ir = "define i32 @test() {\n  %add = add i32 5, 10\n  ret i32 %add\n}"
    
    # Run multiple times to ensure we hit random paths, but just test 1 run for now
    plan = mutator.generate_plan(seed_ir)
    assert plan is not None
    assert plan.line_number > 0
    assert plan.original_line != ""
    # mutated_line might be "" if it fell back to deletion
    assert isinstance(plan.mutated_line, str)

def test_random_mutator_empty_ir():
    mutator = RandomMutator()
    assert mutator.generate_plan("") is None
    assert mutator.generate_plan(";") is None

def test_random_mutator_integration_with_executor():
    mutator = RandomMutator()
    executor = MutationExecutor()
    
    seed_ir = "define i32 @test() {\n  %add = add i32 5, 10\n  ret i32 %add\n}"
    plan = mutator.generate_plan(seed_ir)
    
    if plan:
        mutant = executor.apply(seed_ir, plan)
        assert mutant is not None
        assert mutant != seed_ir
