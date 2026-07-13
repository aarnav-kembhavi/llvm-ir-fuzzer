# The Plain-English Guide to This Project

*Read this if the README feels like it was written for compiler engineers. No prior knowledge assumed.*

---

## 1. The 30-second version

This project **hunts for bugs in LLVM** — one of the most important compilers in the world (it's inside Clang, Rust, Swift, and more).

It does this by:
1. Taking small, correct code samples ("seeds")
2. Asking an AI to make **one small change** to each sample
3. Feeding the changed code to the compiler **twice** — once with optimizations off, once with them cranked to maximum
4. Checking whether the optimizer **broke the program's behavior**

If optimized and unoptimized versions of the *same program* behave differently, the compiler has a bug. That's the whole idea.

---

## 2. Okay, but why? (the actual point of all this)

### Compilers can silently lie to you

A compiler translates your code into machine instructions. When you build with optimizations (`-O3`), the compiler aggressively rewrites your code to make it faster — and *usually* it preserves exactly what your program does.

But compilers are written by humans. Sometimes an optimization is subtly wrong, and the compiler produces a program that does **something different from what you wrote**. This is called a **miscompilation**, and it's one of the scariest classes of bug in computing:

- Your source code is *correct*. Reviewing it finds nothing.
- Your tests might pass in debug builds and fail in release builds — or worse, fail only on customers' machines.
- Nobody suspects the compiler, because "the compiler is never wrong"... except when it is.

Real miscompilations have caused security vulnerabilities and shipped broken software. Finding them **before** they hurt someone is genuinely valuable work — LLVM has a bug tracker full of exactly these reports.

### Why testing compilers is hard

You can't just write unit tests for "every program anyone might compile." The input space is infinite. So researchers use **fuzzing**: generate lots of random-ish programs and see if the compiler chokes.

The problem: truly random text is garbage. LLVM's input language has strict rules, so random mutations produce 99% invalid code that the compiler rejects instantly. You end up testing the *syntax checker*, not the *optimizer* — the part where the dangerous bugs live.

### Why the AI is here

That's this project's trick: instead of random mutations, an **LLM** (a language model) makes the changes. The AI understands the code's structure, so it makes small edits that are *still valid programs* — like changing a multiplication to a modulo, or flipping a comparison. Valid mutants get past the front door and actually exercise the optimizer.

Your first run proved the concept: the LLM's mutants were valid 66% of the time. A random mutator (the built-in `--baseline`) typically manages far less — that comparison is the "science" part of the project.

---

## 3. What is LLVM IR? (the language of the seeds)

Compilers don't translate your code to machine instructions in one leap. They first convert it to an **Intermediate Representation (IR)** — a simple, universal assembly-like language that all optimizations operate on.

This is what it looks like:

```llvm
define i32 @add_five(i32 %x) {
entry:
  %result = add i32 %x, 5
  ret i32 %result
}
```

Reading guide:
- `define i32 @add_five(i32 %x)` — "a function named `add_five` that takes a 32-bit integer and returns one"
- `%result = add i32 %x, 5` — "add 5 to `%x`, call the answer `%result`"
- `ret i32 %result` — "return it"

Things starting with `%` are values, things starting with `@` are function/global names, `i32` means "32-bit integer." That's 80% of what you need to read most seeds.

This project tests LLVM **at the IR level** because that's where the optimizer lives. `opt` (the tool being tested) takes IR in, optimizes it, and spits IR out.

---

## 4. How one iteration works, step by step

Every "iteration" you see in the dashboard is this exact loop:

```
pick a seed → LLM mutates one line → is it still valid IR?
   ├── no  → discard, log it, next iteration        (verdict: SKIPPED)
   └── yes → compile it with -O0 AND with -O3
              └── compare the two results            (the "oracle")
```

The **oracle** is just the judge that decides what the comparison means:

| Verdict | Meaning | Should you care? |
|---|---|---|
| `DIVERGENT` | -O0 and -O3 produced *textually different* IR | **No — this is normal.** The optimizer's whole job is to change code. |
| `IDENTICAL` | Outputs were byte-identical | No. Nothing to optimize. |
| `SKIPPED` | The mutant was invalid, never tested | No. Just wasted ammo. |
| `CRASH` | The compiler itself crashed on valid input | **YES — bug candidate.** Compilers should never crash. |
| `INVALID` | The optimizer emitted *corrupted* IR | **YES — bug candidate.** The optimizer broke the code's structure. |
| `EXEC_MATCH` | (Mode B) both compiled binaries ran and behaved identically | No — that's the optimizer doing its job *correctly*. |
| `SEMANTIC_BUG` | (Mode B) the binaries **behaved differently** | **JACKPOT.** This is a real miscompilation — the holy grail of this whole project. |

**Mode B** (the `--execution` / "Execution oracle" checkbox) is the deeper test: instead of just comparing compiler *output text*, it compiles both versions into actual runnable programs, runs them, and compares what they print and their exit codes. It only works on seeds that have a `main()` function — that's why some seeds show a green `main()` chip in the dashboard.

---

## 4½. A worked example: divergence vs. semantic bug

Take this C function:

```c
int sum_to_n(int n) {           // adds 1+2+3+...+n
    int total = 0;
    for (int i = 1; i <= n; i++) total += i;
    return total;
}
```

**What -O0 does:** keeps your loop exactly as written — load, add, store, repeat.

**What -O3 does:** *deletes the loop entirely* and replaces it with the closed-form
math formula (Gauss's `n(n+1)/2` trick). The output IR shares almost nothing with
the input.

The two outputs are textually completely different → **DIVERGENT**. This is the
optimizer *succeeding*, not failing — which is exactly why `DIVERGENT` is
informational, and why text comparison alone can't find real bugs: a brilliant
rewrite and a broken rewrite both just look "different."

**Enter the execution oracle.** Add a `main()`:

```c
int main() { return sum_to_n(10); }
```

Now the pipeline can compile both versions into real programs and *run* them:

```
-O0 binary exits with: 55    ← the honest loop
-O3 binary exits with: 55    ← the formula rewrite
```

Same behavior → `EXEC_MATCH` → the radical rewrite was *correct*. But if LLVM's
loop-to-formula optimization ever had an off-by-one bug, you'd see:

```
-O0 binary exits with: 55    ← what your code actually computes
-O3 binary exits with: 45    ← what the optimizer broke it into
```

→ **`SEMANTIC_BUG`** — a real miscompilation, caught red-handed. That's the entire
point of the project in two numbers.

> **Divergent** = the translation *looks* different (expected).
> **Semantic bug** = the translation *means* something different (catastrophe).
> A `main()` is what lets the pipeline tell them apart.

---

## 5. How to actually use it (a sane workflow)

Everything below can be done from the dashboard (`python ui/app.py` → http://127.0.0.1:5173).

### First session
1. **Seed Corpus tab** — skim the 15 seeds so you know what's being mutated. They're each ~10–30 lines showcasing one pattern (loops, vectors, atomics...).
2. **New Run tab** — start with `10 iterations`, no checkboxes. Watch the live log. This takes seconds.
3. **Runs tab** — click your run. You'll see mostly `DIVERGENT` and a few `SKIPPED`. That's a healthy, boring result.
4. **Click an iteration row** — this is the best view in the project: the original vs. mutated code side by side, with the changed line highlighted, plus the AI's stated intent ("Replace the multiplication with a modulo to..."). This shows you *exactly* what the AI is doing.

### When you want real results
- Enable **Random baseline** — the run does everything twice (LLM vs. dumb random mutator) and the run page shows the comparison chart. This demonstrates *why* the LLM approach matters.
- Enable **Execution oracle** — slower, but it's the only mode that can find `SEMANTIC_BUG`, the truly damning verdict.
- **Crank the iterations.** This is a numbers game. LLVM is a mature, heavily-tested compiler; 10 iterations finding nothing is *expected*. Real compiler-fuzzing campaigns run thousands to millions of iterations. Treat 0 bug candidates as the normal outcome and any `CRASH`/`INVALID`/`SEMANTIC_BUG` as a genuinely exciting event worth investigating.

### If you ever find a bug candidate
The iteration's folder in `artifacts/` contains everything needed to report it: the exact mutant IR (`mutant.ll`), the compiler's output, and the verdict. A minimized version of that `.ll` file plus the `opt` command line is essentially what an LLVM bug report looks like.

---

## 5½. Real results — a 300-run, explained

These are actual measured numbers from running the pipeline **300 times with the LLM mutator and 300 times with the random baseline**, on the same 16 seeds, then differentially testing every result. Nothing here is estimated. *(Runs `run_20260713_210524` (LLM) and `run_20260713_212634` (baseline); a visual version of all these charts lives in the benchmark report.)*

If you present this project, this is the section to build your talk around. Each result below is one slide.

### Result 1 — The headline: the LLM is 3.2× more efficient

| | LLM-guided | Random baseline |
|---|---|---|
| Valid mutant rate | **37.0%** (111/300) | **11.7%** (35/300) |
| Discard rate (wasted work) | 63.0% | 88.3% |

**What "valid mutant rate" means:** the share of mutations that were actually valid LLVM IR — code the compiler accepts and will try to optimize. The rest are thrown away instantly because they broke the syntax or SSA rules.

**Why it's the whole point:** a mutant that gets rejected at the door never reaches the optimizer, so it can never find an optimizer bug — it just tests the syntax checker. The LLM produces **3.2× more testable mutants** than random mutation (37% ÷ 11.7% ≈ 3.2). That ratio *is* the thesis of the project: an AI that understands the code keeps far more of its edits inside "valid program" space. The random mutator wastes ~88% of its attempts; the LLM wastes ~63%.

### Result 2 — Where the 300 LLM iterations went (verdict distribution)

Of the LLM's 300 iterations:
- **111 → DIVERGENT** — valid, reached the optimizer, and `-O0` vs `-O3` produced different output. *This is normal and expected* — the optimizer's job is to change code.
- **189 → SKIPPED** — discarded before testing because the mutant was invalid or no mutation was produced.
- **0 → CRASH / INVALID / SEMANTIC_BUG** — no bug candidates.

**Read this as:** every valid mutant landed on `DIVERGENT`, and none broke the compiler. Which brings us to the honest caveat...

> **Finding zero bugs is the correct, expected result.** LLVM is one of the most heavily-tested pieces of software on earth. A 300-iteration run is a *proof that the machine works*, not a bug-hunting campaign — those run for millions of iterations. Any professor who knows compilers will expect zero bugs here; claiming otherwise would be the red flag.

### Result 3 — The competence map: where LLM mutation is easy vs. hard

This is the most *interesting* slide. The LLM's valid rate varies a lot depending on which IR feature it's editing:

| Easiest for the LLM | Rate | | Hardest for the LLM | Rate |
|---|---|---|---|---|
| Arithmetic | 63% | | Struct | 16% |
| Integer overflow | 63% | | Vector | 21% |
| Branch | 53% | | Switch | 21% |
| Custom seed | 50% | | Memory | 21% |
| Loop | 47% | | Exception-like | 6% |

**What this tells you:** simple, local patterns (integer math, overflow flags, straight-line branches) are easy for the LLM to mutate validly. The hard ones are exactly the features with the most rigid structure — `struct` type layouts, vector width/type matching, `switch` case tables, and exception-handling scaffolding. Edit one line there and you usually violate a rule somewhere else.

**The honest nuance worth saying out loud:** on three of the gnarliest patterns — **Switch (21% vs 26%), Struct (16% vs 22%), and Exception-like (6% vs 11%)** — the *random* baseline actually did slightly better than the LLM. Why? On heavily-constrained code, the LLM often tries an "intelligent" edit that trips a subtle rule, whereas random deletion sometimes just removes a whole line cleanly and stays valid. Presenting this makes your analysis more credible, and it points straight at future work: better prompting for structured IR.

### Result 4 — Convergence: is 37% a real number or a fluke?

If you plot the **running valid rate** after each iteration, it swings wildly at the start (one lucky mutant early on can read as "50%"), then settles down and hovers in the **37–42%** band for the back half of the run, ending at 37%.

**Why this slide matters:** it answers the first skeptical question — *"you ran it once, is that number even repeatable?"* The curve flattening out is visual proof that 300 iterations is enough for the percentage to stabilize. It's no longer a small-sample coincidence; it's a stable property of the LLM+seed combination.

### Result 5 — Failure-mode breakdown: where the mutants die

Of the LLM's 300 attempts, classified by what happened:

| Outcome | Count | What it means |
|---|---|---|
| **Valid mutant** | 111 | passed `llvm-as`, got tested |
| **Invalid IR** | 107 | the LLM's edit broke the syntax/SSA rules — `llvm-as` rejected it |
| **No-op / skipped** | 74 | the pipeline produced no usable mutation |
| **Bad plan (JSON)** | 8 | the LLM's reply wasn't parseable instructions |

**Read this as a diagnosis of the losses.** The biggest failure bucket isn't the AI misbehaving (only 8 unparseable replies out of 300) — it's that **107 syntactically-plausible edits still violated LLVM's strict rules.** That's the real difficulty of the problem: LLVM IR is unforgiving, and even a smart edit frequently breaks an invariant elsewhere. This is your "why this is hard" slide.

### Result 6 — Throughput & scale: the cost of intelligence

| | LLM-guided | Random baseline |
|---|---|---|
| Time per iteration | 4.2s (waiting on the AI API) | 0.016s (instant) |
| Total for 300 iterations | 21.1 min | 4.7s |

The LLM is **~260× slower per iteration** because every mutation is a network call to the language model. The random mutator is basically free. So the trade is: *the LLM is far slower but far more accurate; random is instant but mostly wasted effort.*

**Scaling it up:** a serious bug-hunting campaign of **1,000,000 iterations** would take ≈**49 days** running one at a time — but each iteration is independent, so running **50 in parallel** brings it down to **≈1 day**. This is the slide that frames the project honestly as a *proof-of-concept* that would need parallel compute to hunt real bugs.

### One more caveat: the execution oracle found nothing to run

Mode B (the execution oracle) logged **0 EXEC_MATCH** results this run. That's not a failure — it's because almost all 16 seeds are *library functions with no `main()`*, so there was nothing to compile-and-run, and the oracle correctly fell back to structural comparison every time. **This is the single clearest place the project can be improved:** add seeds with a `define i32 @main()` (see the next section) and the execution oracle — the only mode that can catch a real `SEMANTIC_BUG` — finally has something to chew on.

---

## 6. Why add your own seed?

The built-in 15 seeds are a starter pack, not a boundary. Every seed is a **neighborhood of programs being explored** — the mutations only ever wander one line away from a seed, so the pipeline can only find bugs *near the patterns the corpus contains*.

Adding your own seed means:

1. **You choose where to hunt.** Optimizer bugs cluster around specific features: overflow flags (`nsw`/`nuw`), pointer arithmetic (`getelementptr`), floating-point fast-math, vector shuffles, atomics. A seed built around a feature aims the entire pipeline at that feature's optimization passes.
2. **You can test code you actually care about.** Compile *your own C function* to IR (`clang -S -emit-llvm -O0 -o - mycode.c`), paste it in as a seed, and now the fuzzer is stress-testing the optimizer *on your code's patterns*. If there's a miscompilation lurking near code shaped like yours, this is how you'd bump into it.
3. **Executable seeds are more powerful.** Give your seed a `define i32 @main()` and the execution oracle can catch behavioral bugs in it — the diversity of *executable* seeds is currently the corpus's weakest spot (the README lists it as future work).
4. **More diversity = better fuzzing.** Fuzzing lives and dies on input diversity. Fifteen seeds cover fifteen neighborhoods; every seed you add is a new neighborhood the pipeline couldn't reach before.

The dashboard's **＋ Add custom seed** flow validates your IR with `llvm-as` before saving, so you can't accidentally poison the corpus — and every run after that automatically includes your seed in the rotation.

---

## 7. Mental model to leave with

> **The compiler makes you a promise: "optimized code behaves identically to unoptimized code."
> This project is a machine for catching it breaking that promise.**

- The **seeds** are the territory being searched.
- The **LLM** is a smart mutation engine that keeps the search inside "valid program" space.
- The **oracle** is the judge comparing -O0 vs -O3.
- `DIVERGENT` is noise, `CRASH`/`INVALID`/`SEMANTIC_BUG` is signal.
- Zero findings on a mature compiler is normal; the pipeline itself working end-to-end *is* the achievement — it's a proof-of-concept that LLM-guided mutation beats random mutation at compiler fuzzing (and the `--baseline` flag exists precisely to prove that on your own machine).

---

## 8. Cheat sheet

| I want to... | Do this |
|---|---|
| See the whole thing work once | New Run → 10 iterations → Start |
| Understand what the AI did | Runs → click a run → click an iteration |
| Prove the LLM beats random | New Run → check **Random baseline** → look at the comparison chart |
| Hunt for real behavioral bugs | New Run → check **Execution oracle**, use seeds with `main()`, lots of iterations |
| Aim the fuzzer at my own code | `clang -S -emit-llvm -O0 -o - mycode.c` → Seed Corpus → ＋ Add custom seed |
| Check results later / from scripts | Everything is in `artifacts/run_*/` as JSON |
| Run it without the UI | `python main.py --iterations 50 --baseline --report` |
| Run the test suite | `pytest -v` |
