# Changelog

All notable changes to this project will be documented in this file.

## [1.0.0] - Post-MVP Hardening
### Added
- Fully functional LLM mutation pipeline (Groq/Gemini/OpenAI support).
- Validation and diff-testing via `llvm-as` and `opt`.
- 4-class Oracle (IDENTICAL, DIVERGENT, INVALID, CRASH).
- Comprehensive JSONL logging and HTML/Terminal report generation.
- Random baseline comparison tool.
- SHA-256 mutation deduplication (Phase 10).
- Time profiling and metrics gathering (Phase 9).
- 15 LLVM IR seed files representing various optimizable patterns and edge cases.
- GitHub Actions CI Pipeline with a mock LLM testing mode.
