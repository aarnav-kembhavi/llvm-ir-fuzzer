import pytest
import tempfile
import yaml
import os
from src.orchestrator import Orchestrator

@pytest.fixture
def test_env(tmp_path):
    # Setup seeds
    seed_dir = tmp_path / "seeds"
    seed_dir.mkdir()
    seed_file = seed_dir / "test.ll"
    seed_file.write_text("define i32 @main() { ret i32 0 }\n")
    
    # Setup config
    config_path = tmp_path / "config.yaml"
    config_data = {
        "pipeline": {
            "seed_dir": str(seed_dir),
            "artifact_dir": str(tmp_path / "artifacts"),
        },
        "llm": {"backend": "mock"},
        "llvm": {"llvm_as": "python", "opt": "python"} # using python as dummy executable
    }
    with open(config_path, "w") as f:
        yaml.dump(config_data, f)
        
    # Setup prompts
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir()
    prompt_file = prompt_dir / "mutation_prompt.txt"
    prompt_file.write_text("Prompt: {numbered_ir}")
    
    # We must mock os.path.join inside Orchestrator to point to tmp_path/prompts
    # but the easiest way is to just run in a CWD that has prompts/
    cwd = os.getcwd()
    os.chdir(str(tmp_path))
    
    yield str(config_path)
    
    os.chdir(cwd)

def test_orchestrator_initialization(test_env):
    orch = Orchestrator(config_path=test_env)
    assert orch.seed_loader is not None
    assert orch.client.__class__.__name__ == "MockClient"
    assert len(orch.seeds) == 1

def test_orchestrator_run_iteration_mock(test_env):
    orch = Orchestrator(config_path=test_env)
    # The actual execution of validation/diff will fail or be meaningless since we use 'python' as the executable
    # but the code shouldn't crash
    orch.run_iteration(1)
    
    # Verify logger created a directory
    assert os.path.exists(orch.logger.run_dir)
    assert os.path.exists(orch.logger.summary_file)
