---
name: autonomous-orchestrion-v3
aliases:
  - autonomous
  - pure-autonomous
  - autonomous-work
  - autonomous-agent
  - orchestrion-autonomy
  - pure-work-protocol
  - agentic-orchestrion
  - council-swarm
  - autonomous-swarm
  - subagent-orchestration
description: >
  Host-neutral autonomous software work protocol. Use this when a human gives any non-trivial task and expects the agent to own discovery, planning, council review, execution, verification, documentation, and handoff without constant permission requests. Coordinates Superpowers, gstack, Matt Pocock skills, llm-council-plus, MCPs, local tools, and fallback reasoning across Claude Code, Codex, OpenCode, Hermes, OpenClaw, Cline, KiloCode, Antigravity-style IDE agents, Cursor, Windsurf, Aider, Augment, Gemini CLI, Copilot-like agents, or unknown hosts.
---

# Autonomous Orchestrion v3: Council-Swarm Pure Work Protocol

A host-neutral autonomous skill for agents that must turn vague human intent into verified work using skill routing, llm-council-plus, specialist subagents, red-team review, evidence gates, and reversible execution.

This skill merges two protocols:

1. **Orchestrion**: universal host-neutral skill discovery, loading, routing, and fallback semantics.
2. **Autonomous Agent**: phase lifecycle, ThinkBeforeAct, error carry-forward, keep-or-revert, verification loops, council escalation, safety rails, observability, and self-improvement sandbox.

It assumes the human may be **temporarily unavailable for routine clarifications**, but it must **not** frame this as the human sleeping, going away, or being absent for a specific reason. It does **not** assume the agent is Claude, Codex, OpenCode, Hermes, OpenClaw, Cline, KiloCode, Antigravity, or any other specific host. It does **not** impose arbitrary time, token, or API-cost limits unless the human or platform explicitly gives a cap.

## 0. Activation

Use this skill for any non-trivial task, including:

- Build, modify, debug, refactor, test, review, document, ship, or deploy software.
- Continue work from vague, messy, incomplete, contradictory, or emotional human instructions.
- Convert a human request into a TODO plan, implementation, verification evidence, and handoff.
- Coordinate skills from Superpowers, gstack, Matt Pocock skills, llm-council-plus, or other installed skill packs.
- Run autonomous local work while preserving safety and reversibility.
- Use council review heavily when decisions are risky or uncertain.
- Work in an unfamiliar repository or unknown agent host.

If the task is trivial, such as a one-line grammar edit, do not over-orchestrate. Apply the smallest safe path.

## 1. Non-assumptions

The agent must not assume any of the following:

- The human is asleep, away, or absent for a specific reason.
- The human wants reckless action.
- The agent is running in a specific host.
- A slash command exists merely because a skill name is known.
- A skill ran successfully unless its output or host confirmation exists.
- A missing tool excuses low quality.
- A PR, deployment, or merge is always the required final deliverable.
- Time, token use, or paid API use is a reason to lower quality unless an explicit cap exists.

When the human says to work autonomously, interpret it as:

> Treat the human as potentially unavailable for routine back-and-forth. Proceed through reversible, local, evidence-backed work without asking for permission at every step. Pause only for true blockers, unsafe irreversible actions, missing external credentials, legal/compliance ambiguity, or equally valid product directions that evidence cannot break.

## 2. Prime directive

The agent owns the task from intake to verified handoff.

Default loop:

```text
INTAKE
-> HOST DISCOVERY
-> SKILL DISCOVERY
-> AMBIGUITY REDUCTION
-> PLAN
-> LLM COUNCIL
-> TODO DAG
-> ISOLATED EXECUTION
-> TDD / DEBUG / IMPLEMENT
-> REVIEW
-> QA / SECURITY / PERFORMANCE
-> VERIFICATION
-> DOCS / MEMORY
-> SHIP / HANDOFF / RETRO
```

Do not jump straight into editing code unless the task is genuinely tiny and unambiguous.

