from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from evaluate.metrics import PipelineMetrics

class ReportGenerator:
    def __init__(self):
        self.console = Console()

    def print_report(self, llm_metrics: PipelineMetrics, baseline_metrics: PipelineMetrics = None):
        self.console.print("\n")
        
        # Summary Overview
        self.console.print(Panel("[bold cyan]LLVM IR Differential Testing — Run Summary[/bold cyan]", expand=False))
        
        # Create Table
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Metric")
        table.add_column("LLM Approach")
        
        has_baseline = baseline_metrics and baseline_metrics.total > 0
        if has_baseline:
            table.add_column("Random Baseline")
            
        def add_row(name, attr, is_pct=False):
            val_llm = getattr(llm_metrics, attr)
            str_llm = f"{val_llm:.1%}" if is_pct else str(val_llm)
            
            if has_baseline:
                val_base = getattr(baseline_metrics, attr)
                str_base = f"{val_base:.1%}" if is_pct else str(val_base)
                table.add_row(name, str_llm, str_base)
            else:
                table.add_row(name, str_llm)

        add_row("Total Iterations", "total")
        add_row("Valid Mutants", "valid_mutants")
        add_row("Unique Mutants", "unique_mutants")
        table.add_section()
        
        add_row("Bug Candidates (CRASH)", "crashes")
        add_row("Bug Candidates (INVALID)", "post_opt_invalid")
        add_row("Bug Candidates (SEMANTIC)", "semantic_bugs")
        add_row("Divergences (Info)", "divergent")
        add_row("Exec Matches (Info)", "exec_matches")
        add_row("Identical", "identical")
        table.add_section()
        
        add_row("Valid Mutant Rate", "valid_mutant_rate", True)
        add_row("Bug Candidate Rate", "bug_candidate_rate", True)
        add_row("Divergence Rate", "divergence_rate", True)
        add_row("Discard Rate", "discard_rate", True)
        table.add_section()

        # Timing rows
        def add_timing_row(name, attr):
            val_llm = getattr(llm_metrics, attr)
            str_llm = f"{val_llm:.2f}s"
            if has_baseline:
                val_base = getattr(baseline_metrics, attr)
                str_base = f"{val_base:.2f}s"
                table.add_row(name, str_llm, str_base)
            else:
                table.add_row(name, str_llm)

        add_timing_row("Total Time", "total_time_seconds")
        add_timing_row("Avg Time / Iteration", "avg_time_per_iteration")
        
        self.console.print(table)
        self.console.print("\n")
        
        # High level outcome
        if llm_metrics.crashes > 0 or llm_metrics.post_opt_invalid > 0 or llm_metrics.semantic_bugs > 0:
            self.console.print("[bold red]BUG CANDIDATES DETECTED! Check artifacts/ for logs.[/bold red]")
        else:
            self.console.print("[bold green]No bug candidates found in this run.[/bold green]")
        self.console.print("\n")

    def save_report(self, path: str, llm_metrics: PipelineMetrics, baseline_metrics: PipelineMetrics = None):
        import json
        from datetime import datetime
        
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "llm_metrics": llm_metrics._asdict()
        }
        
        if baseline_metrics:
            report_data["baseline_metrics"] = baseline_metrics._asdict()
            
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)
