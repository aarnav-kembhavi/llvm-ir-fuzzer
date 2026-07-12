import pytest
from src.llm_client import MockClient
from src.mutation_planner import MutationPlanner, MutationPlan
from src.mutation_executor import MutationExecutor

def test_mock_client():
    client = MockClient()
    response = client.generate("some prompt")
    assert '"line_number": 3' in response
    
    assert client.generate("MOCK_FAIL") is None
    assert client.generate("MOCK_NON_JSON") == "This is just text, not json."

def test_mutation_planner(tmp_path):
    # Setup prompt
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("Prompt: {numbered_ir}")
    
    client = MockClient()
    planner = MutationPlanner(client, str(prompt_path))
    
    seed_ir = "line1\nline2\n  %add = add i32 %a, %b\nline4"
    plan = planner.plan(seed_ir)
    
    assert plan is not None
    assert plan.line_number == 3
    assert plan.original_line == "  %add = add i32 %a, %b"
    assert plan.mutated_line == "  %add = sub i32 %a, %b"

def test_mutation_planner_failures(tmp_path):
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("Prompt: {numbered_ir} MOCK_FAIL")
    planner = MutationPlanner(MockClient(), str(prompt_path))
    assert planner.plan("ir") is None
    
    prompt_path.write_text("Prompt: {numbered_ir} MOCK_NON_JSON")
    planner = MutationPlanner(MockClient(), str(prompt_path))
    assert planner.plan("ir") is None

def test_mutation_executor_primary_path():
    executor = MutationExecutor()
    seed_ir = "line1\nline2\n  %add = add i32 %a, %b\nline4"
    
    plan = MutationPlan(
        description="desc",
        line_number=3,
        original_line="  %add = add i32 %a, %b",
        mutated_line="  %add = sub i32 %a, %b"
    )
    
    result = executor.apply(seed_ir, plan)
    assert result is not None
    assert "sub i32 %a, %b" in result
    assert "add i32 %a, %b" not in result

def test_mutation_executor_fallback_path():
    executor = MutationExecutor()
    seed_ir = "line1\nline2\n  %add = add i32 %a, %b\nline4"
    
    # Wrong line number but correct string
    plan = MutationPlan(
        description="desc",
        line_number=99,
        original_line="  %add = add i32 %a, %b",
        mutated_line="  %add = sub i32 %a, %b"
    )
    
    result = executor.apply(seed_ir, plan)
    assert result is not None
    assert "sub i32 %a, %b" in result

def test_mutation_executor_not_found():
    executor = MutationExecutor()
    seed_ir = "line1\nline2\nline3\nline4"
    
    plan = MutationPlan(
        description="desc",
        line_number=99,
        original_line="missing line",
        mutated_line="new line"
    )
    
    result = executor.apply(seed_ir, plan)
    assert result is None

def test_mutation_executor_deletion():
    executor = MutationExecutor()
    seed_ir = "line1\nline2\n  %add = add i32 %a, %b\nline4"
    
    plan = MutationPlan(
        description="desc",
        line_number=3,
        original_line="  %add = add i32 %a, %b",
        mutated_line=""
    )
    
    result = executor.apply(seed_ir, plan)
    assert result is not None
    lines = result.splitlines()
    assert len(lines) == 3
    assert "line4" in lines[2]

# ── Phase 10: hash / dedup tests ──────────────────────────────────────────

def test_compute_hash_is_deterministic():
    """Same IR text must always produce the same SHA-256 hex digest."""
    ir = "define i32 @foo() { ret i32 42 }\n"
    h1 = MutationExecutor.compute_hash(ir)
    h2 = MutationExecutor.compute_hash(ir)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex = 64 chars

def test_compute_hash_differs_for_different_ir():
    """Different IR must produce different hashes."""
    h1 = MutationExecutor.compute_hash("define i32 @foo() { ret i32 0 }\n")
    h2 = MutationExecutor.compute_hash("define i32 @foo() { ret i32 1 }\n")
    assert h1 != h2

def test_unique_mutants_counted_in_metrics(tmp_path):
    """Phase 10: unique_mutants counts distinct non-null hashes in JSONL."""
    import json
    from evaluate.metrics import MetricsEngine
    jsonl_path = tmp_path / "summary.jsonl"
    entries = [
        {"iteration": 1, "valid_mutant": True, "verdict": "DIVERGENT", "mutant_hash": "aaa"},
        {"iteration": 2, "valid_mutant": True, "verdict": "DIVERGENT", "mutant_hash": "bbb"},
        {"iteration": 3, "valid_mutant": True, "verdict": "DIVERGENT", "mutant_hash": "aaa"},  # duplicate
        {"iteration": 4, "valid_mutant": False, "verdict": "SKIPPED", "mutant_hash": None},
        {"iteration": 5, "valid_mutant": False, "verdict": "SKIPPED"},  # no hash key
    ]
    with open(jsonl_path, "w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")
    metrics = MetricsEngine().compute(str(jsonl_path))
    assert metrics.unique_mutants == 2  # "aaa" and "bbb"