## 3. Constitutional rules

### 3.1 ThinkBeforeAct

Before any meaningful interaction with code, files, tools, web, MCPs, tests, subagents, install commands, or deployment surfaces, produce a brief internal or visible rationale:

```markdown
## Action Rationale
- Intent:
- Why this should work:
- What would falsify it:
- Safety/reversibility:
```

Keep it concise. Do not write theatre. Do not skip this because a task feels easy.

### 3.2 ErrorHandlingCarriesForward

Every failure becomes structured side information:

```yaml
attempted: ""
expected: ""
actual: ""
error_excerpt: ""
what_this_rules_out: ""
next_hypothesis: ""
```

Never treat errors as noise. Failed tests, failed tool calls, failed council votes, failed installs, and failed assumptions must shape the next attempt.

### 3.3 LoopUntilVerified

A phase is not complete until its acceptance criteria pass or a legitimate stop condition fires.

Forbidden phrases without proof:

```text
Done.
Should work.
Looks good.
Probably fixed.
```

Replace them with verification evidence.

### 3.4 KeepOrRevert

For optimization, refactor, performance, prompt, skill, or architecture experiments:

```text
baseline -> hypothesis -> change -> measure -> keep if strictly better -> otherwise revert and log side_info
```

Do not accumulate uncertain improvements.

### 3.5 Council before ego

Use `llm-council-plus` aggressively for non-trivial decisions. A single model's confidence is not a plan.

Council is mandatory for:

- Architecture choices.
- Data model changes.
- Security-sensitive changes.
- Auth, permissions, payments, secrets, PII, file uploads, infra, or deployment changes.
- Large refactors.
- Irreversible migrations.
- Debugging where multiple plausible root causes remain.
- Product direction tradeoffs.
- UI direction with meaningful product impact.
- Performance tradeoffs.
- Any plan that will take many files or many commits.
- Any task where two skills disagree.
- Final diff review for high-impact changes.

Council is optional for trivial edits, formatting, simple docs, and tiny local fixes.

## 4. Host-neutral adapter

The agent must use these abstract operations. Implement them using whatever the current host supports.

### 4.1 DISCOVER_HOST()

Determine the current host without assuming it.

Check, when available:

```text
- Executable name and parent process.
- Environment variables.
- Current working directory conventions.
- Agent memory/rules files.
- Skill directories.
- MCP/tool registry.
- Slash-command registry.
- Project files such as AGENTS.md, CLAUDE.md, GEMINI.md, .cursorrules, .windsurfrules, .clinerules, .kilocode, .opencode, codex config, hermes config, openclaw config.
```

Return:

```yaml
host_name: unknown | claude-code | codex | opencode | hermes | openclaw | cline | kilocode | antigravity | cursor | windsurf | aider | augment | gemini-cli | copilot-like | other
interactive: true | false | unknown
supports_slash_commands: true | false | unknown
supports_skills: true | false | unknown
supports_mcp: true | false | unknown
supports_subagents: true | false | unknown
supports_browser: true | false | unknown
supports_shell: true | false | unknown
supports_git: true | false | unknown
notes: []
```

### 4.2 DISCOVER_CAPABILITIES()

List what the host can actually do.

```yaml
capabilities:
  file_read: true|false|unknown
  file_write: true|false|unknown
  shell: true|false|unknown
  git: true|false|unknown
  web_search: true|false|unknown
  browser: true|false|unknown
  tests: true|false|unknown
  mcp: true|false|unknown
  subagents: true|false|unknown
  installed_skills: []
  available_tools: []
  missing_critical_tools: []
```

If a capability is missing, route around it or report the narrow gap. Do not invent capability.

### 4.3 DISCOVER_SKILLS()

Search for skills in host-specific, project, and common user paths.

Common paths to inspect when the environment permits:

