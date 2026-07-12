"""
Web dashboard for the LLM-Guided LLVM IR Differential Testing Pipeline.

Run:  python ui/app.py   (from the project root)
Then open http://127.0.0.1:5173
"""
import json
import os
import re
import subprocess
import sys
import threading
from pathlib import Path

import yaml
from flask import Flask, jsonify, request, send_from_directory

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
SEEDS_DIR = PROJECT_ROOT / "seeds"
STATIC_DIR = Path(__file__).resolve().parent / "static"

sys.path.insert(0, str(PROJECT_ROOT))
from src.ir_validator import IRValidator  # noqa: E402  (reuses the pipeline's own validator)

RUN_ID_RE = re.compile(r"^run_\d{8}_\d{6}$")
SEED_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,60}$")
CUSTOM_MARKER = "; custom-seed (added via dashboard)"

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")

# ---------------------------------------------------------------- pipeline runner
_run_lock = threading.Lock()
_run_state = {
    "running": False,
    "lines": [],          # captured stdout lines
    "returncode": None,
    "args": None,
}


def _pump_output(proc):
    for raw in proc.stdout:
        line = raw.rstrip("\r\n")
        _run_state["lines"].append(line)
    proc.wait()
    _run_state["returncode"] = proc.returncode
    _run_state["running"] = False


@app.post("/api/pipeline/start")
def start_pipeline():
    with _run_lock:
        if _run_state["running"]:
            return jsonify({"error": "A pipeline run is already in progress."}), 409

        body = request.get_json(silent=True) or {}
        iterations = max(1, min(int(body.get("iterations", 10)), 500))
        cmd = [sys.executable, "-u", "main.py", "--iterations", str(iterations), "--report"]
        strategy = body.get("strategy")
        if strategy in ("round_robin", "random", "least_mutated"):
            cmd += ["--strategy", strategy]
        if body.get("baseline"):
            cmd.append("--baseline")
        if body.get("execution"):
            cmd.append("--execution")

        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        proc = subprocess.Popen(
            cmd, cwd=str(PROJECT_ROOT),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", env=env,
        )
        _run_state.update(running=True, lines=[], returncode=None, args=cmd[2:])
        threading.Thread(target=_pump_output, args=(proc,), daemon=True).start()
        return jsonify({"started": True, "command": " ".join(cmd[2:])})


@app.get("/api/pipeline/status")
def pipeline_status():
    offset = int(request.args.get("offset", 0))
    return jsonify({
        "running": _run_state["running"],
        "returncode": _run_state["returncode"],
        "args": _run_state["args"],
        "lines": _run_state["lines"][offset:],
        "total_lines": len(_run_state["lines"]),
    })


