import json
from collections import namedtuple
from typing import List, Dict

PipelineMetrics = namedtuple("PipelineMetrics", [
    "total", "valid_mutants", "crashes", "post_opt_invalid",
    "divergent", "identical", "inconclusive", "parse_failures",
    "valid_mutant_rate", "crash_rate", "invalid_after_opt_rate",
    "bug_candidate_rate", "divergence_rate", "discard_rate",
    "total_time_seconds", "avg_time_per_iteration",
    "unique_mutants",
    "semantic_bugs", "exec_matches",
])

class MetricsEngine:
    def compute(self, jsonl_path: str) -> PipelineMetrics:
        entries = []
        try:
            with open(jsonl_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        entries.append(json.loads(line))
        except FileNotFoundError:
            return self._empty_metrics()

        if not entries:
            return self._empty_metrics()

        total = len(entries)
        valid_mutants = sum(1 for e in entries if e.get("valid_mutant"))
        crashes = sum(1 for e in entries if e.get("verdict") == "CRASH")
        invalid = sum(1 for e in entries if e.get("verdict") == "INVALID")
        divergent = sum(1 for e in entries if e.get("verdict") == "DIVERGENT")
        identical = sum(1 for e in entries if e.get("verdict") == "IDENTICAL")
        inconclusive = sum(1 for e in entries if e.get("verdict") == "INCONCLUSIVE")
        parse_failures = sum(1 for e in entries if e.get("verdict") == "SKIPPED" and not e.get("valid_mutant"))
        
        # Execution Oracle additions
        semantic_bugs = sum(1 for e in entries if e.get("verdict") == "SEMANTIC_BUG")
        exec_matches = sum(1 for e in entries if e.get("verdict") == "EXEC_MATCH")

        # Timing aggregation — field is optional; treat missing as 0
        times = [e.get("iteration_time_seconds", 0.0) for e in entries]
        total_time = sum(times)
        avg_time = total_time / total if total > 0 else 0.0

        # Uniqueness: count distinct non-null hashes
        unique_mutants = len({e["mutant_hash"] for e in entries if e.get("mutant_hash")})

        return PipelineMetrics(
            total=total,
            valid_mutants=valid_mutants,
            crashes=crashes,
            post_opt_invalid=invalid,
            divergent=divergent,
            identical=identical,
            inconclusive=inconclusive,
            parse_failures=parse_failures,

            valid_mutant_rate=valid_mutants / total if total > 0 else 0.0,
            crash_rate=crashes / valid_mutants if valid_mutants > 0 else 0.0,
            invalid_after_opt_rate=invalid / valid_mutants if valid_mutants > 0 else 0.0,
            bug_candidate_rate=(crashes + invalid) / valid_mutants if valid_mutants > 0 else 0.0,
            divergence_rate=divergent / valid_mutants if valid_mutants > 0 else 0.0,
            discard_rate=(total - valid_mutants) / total if total > 0 else 0.0,

            total_time_seconds=round(total_time, 3),
            avg_time_per_iteration=round(avg_time, 3),
            unique_mutants=unique_mutants,
            semantic_bugs=semantic_bugs,
            exec_matches=exec_matches,
        )

    def _empty_metrics(self) -> PipelineMetrics:
        return PipelineMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0, 0, 0)
