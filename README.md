# LLM-Guided LLVM IR Differential Testing Pipeline
[![CI](https://github.com/aarnav-kembhavi/llvm-ir-fuzzer/actions/workflows/ci.yml/badge.svg)](https://github.com/aarnav-kembhavi/llvm-ir-fuzzer/actions/workflows/ci.yml)

## 1. Project Title

LLM-Guided LLVM IR Differential Testing with Execution-Based Semantic Oracle

## 2. Overview

This project is an automated **LLVM Intermediate Representation (IR) differential testing pipeline**. It is designed to automatically generate test cases for the LLVM compiler framework and evaluate how different compiler optimization levels behave. 

Instead of generating entirely random code, it uses a **Large Language Model (LLM)** to intelligently mutate a set of existing, perfectly valid seed IR files. The pipeline then takes these mutated files, validates them using LLVM's built-in tools (`llvm-as`), and compiles them using different optimization flags (specifically, unoptimized `-O0` and highly optimized `-O3`). 

By comparing the outputs of the compiler across these two optimization levels, the system can detect discrepancies. The system meticulously logs all metrics, outputs, and findings into organized artifacts. Recently, an **optional execution-based oracle** was added. This means the system can not only look at the text differences in the compiler's output but can actually execute the compiled programs to see if the optimizer accidentally broke the program's observable behavior.

## 3. Why this project exists

Testing compilers is notoriously difficult. A compiler bug, also known as a miscompilation, occurs when a compiler takes correct source code and accidentally generates incorrect machine code. These bugs are silent and highly dangerous.

* **Random fuzzing produces garbage:** Traditional fuzzers often generate random characters or naive string substitutions. When dealing with LLVM IR, which has strict syntax and Static Single Assignment (SSA) rules, random fuzzing results in massive amounts of invalid code that the compiler immediately rejects.
* **LLMs can help generate better mutations:** Large Language Models understand context. By asking an LLM to perform localized, single-line mutations on already valid code, we can guarantee a near 100% valid mutation rate, ensuring we are actually testing the optimizer and not just the syntax checker.
* **Structural diff alone is not enough:** Comparing the text output of `-O0` and `-O3` will almost always show a difference, because `-O3`'s job is to change and optimize the code. This creates a high false-positive rate.
* **Execution oracle helps detect semantic bugs:** To solve the false-positive problem, the execution oracle compiles and runs the programs. If `-O3` optimizes the code but changes the actual printed output or exit code of the program, we know we have found a genuine semantic bug.

## 4. System architecture

The pipeline follows a strict, step-by-step automated workflow:

**Seed Corpus → Selector → Prompt Builder → LLM → Mutation Planner → Mutation Executor → IR Validator → Diff Tester → Oracle → Logger → Metrics → Report**

1. **Seed Corpus & Selector:** A valid LLVM IR seed is selected from the corpus.
2. **LLM Mutation:** The seed is sent to the LLM alongside a prompt asking for a targeted, single-line mutation.
3. **Validator:** The mutated IR is verified for syntax errors using `llvm-as`.
4. **Diff Tester:** The valid mutant is passed through the `opt` tool using both `-O0` and `-O3` passes.
5. **Oracle:** Evaluates the compiler outputs.
   * **Structural Oracle (Mode A):** Hashes the textual IR outputs of `-O0` and `-O3` to see if they are identical or divergent. 
   * **Execution Oracle (Mode B):** If enabled, and if the IR contains a `main()` function, the oracle uses `clang` to compile both versions to executables. It runs them and compares their standard output and exit codes. If a seed is not executable, the system safely falls back to Mode A.
6. **Logger & Metrics:** Every step, including timing, hashes, and outputs, is saved to disk and aggregated into a summary report.

## 5. Features

* **Seed corpus:** A handcrafted collection of diverse LLVM IR patterns (loops, vectors, exceptions).
* **LLM-guided mutation:** Context-aware mutations that maintain strict SSA form.
* **Random baseline:** A naive regex-based mutator included to serve as a scientific control group.
* **SHA-256 deduplication:** Prevents redundant processing by hashing mutants and skipping duplicates.
* **Validator:** Fast-fails invalid IR to save compute time.
* **Differential testing:** Direct comparison of LLVM's `opt` passes.
* **Four-verdict structural oracle:** Classifies bugs into CRASH, INVALID, DIVERGENT, and IDENTICAL.
* **Execution oracle:** Deep semantic validation by running compiled machine code.
* **Logging and metrics:** Exhaustive JSONL artifacts and timing profiles.
* **Report generation:** Clean terminal tables and JSON exports.
* **CI support:** GitHub Actions workflow utilizing a mock LLM backend for rapid testing.

## 6. Project structure

* `seeds/`: The directory containing the valid `.ll` input files.
* `src/`: Core Python modules (orchestrator, LLM client, diff tester, oracle, etc.).
* `baselines/`: Contains the random mutator logic used for baseline comparisons.
* `evaluate/`: Contains the metrics engine and terminal report generators.
* `tests/`: Extensive `pytest` unit and integration tests.
* `artifacts/`: The output directory where all logs, metrics, and JSON reports are saved per run.
* `config.yaml`: The central configuration file for LLVM tool paths and pipeline settings.
* `main.py`: The entry point CLI script to run the pipeline.

## 7. Setup instructions

Follow these steps to set up the project from scratch on your local machine:

1. **Create a virtual environment:**
   ```bash
   python -m venv venv
   ```
2. **Activate the virtual environment:**
   * On Windows: `venv\Scripts\activate`
   * On Linux/Mac: `source venv/bin/activate`
3. **Install requirements:**
   ```bash
   pip install -r requirements.txt
   ```
4. **Install LLVM:**
   You must have the LLVM toolchain installed on your system. Specifically, you need `llvm-as`, `opt`, and `clang`. 
   * On Windows: Download the pre-built binaries from the LLVM release page and add them to your system PATH.
   * On Ubuntu: `sudo apt install llvm clang`
5. **Verify LLVM installation:**
   Run the following commands in your terminal to ensure they are accessible:
   ```bash
   llvm-as --version
   opt --version
   clang --version
   ```
6. **Set Environment Variables:**
   Copy the `.env.template` file to a new file named `.env`:
   ```bash
   cp .env.template .env
   ```
   Open the `.env` file and insert your API keys. The system supports `GEMINI_API_KEY`, `OPENAI_API_KEY`, and `GROQ_API_KEY`. The default configuration uses Gemini.

## 8. How to run

The pipeline is executed via `main.py`. Here are the most common commands:

* **Normal structural run (10 iterations):**
  ```bash
  python main.py --iterations 10
  ```
* **Run with the random baseline comparison:**
  ```bash
  python main.py --iterations 10 --baseline
  ```
* **Run with baseline and print a terminal report:**
  ```bash
  python main.py --iterations 10 --baseline --report
  ```
* **Run with the Execution Oracle enabled (Mode B):**
  ```bash
  python main.py --iterations 10 --execution --baseline --report
  ```
* **Run the test suite:**
  ```bash
  pytest -v
  ```

## 9. What output to expect

When you run the pipeline, you will see real-time progress in your terminal. Upon completion, a new timestamped directory is created inside the `artifacts/` folder (e.g., `artifacts/run_20260505_120000/`).

Inside this run directory, you will find:
* `iter_001/`, `iter_002/`, etc.: Folders for every single mutation attempt.
  * `seed.ll`: The original IR used for that iteration.
  * `mutant.ll`: The newly generated IR from the LLM.
  * `mutation_plan.json`: The specific line substitution proposed by the LLM.
  * `validation.log`: The output from `llvm-as`.
  * `oracle_result.json`: The raw return codes and diffs from `opt`.
* `run_summary.jsonl`: A master log file containing a single JSON object for every iteration, used for fast metric calculation.
* `summary_report.json`: (If `--report` is used) A clean, aggregated JSON file containing all final percentages, counts, and timing data.

## 10. Understanding the results

The Oracle assigns a specific verdict to every valid mutant it processes:

* **CRASH:** The compiler (`opt`) threw a fatal error or crashed with a non-zero exit code while processing the IR. This is a **bug candidate**.
* **INVALID:** The `-O3` pass succeeded, but the resulting IR was structurally invalid when passed back through `llvm-as`. This indicates the optimizer corrupted the code. This is a **bug candidate**.
* **DIVERGENT:** The textual IR output of `-O0` is different from `-O3`. This is entirely normal and **usually informational**, as optimizers are supposed to change the code.
* **IDENTICAL:** The `-O0` and `-O3` text outputs are exactly the same.
* **EXEC_MATCH:** (Execution Oracle Only) Both the `-O0` and `-O3` compiled binaries were executed, and their stdout/exit codes matched perfectly. The optimization was safe.
* **SEMANTIC_BUG:** (Execution Oracle Only) Both binaries executed, but their outputs differed. This means the optimizer changed the observable behavior of the program. This is a **critical bug candidate**.

## 11. Evaluation summary

If you use the `--report` flag, a summary table is printed displaying:

* **Valid mutant rate:** The percentage of LLM-generated IR that passed `llvm-as` syntax checking.
* **Unique mutants:** The number of structurally distinct mutants generated (via SHA-256 deduplication).
* **Discard rate:** The percentage of iterations thrown away due to syntax errors.
* **Total time / Avg time:** Performance profiling metrics showing pipeline throughput.
* **Bug candidate rate:** The percentage of valid mutants that triggered a CRASH or INVALID verdict.
* **Bug Candidates (SEMANTIC):** The total count of behavioral miscompilations found (only tracks if `--execution` is used).

## 12. Limitations

* **Not all seeds are executable:** The Execution Oracle strictly requires a `main()` function to compile and run. If you feed it a library function snippet, the oracle will gracefully skip execution and fall back to structural checks.
* **Proof-of-concept scale:** The pipeline is a research tool. To find zero-day compiler bugs, you must run it for thousands or millions of iterations. Small runs (e.g., 20 iterations) will likely yield 0 bugs, which is expected for mature compilers like LLVM.
* **Semantic validation is optional:** It adds significant time overhead due to subprocess execution and requires `clang` to be installed.

## 13. Current status

* ✅ Pipeline is fully implemented and automated.
* ✅ Comprehensive unit and integration tests exist.
* ✅ GitHub Actions CI is configured and passing.
* ✅ Execution Oracle (Mode B) is successfully included and handles fallbacks safely.
* The project is stable, complete, and ready for use and experimentation.

## 14. Future work

* Expanding the seed corpus with more executable C-to-IR examples.
* Integrating formal verification tools (like Alive2) for stronger semantic oracles when execution isn't possible.
* Implementing coverage-guided mutation (feeding LLVM source coverage back to the LLM).
* Running distributed, large-scale bug-hunting experiments.

## 15. Troubleshooting

* **`llvm-as`, `opt`, or `clang` not found:** Ensure you have installed the LLVM toolchain and added its `bin` directory to your system's PATH variable.
* **Venv activation issues:** On Windows, you may need to run `Set-ExecutionPolicy Unrestricted -Scope CurrentUser` in PowerShell to allow script execution.
* **Missing API key errors:** Double-check that your `.env` file exists in the root directory and contains a valid key (e.g., `GEMINI_API_KEY=your_key_here`).
* **High invalid IR output:** If the LLM generates entirely invalid code, ensure you are using a capable model (like Gemini 1.5 Pro/Flash or GPT-4). Weaker models struggle with SSA constraints.
* **No artifacts created:** Ensure the script has write permissions to the directory where you cloned the project.
* **Execution oracle skipped (No main):** This is expected behavior if the seed you are mutating (like `seeds/01_arithmetic.ll`) does not contain a `define i32 @main()` function. The system will fall back to Mode A.

## 16. License / Academic Note

This project was developed as an academic and compiler design lab initiative. It serves as a proof-of-concept for integrating Large Language Models into traditional compiler fuzzing and differential testing workflows.
