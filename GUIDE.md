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
