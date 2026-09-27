# ADR-005: Computer Use, Serena Semantic Engine & Sandboxed Execution
**Status:** Accepted  
**Date:** 2026-09-27  

## Context
Enabling AI agents to control operating systems, run shell commands, and edit code presents critical security risks (accidental file deletion, remote code execution, prompt injection).

## Decision
1. **Four Risk Classes**: Every tool call is categorized as `READ`, `REVERSIBLE_WRITE`, `EXTERNAL_COMMUNICATION`, or `HIGH_IMPACT`.
2. **Semantic Code Operations over Raw Replacement**: Integrate the Serena Semantic Engine (MCP) for AST-level symbol inspection and surgical editing.
3. **Execution Sandbox**: Shell commands execute strictly in isolated project directory roots with allowlisted binaries and timeout bounds.
4. **Interactive Human Approval**: High-impact and external communication actions mandate non-bypassable user confirmation via UI or signed confirmation tokens.

## Consequences
- Prevents catastrophic system damage while empowering the assistant to safely edit code and manage development workflows.
