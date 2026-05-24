# Orchestrion Universal Agent Router

**Project-Level Skill for Host-Neutral Agent Orchestration**

## What This Skill Does

Orchestrion is a universal orchestration framework that **routes tasks through the right planning, execution, and QA gates without assuming a specific agent host**.

Instead of baking assumptions about which agent (Claude Code, Cline, Cursor, Codex, Hermes, OpenClaw, etc.) is running the task, Orchestrion detects the current host and automatically:

1. **Discovers installed skills** from the right locations (native, MCP, project-level, global)
2. **Routes tasks intelligently** through specialized skills for:
   - Ambiguous/exploratory work → planning mode
   - Features → blueprint + spec + implementation
   - Bugs → diagnose + root cause + fix + verify
   - Refactoring → improve-codebase-architecture + review
   - UI/UX → design consultation + implementation
   - DX/APIs → devex review + documentation
   - Security → threat modeling + remediation
   - Testing → test strategy + implementation
3. **Coordinates skill families** without forcing a single opinionated family:
   - Superpowers (Vercel/Copilot ecosystem)
   - gstack (Cursor/GStack)
   - Matt Pocock skills (TypeScript/architecture)
   - llm-council-plus (multi-model deliberation)
4. **Enforces verification gates** on completion claims (no fake completions, no unverified claims)

## Why It Matters

You can use this **project** with different agents (run it in Claude Code, then Cline, then Cursor) and Orchestrion automatically adapts skill loading, task routing, and output formatting to each host's native capabilities.

**Without Orchestrion:** Each agent assumes its own skill environment, leading to missing skills, wrong skill versions, or incorrect task routing.

**With Orchestrion:** One task router works across all compatible agents at project level.

## Installation

This skill is already installed at the project level in `.cline/skills/orchestrion-universal-agent-router/`.

### For Cline Users

Cline automatically discovers and loads skills from `.cline/skills/` on startup. No additional setup needed.

### For Claude Code Users

Claude Code looks for project-level skills using the Claude Code MCP protocol. If you've configured `.cline/` in your project instructions, Claude Code will load this skill.

### For Other Agents

Check your agent's documentation on project-level skill loading:
- **Cursor:** `.cursor/skills/` directory
- **Codex:** Global `~/.codex/skills/` or project-level via configuration
- **Hermes/OpenClaw:** Project instructions or MCP server registration

## Usage

### Activation

Orchestrion activates automatically at task start when the agent detects this skill is installed. It runs silently unless:
- Task routing requires explicit user confirmation (ambiguous tasks, scope decisions)
- Host detection returns "Unknown" (fallback to manual routing)
- A task has multiple possible paths (feature vs refactoring vs research)

### Core Workflow

1. **User submits task** → Orchestrion detects agent host
2. **Host discovery** → Loads skill list from detected host locations
3. **Task classification** → Routes to specialized skill family
4. **Skill execution** → Coordinates with specific skills (blueprint, design, testing, etc.)
5. **Verification gates** → Enforces proof-of-work before completion claims
6. **Output formatting** → Adapts output to host's native format

### Example: Feature Implementation

```
User: "Build a Redis caching layer for the API"
↓
Orchestrion detects: Cline host
↓
Loads skills: blueprint, spec-creator, backend architecture, testing
↓
Routes to: Feature workflow
↓
Executes:
  1. blueprint skill → creates .blueprint.md
  2. spec-creator skill → creates SPEC.md
  3. Code implementation (backend-specific)
  4. test-master skill → writes test suite
  5. verification gate → proof tests pass + no regressions
↓
Output: Verified feature, tests passing, PR ready
```

### Example: Ambiguous Task

```
User: "Help me understand why the onboarding flow drops off"
↓
Orchestrion detects: Task is investigatory + ambiguous
↓
Routes to: Planning mode
↓
Choices presented:
  - Product discovery (interview customers)
  - Analytics diagnosis (cohort analysis)
  - UX research (user testing)
  - Performance audit (page speed)
↓
User picks "UX research"
↓
Orchestrion routes to: usability-tester + ux-heuristics + improve-retention
```

## Skill References

See **SKILL.md** in this directory for:
- Complete host detection table and hints
- Skill loading precedence rules
- All task routing workflows
- Verification gate details
- Master TODO ledger for multi-phase work
- 8 non-negotiable rules enforcing completion integrity

## Project Context

This skill is installed as part of the **unifyapps-fdse-assignment** project to enable:

- **Agentic onboarding** workflows that work across different AI agent hosts
- **Universal task routing** without hardcoding assumptions about which agent is running
- **Skill family coordination** (combining features from gstack, Superpowers, Matt Pocock, and council-based deliberation)
- **Verification-first execution** (no fake completions, proof before claims)

## Quick Start

1. **For this project:** Skills are automatically discovered at `.cline/skills/`
2. **Run any task:** Orchestrion automatically activates and routes appropriately
3. **Check host hints:** See SKILL.md for your specific agent host
4. **Consult task router:** See SKILL.md section "Task Router" for your task type

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Skill not detected | Check `.cline/skills/` exists and this directory is readable |
| Wrong task routing | Check "Task Classification" in SKILL.md; confirm task type |
| Skills not loading | Review "Skill Loading Precedence" in SKILL.md for host hints |
| Host detection failed | Manually set agent type in project instructions or .cline/AGENTS.md |

## References

- **SKILL.md** – Portable skill definition (load into any agent that supports SKILL.md format)
- **.cline/README.md** – Project-level skills setup documentation
- **ARCHITECTURE.md** – Project architecture and integration points
