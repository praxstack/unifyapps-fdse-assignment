# Autonomous Orchestrion v3: Council-Swarm Pure Work Protocol

**Project-Level Skill for Host-Neutral Autonomous Work**

## What This Skill Does

Autonomous Orchestrion v3 is a **pure autonomous work protocol** that enables agents to take tasks from vague human intent all the way through to verified, production-ready handoff without constant permission requests.

Unlike manual skills, Autonomy Orchestrion orchestrates an entire workflow:

1. **Host discovery** – Detects the current agent environment
2. **Skill discovery & loading** – Finds and loads all available skills
3. **Planning with council review** – llm-council-plus gates architecture/security/risky decisions
4. **Subagent orchestration** – Spawns specialist agents (researchers, architects, reviewers, red-teams, QA)
5. **TDD execution** – Builds changes in small, tested slices
6. **Multi-stage review** – Code review, security review, QA, performance testing
7. **Verification gates** – Proof before claims, no fake completions
8. **Documentation & handoff** – Memory, docs, and session log

## Why It Matters

**Without Orchestrion v3:** Agents ask permission constantly, make local decisions without evidence, and deliver code without rigorous verification.

**With Orchestrion v3:** Agents take ownership—planning, executing, reviewing, testing, and shipping in a single continuous workflow while preserving safety and reversibility.

Key difference from other skills:
- **Not a reference guide** – It's an executable protocol with phases, gates, and rollback rules
- **Council-integrated** – Escalates architecture, security, and risky decisions to llm-council-plus
- **Subagent-native** – Spawns fresh-context reviewers, red-teams, and specialists
- **Verification-first** – No "done" without proof; forbidden phrases like "should work"
- **Host-neutral** – Works across Claude Code, Cline, Cursor, Codex, Hermes, etc.

## Installation

This skill is already installed at the project level in `.cline/skills/autonomous-orchestrion-v3/`.

### For Cline Users

Cline automatically discovers and loads skills from `.cline/skills/` on startup. No additional setup needed.

### For Claude Code Users

Claude Code loads project-level skills via MCP protocol. If `.cline/` is configured in your project instructions, this skill will be discoverable.

### For Other Agents

- **Cursor:** `.cursor/skills/` directory
- **Codex:** Global `~/.codex/skills/` or project-level via configuration
- **Hermes/OpenClaw:** Project instructions or MCP server registration

## Usage

### Activation

Activate **autonomous-orchestrion-v3** at the start of any non-trivial task:

```text
User: "Build a Redis caching layer with fallback for the API"
↓
Orchestrion v3 activates
↓
- Host discovery (detect: Cline)
- Skill discovery (find: blueprint, spec-creator, testing skills)
- Planning phase with council review
- Spawn: repo-cartographer, architecture-critic, test-strategist
- Execute: TDD loop with git worktree isolation
- Review: code-review, security review, QA
- Verify: tests pass, no regressions, docs updated
- Deliver: PR ready, session log complete
```

### Core Workflow Phases

```
INTAKE
├─ Parse task, detect blockers
│
BOOTSTRAP
├─ DISCOVER_HOST() → Detect current agent (Cline, Claude Code, Cursor, etc.)
├─ DISCOVER_CAPABILITIES() → File I/O, shell, git, browser, MCP, subagents
├─ DISCOVER_SKILLS() → Load project skills, fallback to global, procedural
├─ Load or fallback to this skill
│
RECON
├─ Map codebase (spawn repo-cartographer if unfamiliar)
├─ Identify risks, unknowns, related code
├─ Produce Recon Note
│
PLAN
├─ Define SPEC: requirements, non-goals, risks
├─ Define BLUEPRINT: steps, files, tests, rollback
├─ Define TODO DAG with dependencies
├─ Spawn: research-scout, architecture-critic, red-team (for risky work)
├─ Send to llm-council-plus for non-trivial decisions
├─ Record rejected alternatives
│
ISOLATE
├─ Create git worktree or branch (if safe)
├─ Snapshot baseline tests
│
EXECUTE
├─ Use TDD: write failing test → implement → refactor → commit
├─ For each task: small verified slices
├─ If blocked: diagnose, call council with failure trace
│
REVIEW
├─ Code review (via review skill or fresh-context reviewer subagent)
├─ Security review (via cso skill or red-team subagent)
├─ Run council final-diff review for high-impact changes
│
QA / SECURITY / PERFORMANCE
├─ Run qa skill (UI testing, behavior verification)
├─ Run design-review if UI changed
├─ Run benchmark if performance-sensitive
├─ Add regression tests for verified bugs
│
VERIFY
├─ Run full test suite
├─ Run typecheck, lint, format, build, smoke tests
├─ Compare behavior to acceptance criteria
├─ Confirm no unrelated changes
│
DOCS / MEMORY / HANDOFF
├─ Update README, ADRs, CONTEXT.md
├─ Run sync-gbrain or learn (memory tools)
├─ Run handoff if another session may continue
│
SHIP / FINAL HANDOFF
├─ Run ship skill (merge, deploy, or generate PR)
├─ Run canary (monitor post-deploy)
├─ Run retro for non-trivial work
```

