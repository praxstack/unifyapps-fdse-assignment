---
name: orchestrion-universal-agent-router
description: >
  Universal host-neutral agent orchestration skill. Use this at the start of any non-trivial task to discover the current agent host, load the right installed skills, route ambiguous human requests through planning/TDD/debugging/review/QA/council gates, create TODOs, and prevent false completion. Designed to coordinate Superpowers, gstack, Matt Pocock skills, and llm-council-plus without assuming Claude, Codex, OpenCode, Hermes, OpenClaw, Cline, KiloCode, Antigravity, or any other specific agent.
---

# Orchestrion: Universal Agent Skill Router

> A host-neutral skill for agents that must coordinate many other skills without pretending every agent is the same machine.

## 0. Activation

Use Orchestrion whenever the human asks for any of the following:

- Build, modify, debug, refactor, review, test, document, ship, or deploy software.
- Turn vague human intent into a plan or implementation.
- Use or combine skills from Superpowers, gstack, Matt Pocock skills, or llm-council-plus.
- Work in an unfamiliar repository.
- Make a decision with architecture, security, product, data, deployment, or long-term maintenance risk.
- Continue work after another agent/session.
- Create TODOs for agent execution.

If the task is trivial, still perform a lightweight host/capability check, but do not run the full orchestration ceremony.

---

## 1. Prime directive

The human may provide vague, messy, contradictory, incomplete, emotional, or misspelled tasks.

Do not jump straight into implementation.

Route the task through the strongest available workflow:

```text
INTAKE
→ HOST DISCOVERY
→ SKILL DISCOVERY
→ AMBIGUITY REDUCTION
→ PLAN
→ COUNCIL CHECK WHEN HIGH-RISK
→ TODO CREATION
→ ISOLATED EXECUTION
→ TDD / DEBUG / IMPLEMENT
→ REVIEW
→ QA / SECURITY / PERFORMANCE
→ VERIFICATION
→ DOCS
→ SHIP / HANDOFF / RETRO
```

### Non-negotiable contract

```text
1. Do not pretend a skill, MCP tool, plugin, browser, or CLI exists.
2. Do not claim a skill was loaded unless it was actually invoked, read, imported, or applied through a declared fallback.
3. Do not implement through ambiguity when clarification/planning skills are available.
4. Do not patch bugs without reproduction and root-cause evidence.
5. Do not claim completion without verification evidence.
6. Do not ship without review and QA when those skills/tools exist.
7. Do not deploy without post-deploy observation when deployment/canary tools exist.
8. TODOs are the execution spine, not decoration.
```

---

## 2. Host-neutral vocabulary

Different agents expose skills differently. Use these abstract operations and map them to the current host.

| Abstract operation | Meaning |
|---|---|
| `DISCOVER_HOST()` | Identify current agent/runtime and available capability surfaces. |
| `DISCOVER_SKILLS()` | Find installed skills, slash commands, MCP tools, plugins, rule files, and project docs. |
| `LOAD_SKILL(name)` | Invoke/read/import the real skill through the host's native mechanism. |
| `RUN_SKILL(name, input)` | Execute the skill if the host supports executable skills or slash commands. |
| `FALLBACK_METHOD(name)` | Apply the documented method manually, clearly labeled as fallback. |
| `CREATE_TODO_LEDGER()` | Create a living task list with states, evidence, blockers, and skill gates. |
| `COUNCIL_QUERY()` | Use llm-council-plus through MCP, REST/API skill, CLI/web UI, or fallback prompt handoff. |

Never expose these names as fake tool calls. They are implementation-independent mental handles.

---

## 3. Host discovery

Before choosing paths, identify where you are running.

### 3.1 Detect host identity

Inspect what is available, in this order:

```text
1. System/developer/runtime metadata.
2. Built-in tool names.
3. Agent-specific command palette/slash command list.
4. Environment variables.
5. Project instruction files.
6. Local skill/plugin directories.
7. Process names or CLI help output, if terminal access exists.
```

### 3.2 Known host hints

Use these as hints, not truth. Verify locally.

| Host / agent family | Common clues | Likely skill surfaces |
|---|---|---|
| Claude Code | CLAUDE.md, ~/.claude/skills, /plugin, claude mcp | Skills, slash commands, MCP |
| OpenAI Codex CLI | AGENTS.md, ~/.codex, codex CLI | Instructions, skills/plugins where supported, terminal |
| OpenCode | ~/.config/opencode, opencode CLI | Skills/config, terminal |
| Cursor | .cursor, Cursor rules, IDE agent context | Rules, commands, MCP/tool integrations |
| Cline / Roo / KiloCode style agents | VS Code extension context, MCP config, task plan UI | MCP, project rules, edit/terminal/browser tools |
| Antigravity-style IDE agents | IDE workspace context, task/run panels | Project docs, tool use, terminal/browser if exposed |
| Hermes | ~/.hermes, Hermes memory/skills, handoff/delegation patterns | Skills, memory, CLI delegation |
| OpenClaw | OpenClaw/ClawHub context, ACP/agent sessions | Native skills, spawned coding sessions |
| Gemini CLI | GEMINI.md, Gemini CLI, MCP config | Instructions, MCP, terminal |
| GitHub Copilot coding agent | GitHub issue/PR context, Copilot agent environment | Repository instructions, PR workflows |
| Unknown agent | No reliable host signal | Markdown method fallback + available tools only |

