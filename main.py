import argparse
import sys
from dotenv import load_dotenv
from src.orchestrator import Orchestrator

def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="LLM-Guided LLVM IR Differential Testing Pipeline")
    parser.add_argument("--iterations", type=int, default=20, help="Number of iterations to run")
    parser.add_argument("--strategy", type=str, choices=["round_robin", "random", "least_mutated"], 
                        help="Seed selection strategy (overrides config)")
    parser.add_argument("--baseline", action="store_true", help="Run random baseline for comparison")
    parser.add_argument("--report", action="store_true", help="Print metrics report at the end")
    parser.add_argument("--execution", action="store_true", help="Enable execution-based differential testing (Mode B)")
    parser.add_argument("--config", type=str, default="config.yaml", help="Path to configuration file")
    
    args = parser.parse_args()
    
    try:
        orchestrator = Orchestrator(config_path=args.config, execution_mode=args.execution)
        
        if args.strategy:
            orchestrator.seed_selector.strategy = args.strategy
            
        orchestrator.run_pipeline(
            iterations=args.iterations,
            run_baseline=args.baseline,
            show_report=args.report
        )
    except Exception as e:
        print(f"Fatal error initializing pipeline: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
