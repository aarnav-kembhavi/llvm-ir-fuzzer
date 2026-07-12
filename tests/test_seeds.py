import os
import pytest
from src.seed_loader import SeedLoader
from src.seed_selector import SeedSelector

@pytest.fixture
def mock_seeds_dir(tmp_path):
    # Create a temporary directory with mock .ll files
    seed_dir = tmp_path / "seeds"
    seed_dir.mkdir()
    
    # Create 15 files
    for i in range(1, 16):
        file_path = seed_dir / f"{i:02d}_test.ll"
        content = f"; Pattern: test_{i}\ndefine i32 @test_{i}() {{\n  ret i32 {i}\n}}\n"
        file_path.write_text(content, encoding="utf-8")
        
    # Create one non-LL file to ensure it's ignored
    (seed_dir / "ignore.txt").write_text("ignore me")
    
    return str(seed_dir)

def test_seed_loader(mock_seeds_dir):
    loader = SeedLoader(mock_seeds_dir)
    seeds = loader.load_all()
    
    assert len(seeds) == 15
    
    # Check that Seed objects are correctly formed
    assert seeds[0].pattern_type == "test_1"
    assert seeds[0].ir_text.startswith("; Pattern: test_1")
    assert seeds[0].path.endswith("01_test.ll")

def test_seed_loader_empty_dir(tmp_path):
    loader = SeedLoader(str(tmp_path))
    with pytest.raises(ValueError, match="No .ll files found"):
        loader.load_all()

def test_seed_loader_missing_dir():
    loader = SeedLoader("nonexistent_directory_xyz")
    with pytest.raises(FileNotFoundError):
        loader.load_all()

def test_seed_selector_round_robin(mock_seeds_dir):
    loader = SeedLoader(mock_seeds_dir)
    seeds = loader.load_all()
    
    selector = SeedSelector(seeds, strategy="round_robin")
    
    # Should cycle through exactly in order
    for i in range(15):
        seed = selector.next()
        assert seed.pattern_type == f"test_{i+1}"
        
    # Should wrap around
    seed = selector.next()
    assert seed.pattern_type == "test_1"

def test_seed_selector_random(mock_seeds_dir):
    loader = SeedLoader(mock_seeds_dir)
    seeds = loader.load_all()
    
    selector = SeedSelector(seeds, strategy="random")
    seed = selector.next()
    assert seed in seeds

def test_seed_selector_least_mutated(mock_seeds_dir):
    loader = SeedLoader(mock_seeds_dir)
    seeds = loader.load_all()
    
    selector = SeedSelector(seeds, strategy="least_mutated")
    
    # Pick 15 times, each seed should be picked exactly once since it picks the least mutated
    picked = set()
    for _ in range(15):
        seed = selector.next()
        picked.add(seed.path)
        
    assert len(picked) == 15

def test_real_seed_directory():
    """Phase 11: Verify the real seeds directory contains at least 15 valid seeds."""
    loader = SeedLoader("seeds")
    seeds = loader.load_all()
    assert len(seeds) >= 15
