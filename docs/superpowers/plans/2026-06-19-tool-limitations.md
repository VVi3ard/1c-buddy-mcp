# Tool Limitations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Append deterministic, tool-specific limitations to every successful MCP response.

**Architecture:** A focused formatter maps public tool names to warnings and appends a stable Markdown section. Server invocation applies it after successful upstream calls, controlled by a boolean environment setting.

**Tech Stack:** Python 3.11+, FastMCP, pydantic-settings, pytest.

---

### Task 1: Regression tests

- [ ] Add parameterized assertions for all eight warnings, disabled formatting, and unchanged errors.
- [ ] Run focused tests and confirm failure before implementation.

### Task 2: Formatter and configuration

- [ ] Create `src/onec_buddy_mcp/limitations.py` with warning texts and formatter.
- [ ] Add `ONEC_AI_INCLUDE_LIMITATIONS: bool = True` to settings.
- [ ] Format successful `_invoke` results using the public method name.
- [ ] Run focused tests and the complete suite.

### Task 3: Documentation and publication

- [ ] Document response sections and the opt-out variable in `README.md`.
- [ ] Run a live stdio request and verify its warning.
- [ ] Review, commit, and push the scoped changes to `origin`.