If the host is unknown, proceed with the portable fallback protocol. Do not block unless the task requires unavailable tools.

---

## 4. Capability discovery

Create a capability matrix before running a serious workflow.

```markdown
## Capability Matrix

- Host:
- Skill mechanism available: yes/no/unknown
- Slash commands available: yes/no/unknown
- MCP available: yes/no/unknown
- Terminal available: yes/no/unknown
- File editing available: yes/no/unknown
- Browser available: yes/no/unknown
- Git available: yes/no/unknown
- Issue tracker available: yes/no/unknown
- LLM Council Plus available: yes/no/unknown
- Existing project instructions: [AGENTS.md / CLAUDE.md / GEMINI.md / .cursor rules / other]
- Missing critical capabilities:
```

### 4.1 Generic local search commands

Use only if terminal/filesystem access exists.

```bash
# Common skill and instruction locations
for d in \
  "$HOME/.claude/skills" \
  "$HOME/.codex/skills" \
  "$HOME/.config/opencode/skills" \
  "$HOME/.cursor/skills" \
  "$HOME/.hermes/skills" \
  "$HOME/.gbrain/skills" \
  "$HOME/.kiro/skills" \
  "$HOME/.slate/skills" \
  "$HOME/.factory/skills" \
  ".claude" ".cursor" ".codex" ".opencode" ".hermes" ".roo" ".clinerules" ".kilocode"
do
  [ -e "$d" ] && echo "FOUND $d"
done

# Find skill files without assuming host
find "$HOME" "$(pwd)" \
  -maxdepth 5 \( -iname "SKILL.md" -o -iname "AGENTS.md" -o -iname "CLAUDE.md" -o -iname "GEMINI.md" -o -iname "*rules*" \) \
  2>/dev/null | sort | head -200
```

---

## 5. Skill loading precedence

When multiple mechanisms exist, prefer the one with the strongest native semantics.

```text
1. Native executable skill/slash command/plugin.
2. MCP tool that performs the intended action.
3. Local SKILL.md read/import.
4. Project instruction file, such as AGENTS.md, CLAUDE.md, GEMINI.md, rules files.
5. Official repo docs.
6. Manual fallback method, clearly labeled.
```

### 5.1 Missing skill rule

If a required skill is missing:

```markdown
## Missing Skill Handling

- [ ] Name the missing skill.
- [ ] State which host/capability was checked.
- [ ] Search likely locations.
- [ ] If install is safe and permitted, install or print exact install steps.
- [ ] If install is not possible, use `FALLBACK_METHOD(skill-name)` and label it.
- [ ] Continue with best-effort only if correctness and safety are not compromised.
```

Never say "loaded X" if the agent only copied the idea of X.

---

## 6. Always-start skill gate

For non-trivial software work, first try to load:

```text
using-superpowers
```

using-superpowers is the dispatcher/constitution layer. If present, obey it first.

If unavailable, apply this fallback:

```markdown
## Fallback: using-superpowers

- [ ] Search for applicable skills before acting.
- [ ] Prefer process skills before implementation skills.
- [ ] If any skill has even a small chance of applying, inspect/load it before proceeding.
- [ ] Treat debugging/TDD/verification skills as rigid workflows.
- [ ] Treat product/design/planning skills as adaptable workflows.
```

---

## 7. Core skill families

### 7.1 Superpowers: discipline and workflow gates

Use as the constitutional workflow.

| Skill | Use when |
|---|---|
| using-superpowers | Start every non-trivial task; route to skills. |
| brainstorming | Human request is rough, ambiguous, product/design-heavy, or underspecified. |
| using-git-worktrees | Work should be isolated before implementation. |
| writing-plans | Convert accepted direction into small executable tasks. |
| executing-plans | Execute a plan with checkpoints. |
| dispatching-parallel-agents | Independent tasks can run in parallel without shared mutable conflict. |
| subagent-driven-development | Use fresh agents per task/slice. |
| test-driven-development | Build or fix via red/green/refactor. |
| systematic-debugging | Bug, regression, unknown failure, flaky behavior. |
| requesting-code-review | Ask for review before continuing/merging. |
| receiving-code-review | Process review feedback without defensiveness. |
| verification-before-completion | Before saying done. |
| finishing-a-development-branch | Final branch/PR/merge/keep/discard decision. |
| writing-skills | Create or improve skills. |

### 7.2 Matt Pocock skills: engineering clarity

Use to turn unclear work into crisp engineering artifacts.