### Constitutional Rules (Always Apply)

1. **ThinkBeforeAct** – Brief rationale before any action on code/files/tools/deployment
2. **ErrorHandlingCarriesForward** – Errors become structured side-information for next attempt
3. **LoopUntilVerified** – Phases complete only when acceptance criteria pass
4. **KeepOrRevert** – Experiments: baseline → hypothesis → change → measure → keep or revert
5. **CouncilBeforeEgo** – Escalate architecture, security, risky decisions to council

### Ambiguity Blockers (Ask Human Only For)

```text
✓ Irreversible destructive action
✓ Production data writes, payments, sent emails
✓ Force-push to protected branches
✓ Missing credentials or OAuth
✓ Security boundary ambiguity
✓ Legal/compliance/license/PII ambiguity
✓ Equally valid product directions (evidence can't break tie)
✓ Required skill/tool unavailable + no fallback

✗ Vague requirements (infer, document, proceed reversibly)
✗ Failing tests (debug it)
✗ Missing skill with procedural fallback (use fallback, log it)
✗ Work takes time (continue while session allows)
✗ Work uses paid APIs (prefer quality, use council where valuable)
```

## Skill References

See **SKILL.md** in this directory for:
- Complete host detection table (Cline, Claude Code, Cursor, Codex, Hermes, OpenClaw, etc.)
- DISCOVER_* operations with return schemas
- Subagent orchestration patterns with spawn contracts
- Council-swarm policy for coordinating subagents + llm-council-plus
- Comprehensive task router (9 routes: feature, bug, refactor, UI/UX, API/DX, security, testing, docs)
- Retry/fallback matrix with 6 tiers
- Observability logging and session telemetry labels
- Self-improvement sandbox with gating rules
- Final summary format (facts and proof, no marketing)

## Project Context

This skill is installed as part of the **unifyapps-fdse-assignment** project to enable:

- **Agentic onboarding** workflows where agents own entire feature cycles
- **Council-governed decisions** for architecture, security, and high-risk changes
- **Subagent coordination** for parallel research, review, and testing
- **Host-neutral execution** across different AI agent tools
- **Verification-first delivery** with no fake completions

## Quick Start

1. **Start a non-trivial task:** Orchestrion v3 activates automatically if installed
2. **Task routing:** Orchestrion detects task type (feature/bug/refactor/security/etc.) and routes through appropriate phases
3. **Phase execution:** Each phase follows the universal contract (inspect → criteria → act → verify → improve)
4. **Council escalation:** Architecture/security/risky decisions route to llm-council-plus
5. **Subagent spawning:** Specialist agents (reviewers, red-teams, QA) run in parallel for non-trivial work
6. **Verification gates:** No phase completes without proof; no fake claims

## Example Task: "Add multi-tenant database support"

```
User: "Add multi-tenant database support with schema isolation"
↓
Orchestrion v3 reads task
↓
BOOTSTRAP
├─ Host: Cline
├─ Capabilities: file R/W, shell, git, tests, subagents, MCP
├─ Skills: blueprint, spec-creator, testing, security, orchestrion-v3
│
RECON
├─ Spawn repo-cartographer → module map, DB schema, multi-tenancy risks
│
PLAN
├─ SPEC: requirements (isolation, performance, migration), non-goals (sharding)
├─ BLUEPRINT: schema migration, auth layer, tests, rollback
├─ Spawn: architecture-critic (isolation options), red-team (security), test-strategist
├─ Council review: tenant isolation strategy, rollback risk
│
EXECUTE (TDD)
├─ Write failing test for tenant isolation
├─ Implement schema changes
├─ Add auth middleware
├─ Run focused tests
├─ Commit: "WIP: schema migration"
├─ Repeat for each tenant-aware feature
│
REVIEW + QA
├─ Code review (schema impact)
├─ Security review (isolation boundary)
├─ QA: test data across tenants
├─ Benchmark: multi-tenant query performance
│
VERIFY + SHIP
├─ Full test suite passes
├─ Migration rollback tested
├─ Docs updated
├─ PR created, deployed to staging
├─ Canary monitored
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Skill not activated | Check `.cline/skills/` exists; restart agent |
| Skills not discovered | Review DISCOVER_SKILLS() in SKILL.md; check skill paths |
| Council not available | Install llm-council-plus; verify MCP registration |
| Subagents not spawning | Check host supports subagents; use fallback to lead-agent-only mode |
| Phase criteria failed | Never weaken criteria mid-loop; revise criterion, restart phase, log change |
| Repeated failures | Escalate to council with full error trace; use retry/fallback matrix |

## References

- **SKILL.md** – Portable skill definition (full 1497-line reference with advanced workflows)
- **.cline/README.md** – Project-level skills setup documentation
- **orchestrion-universal-agent-router/** – Companion skill for host discovery routing
- **ARCHITECTURE.md** – Project architecture and integration points

---

**Remember:** This is not just a reference guide—it's an executable protocol. Follow the phases, respect the gates, verify before claiming done, and preserve reversibility.
