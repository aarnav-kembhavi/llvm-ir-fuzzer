import os
import time
import yaml
from rich.console import Console

from src.seed_loader import SeedLoader
from src.seed_selector import SeedSelector
from src.llm_client import create_client
from src.mutation_planner import MutationPlanner
from src.mutation_executor import MutationExecutor
from src.ir_validator import IRValidator
from src.diff_tester import DiffTester
from src.oracle import Oracle
from src.logger import Logger
from baselines.random_mutator import RandomMutator
from evaluate.metrics import MetricsEngine
from evaluate.report import ReportGenerator

class Orchestrator:
    def __init__(self, config_path="config.yaml", execution_mode=False):
        self.console = Console()
        self.config = self._load_config(config_path)
        
        # Initialize pipeline components
        pipeline_cfg = self.config.get("pipeline", {})
        llvm_cfg = self.config.get("llvm", {})
        llm_cfg = self.config.get("llm", {})
        oracle_cfg = self.config.get("oracle", {})
        
        # Directory paths
        self.seed_dir = pipeline_cfg.get("seed_dir", "seeds/")
        self.artifact_dir = pipeline_cfg.get("artifact_dir", "artifacts/")
        
        # Tools
        self.seed_loader = SeedLoader(self.seed_dir)
        try:
            self.seeds = self.seed_loader.load_all()
        except Exception as e:
            self.console.print(f"[bold red]Pipeline Error: {e}[/bold red]")
            # Pipeline exits here if no seeds
            raise e
            
        self.seed_selector = SeedSelector(
            self.seeds, 
            strategy=pipeline_cfg.get("seed_strategy", "round_robin")
        )
        
        # LLM Mutation tools
        prompt_path = os.path.join("prompts", "mutation_prompt.txt")
        self.client = create_client(llm_cfg)
        self.planner = MutationPlanner(self.client, prompt_path)
        self.executor = MutationExecutor()
        
        # Baseline
        self.random_mutator = RandomMutator()
        
        # LLVM / Oracle
        self.validator = IRValidator(
            llvm_as_path=llvm_cfg.get("llvm_as", "llvm-as"),
            timeout_seconds=llvm_cfg.get("timeout_seconds", 30)
        )
        self.diff_tester = DiffTester(
            opt_path=llvm_cfg.get("opt", "opt"),
            timeout_seconds=llvm_cfg.get("timeout_seconds", 30)
        )
        self.oracle = Oracle(
            self.validator, 
            execution_mode=execution_mode,
            compiler_path=oracle_cfg.get("compiler", "clang"),
            timeout_seconds=oracle_cfg.get("timeout_seconds", 5)
        )
        
        # Logging & Reporting
        self.logger = Logger(base_dir=self.artifact_dir)
        self.metrics_engine = MetricsEngine()
        self.report_generator = ReportGenerator()
        self.seen_mutant_hashes: set = set()

    def _load_config(self, path):
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def run_iteration(self, iteration: int, use_baseline: bool = False):
        self.console.print(f"\n[cyan]Starting Iteration {iteration}[/cyan]")
        iter_start = time.perf_counter()
        
        try:
            seed = self.seed_selector.next()
            self.console.print(f"Seed: {seed.path} (Pattern: {seed.pattern_type})")
            
            prompt_text = None
            plan = None
            mutant_ir = None
            

            if use_baseline:
                plan = self.random_mutator.generate_plan(seed.ir_text)
                if plan:
                    mutant_ir = self.executor.apply(seed.ir_text, plan)
            else:
                numbered_ir = self.planner._prepend_line_numbers(seed.ir_text)
                prompt_text = self.planner.prompt_template.replace("{numbered_ir}", numbered_ir)
                plan = self.planner.plan(seed.ir_text)
                if plan:
                    mutant_ir = self.executor.apply(seed.ir_text, plan)
                    
            if not plan or not mutant_ir:
                self.console.print("[yellow]Mutation failed or skipped.[/yellow]")
                elapsed = time.perf_counter() - iter_start
                self.logger.log_iteration(iteration, seed.path, seed.ir_text, prompt_text, plan, iteration_time_seconds=elapsed)
                return


            mutant_hash = self.executor.compute_hash(mutant_ir)
            if mutant_hash in self.seen_mutant_hashes:
                self.console.print("[yellow]Duplicate mutant skipped (seen before).[/yellow]")
                elapsed = time.perf_counter() - iter_start
                self.logger.log_iteration(iteration, seed.path, seed.ir_text, prompt_text, plan, iteration_time_seconds=elapsed)
                return
            self.seen_mutant_hashes.add(mutant_hash)
                
            self.console.print(f"Mutated line {plan.line_number}")
            

            validation = self.validator.validate(mutant_ir)
            if not validation.valid:
                self.console.print(f"[yellow]Invalid IR: {validation.error_message[:50]}...[/yellow]")
                elapsed = time.perf_counter() - iter_start
                self.logger.log_iteration(iteration, seed.path, seed.ir_text, prompt_text, plan, mutant_ir, validation, iteration_time_seconds=elapsed)
                return
                
            self.console.print("[green]IR is valid.[/green]")
            

            temp_mutant_path = f"temp_mutant_{iteration}.ll"
            with open(temp_mutant_path, "w", encoding="utf-8") as f:
                f.write(mutant_ir)
                
            try:
                diff_result = self.diff_tester.test(temp_mutant_path)
            finally:
                if os.path.exists(temp_mutant_path):
                    os.remove(temp_mutant_path)
                    
            oracle_result = self.oracle.classify(diff_result)
            
            if oracle_result.is_bug_candidate:
                self.console.print(f"[bold red]VERDICT: {oracle_result.verdict} - BUG CANDIDATE![/bold red]")
            else:
                self.console.print(f"Verdict: {oracle_result.verdict}")
                

            elapsed = time.perf_counter() - iter_start
            self.logger.log_iteration(iteration, seed.path, seed.ir_text, prompt_text, plan, mutant_ir, validation, oracle_result, iteration_time_seconds=elapsed, mutant_hash=mutant_hash)
            
        except Exception as e:
            self.console.print(f"[bold red]Exception during iteration {iteration}: {e}[/bold red]")
            elapsed = time.perf_counter() - iter_start
            # Log as skipped iteration if possible
            try:
                self.logger.log_iteration(iteration, "unknown", "", None, None, None, None, None, iteration_time_seconds=elapsed)
            except Exception:
                pass

    def run_pipeline(self, iterations: int, run_baseline: bool = False, show_report: bool = False):
        self.console.print(f"[bold magenta]Starting Pipeline ({iterations} iterations)[/bold magenta]")
        self.console.print(f"Logging to: {self.logger.run_dir}")
        
        # Run LLM or selected approach
        for i in range(1, iterations + 1):
            self.run_iteration(i, use_baseline=False)
            
        llm_metrics = self.metrics_engine.compute(self.logger.summary_file)
        baseline_metrics = None
        
        # Optional baseline run for comparison
        if run_baseline:
            self.console.print(f"\n[bold magenta]Starting Random Baseline Pipeline ({iterations} iterations)[/bold magenta]")
            # Create a separate logger for baseline to keep metrics separate
            baseline_logger = Logger(base_dir=self.artifact_dir)
            self.logger = baseline_logger
            
            for i in range(1, iterations + 1):
                self.run_iteration(i, use_baseline=True)
                
            baseline_metrics = self.metrics_engine.compute(baseline_logger.summary_file)
            
        if show_report:
            self.report_generator.print_report(llm_metrics, baseline_metrics)
            
            report_path = os.path.join(self.logger.run_dir, "summary_report.json")
            self.report_generator.save_report(report_path, llm_metrics, baseline_metrics)
            self.console.print(f"[green]Saved summary report to {report_path}[/green]")