| Skill | Use when |
|---|---|
| setup-matt-pocock-skills | First-time repo setup. |
| grill-me | Non-code or general ambiguity. |
| grill-with-docs | Code/product task requiring shared context, CONTEXT.md, ADRs. |
| to-prd | Convert conversation/plan to PRD. |
| to-issues | Slice PRD/plan into vertical issues. |
| tdd | Implement a vertical slice with tests. |
| diagnose | Debug hard issues with reproduce/minimize/hypothesize/instrument/fix/regression-test. |
| triage | Classify and route issues. |
| zoom-out | Understand architecture/system context. |
| improve-codebase-architecture | Refactor toward better boundaries/deep modules. |
| prototype | Explore throwaway UI/business-logic direction. |
| handoff | Compress context for another session/agent. |
| caveman | Ultra-compressed token-saving mode. |
| write-a-skill | Create a new skill. |
| git-guardrails-claude-code | Apply git safety patterns even if host is not Claude. |
| setup-pre-commit | Add quality gates. |

### 7.3 gstack: specialist product/engineering team

Use for role-based scrutiny and shipping. (Comprehensive list of 30+ gstack skills available in full reference docs)

### 7.4 llm-council-plus: deliberation gate

Use for high-stakes decisions, not routine edits.

Council should be used for: architecture decisions, security-sensitive work, irreversible migrations, large refactors, unclear product strategy, major UI direction choices, multiple plausible root causes, performance tradeoffs, API/data model design, deployment risk, when skills disagree, before high-impact shipping.

Council should usually be skipped for: typos, formatting, simple copy changes, obvious one-line fixes, routine tests, low-risk dependency bumps.

---

## 8. Task router

### 8.1 Vague or ambiguous task

```text
using-superpowers
→ brainstorming
→ grill-me OR grill-with-docs
→ /office-hours if product-ish
→ llm-council-plus if high-impact or options conflict
```

### 8.2 New feature

```text
using-superpowers
→ brainstorming
→ grill-with-docs
→ /office-hours
→ /autoplan
→ /plan-ceo-review
→ /plan-eng-review
→ /plan-design-review if UI/UX
→ /plan-devex-review if developer-facing
→ llm-council-plus if high-impact
→ to-prd
→ to-issues
→ using-git-worktrees
→ writing-plans
→ subagent-driven-development OR executing-plans
→ test-driven-development OR tdd
→ /review
→ requesting-code-review
→ receiving-code-review if needed
→ /qa
→ verification-before-completion
→ /document-release
→ /ship
```

### 8.3 Bug, regression, or flaky behavior

```text
using-superpowers
→ systematic-debugging
→ diagnose
→ /investigate
→ zoom-out if architecture unclear
→ llm-council-plus if root cause disputed
→ test-driven-development OR tdd
→ /review
→ /qa OR /qa-only
→ verification-before-completion
```

Hard rule: **No root cause, no fix. No regression test, no completion.**

### 8.4 Architecture cleanup/refactor

```text
using-superpowers
→ zoom-out
→ improve-codebase-architecture
→ /plan-eng-review
→ llm-council-plus
→ to-prd
→ to-issues
→ using-git-worktrees
→ writing-plans
→ test-driven-development OR tdd
→ /review
→ verification-before-completion
```

### 8.5 UI/UX/frontend polish

```text
using-superpowers
→ brainstorming
→ grill-with-docs
→ /plan-design-review
→ /design-consultation if direction unclear
→ /design-shotgun if alternatives useful
→ /design-html if converting approved mockup
→ /design-review
→ /qa
→ /benchmark if performance-sensitive
```

### 8.6 Security-sensitive work

```text
using-superpowers
→ careful / guard / freeze if available
→ git-guardrails-claude-code or equivalent
→ /cso
→ llm-council-plus
→ /review
→ verification-before-completion
```

---

## 9. Master TODO ledger

Maintain a living ledger. Use the host's TODO tool if available; otherwise maintain this Markdown.

```markdown
# Orchestrion TODO Ledger

## Task
- Human request:
- Interpreted goal:
- Host:
- Repo:
- Branch/worktree:
- Risk level: low / medium / high / critical

## Capabilities
- Skills:
- MCP:
- Terminal:
- Browser:
- Git:
- Council:

## Assumptions
- [ ] ...

## Skill gates
- [ ] using-superpowers: loaded / fallback / unavailable
- [ ] ambiguity reducer:
- [ ] product gate:
- [ ] engineering gate:
- [ ] council gate:
- [ ] TDD/debug gate:
- [ ] review gate:
- [ ] QA gate:
- [ ] security gate:
- [ ] verification gate:
- [ ] docs gate:
- [ ] ship/handoff gate:

## Work items
| ID | State | Task | Skill/source | Evidence | Blocker |
|---|---|---|---|---|---|
| T1 | todo |  |  |  |  |

## Evidence
- Tests:
- Logs:
- Screenshots:
- URLs:
- Commits:
- PR:
- Council result:
- Review result:
```

State values: `todo`, `doing`, `blocked`, `needs-human`, `needs-council`, `needs-review`, `needs-qa`, `done`, `discarded`

---

## 10. Output rules

When reporting back to the human:

1. Say what was done.
2. Say which skills were actually loaded or which fallbacks were used.
3. Show the TODO ledger state.
4. Evidence for claims.
5. Next concrete action (if any).