# ---------------------------------------------------------------- artifacts
def _read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _read_text(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return None


def _read_jsonl(path):
    rows = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    except OSError:
        pass
    return rows


def _run_dir(run_id):
    if not RUN_ID_RE.match(run_id):
        return None
    d = ARTIFACTS_DIR / run_id
    return d if d.is_dir() else None


@app.get("/api/runs")
def list_runs():
    runs = []
    if ARTIFACTS_DIR.is_dir():
        for d in sorted(ARTIFACTS_DIR.iterdir(), reverse=True):
            if not (d.is_dir() and RUN_ID_RE.match(d.name)):
                continue
            iters = _read_jsonl(d / "run_summary.jsonl")
            verdicts = {}
            bug_candidates = 0
            for it in iters:
                v = it.get("verdict", "SKIPPED")
                verdicts[v] = verdicts.get(v, 0) + 1
                if it.get("is_bug_candidate"):
                    bug_candidates += 1
            report = _read_json(d / "summary_report.json")
            runs.append({
                "id": d.name,
                "timestamp": d.name[4:],  # yyyymmdd_hhmmss
                "iterations": len(iters),
                "verdicts": verdicts,
                "bug_candidates": bug_candidates,
                "has_report": report is not None,
                "has_baseline": bool(report and report.get("baseline_metrics")),
            })
    return jsonify(runs)


@app.get("/api/runs/<run_id>")
def run_detail(run_id):
    d = _run_dir(run_id)
    if d is None:
        return jsonify({"error": "run not found"}), 404
    iters = _read_jsonl(d / "run_summary.jsonl")
    return jsonify({
        "id": run_id,
        "report": _read_json(d / "summary_report.json"),
        "iterations": iters,
    })


@app.get("/api/runs/<run_id>/iterations/<int:n>")
def iteration_detail(run_id, n):
    d = _run_dir(run_id)
    if d is None:
        return jsonify({"error": "run not found"}), 404
    it = d / f"iter_{n:03d}"
    if not it.is_dir():
        return jsonify({"error": "iteration not found"}), 404
    return jsonify({
        "run_id": run_id,
        "iteration": n,
        "seed": _read_text(it / "seed.ll"),
        "mutant": _read_text(it / "mutant.ll"),
        "plan": _read_json(it / "mutation_plan.json"),
        "oracle": _read_json(it / "oracle_result.json"),
        "validation": _read_text(it / "validation.log"),
        "prompt": _read_text(it / "prompt.txt"),
    })


@app.get("/api/seeds")
def list_seeds():
    seeds = []
    if SEEDS_DIR.is_dir():
        for p in sorted(SEEDS_DIR.glob("*.ll")):
            content = _read_text(p) or ""
            m = re.search(r";\s*Pattern:\s*(.+)", content)
            # fall back to the filename: "11_integer_overflow" -> "integer overflow"
            fallback = re.sub(r"^\d+_", "", p.stem).replace("_", " ")
            seeds.append({
                "name": p.name,
                "pattern": m.group(1).strip() if m else fallback,
                "lines": content.count("\n") + 1,
                "has_main": "@main(" in content,
                "custom": CUSTOM_MARKER in content,
                "content": content,
            })
    return jsonify(seeds)


def _validate_ir(content):
    validator = IRValidator(
        llvm_as_path=os.environ.get("LLVM_AS_PATH", "llvm-as"),
        timeout_seconds=30,
    )
    return validator.validate(content)


@app.post("/api/seeds/validate")
def validate_seed():
    body = request.get_json(silent=True) or {}
    result = _validate_ir(body.get("content", ""))
    return jsonify({"valid": result.valid, "error": result.error_message})


@app.post("/api/seeds")
def add_seed():
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip().removesuffix(".ll")
    content = (body.get("content") or "").replace("\r\n", "\n").strip()
    pattern = (body.get("pattern") or "custom").strip()

    if not SEED_NAME_RE.match(name):
        return jsonify({"error": "Invalid name — use letters, digits, - or _ (max 61 chars)."}), 400
    if not content:
        return jsonify({"error": "Seed content is empty."}), 400
    path = SEEDS_DIR / f"{name}.ll"
    if path.exists():
        return jsonify({"error": f"A seed named {name}.ll already exists."}), 409

    result = _validate_ir(content)
    if not result.valid:
        return jsonify({"error": "IR failed llvm-as validation.", "detail": result.error_message}), 422

    # SeedLoader reads the pattern from line 1, so it must stay first;
    # the custom marker (enables deletion) goes on line 2.
    if content.startswith("; Pattern:"):
        first, _, rest = content.partition("\n")
        text = f"{first}\n{CUSTOM_MARKER}\n{rest}"
    else:
        text = f"; Pattern: {pattern}\n{CUSTOM_MARKER}\n{content}"
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text + "\n")
    return jsonify({"saved": True, "name": path.name})


@app.delete("/api/seeds/<name>")
def delete_seed(name):
    name = name.removesuffix(".ll")
    if not SEED_NAME_RE.match(name):
        return jsonify({"error": "invalid name"}), 400
    path = SEEDS_DIR / f"{name}.ll"
    if not path.is_file():
        return jsonify({"error": "seed not found"}), 404
    if CUSTOM_MARKER not in (_read_text(path) or ""):
        return jsonify({"error": "Only custom seeds added via the dashboard can be deleted."}), 403
    path.unlink()
    return jsonify({"deleted": True})


@app.get("/api/config")
def get_config():
    cfg = {}
    try:
        with open(PROJECT_ROOT / "config.yaml", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    except OSError:
        pass
    # never expose API keys — only which backend is active
    backend = os.environ.get("LLM_BACKEND") or cfg.get("llm", {}).get("backend", "?")
    return jsonify({
        "backend": backend,
        "model": (cfg.get("llm", {}).get("models", {}) or {}).get(backend)
                 or cfg.get("llm", {}).get("model", "?"),
        "compare_levels": cfg.get("oracle", {}).get("compare_levels", ["O0", "O3"]),
        "seed_strategy": cfg.get("pipeline", {}).get("seed_strategy", "round_robin"),
    })


@app.get("/")
def index():
    return send_from_directory(str(STATIC_DIR), "index.html")


if __name__ == "__main__":
    # load .env so LLM_BACKEND is reflected in /api/config
    try:
        from dotenv import load_dotenv
        load_dotenv(PROJECT_ROOT / ".env")
    except ImportError:
        pass
    app.run(host="127.0.0.1", port=5173, debug=False)