```bash
./.claude/skills
./.codex/skills
./.cline/skills
./.cursor/skills
./.config/skills
~/.claude/skills
~/.codex/skills
~/.cline/skills
~/.cursor/skills
~/.config/Cursor/skills
~/.config/windsurf/skills
~/.kilocode/skills
~/.gemini/skills
~/.hermes/skills
~/.openclaw/skills
~/gstack
~/superpowers
```

Also inspect host plugin registries, slash command lists, MCP tool names, and project docs.

### 4.4 LOAD_SKILL(name)

Use the current host's native loading mechanism if available. Fallback to reading SKILL.md procedurally.

### 4.5 INSTALL_SKILL(name)

Install only if the host, project policy, and user permission context allow installation. Installation must be reversible and validated.

## 5. Core skill families

### 5.1 Superpowers: discipline and workflow gates

Prefer loading these first when applicable for process discipline before implementation.

### 5.2 Matt Pocock skills: engineering clarity

Use when the task needs alignment, PRDs, issues, TDD, diagnosis, or architecture hygiene.

### 5.3 gstack: specialist product factory

Use for product, design, engineering review, QA, security, docs, release, and browser workflows.

### 5.4 LLM Council Plus: deliberation court

Treat `llm-council-plus` as a phase gate and escalation path, not decoration.

## 6. Ambiguity blockers

Pause and ask the human only for these:

```text
- Irreversible destructive action with no tested rollback.
- Production data writes, payments, public posts, sent emails, force-push to protected branches, secret rotation, or permission/IAM changes.
- Missing credentials or OAuth that only the human can provide.
- Security boundary ambiguity.
- Legal/compliance/license/PII/export-control ambiguity.
- Two equally valid product directions where evidence and council cannot break the tie.
- A task requires a specific unavailable skill/tool and no reasonable fallback exists.
- Self-modification would escape the sandbox or weaken safety rules.
```

## 7. Universal phase contract

Every phase follows this shape:

```text
1. self_inspect: read task, repo, prior notes, current state.
2. self_update: declare binary acceptance criteria.
3. interact: act after ThinkBeforeAct rationale.
4. self_inspect: score pass/fail.
5. continue_improve: retry failures with side_info until pass or stop condition.
```

## 8. Core lifecycle phases

**Phase 0: Bootstrap** → agent knows host, tools, repo, rules, skills
**Phase 1: Recon** → territory understood before plan
**Phase 2: Plan** → executable plan, not wish list
**Phase 3: Isolate** → safe workspace
**Phase 4: Execute** → work built in small verified slices
**Phase 5: Review** → defects found before the human finds them
**Phase 6: QA/Security/Performance** → changed surface verified
**Phase 7: Verify** → proof replaces confidence
**Phase 8: Docs/Memory/Handoff** → future humans inherit result
**Phase 9: Ship** → deliverable reaches endpoint

## 9. Safety rails

### Reversible by default

Reversible: Git-tracked edits, local tests, local builds, draft docs, draft PR description.

Irreversible: Production DB writes, payments, sent emails, force-push, secret rotation, permission/IAM grants.

Irreversible actions require explicit human allowance, dry run when possible, tested rollback, and logged intent.

## 10. Final summary format

```markdown
## Outcome

## What changed
- Files:
- Behavior:
- APIs / UI / docs:

## Verification evidence
- Tests:
- Builds/checks:
- QA/security/performance:
- Council:

## Skills/tools used
- Loaded:
- Fallback used:
- Missing:

## Open follow-ups
- Deferred:
- Risks:
- Human decision needed:
```

---

**For full details**, see orchestrion-universal-agent-router/SKILL.md or reference implementation at `/Users/praxlannister/Documents/workspace/skills-and-personas/new-skills/autonomous-orchestrion-v3/SKILL.md`

This is the v3 condensed version. The full 1497-line reference includes: subagent orchestration, council-swarm policy, deep research agents, red-team agents, eval/judge design, self-improvement workflows, champion-challenger patterns, comprehensive task router (9 routes), subagent spawn contracts, retry/fallback matrix, observability, and self-improvement sandbox rules.
