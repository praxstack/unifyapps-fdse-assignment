# Cline Project Skills Directory

This directory contains **project-level skills** for Cline and other agents working on this project.

## Structure

```
.cline/
├── skills/
│   └── orchestrion-universal-agent-router/
│       ├── SKILL.md
│       └── README.md
└── README.md (this file)
```

## Available Skills

### orchestrion-universal-agent-router

**Purpose**: Universal host-neutral agent orchestration skill for coordinating complex workflows.

**When to use**:
- At the start of any non-trivial task
- When discovering current agent host and capabilities
- When routing ambiguous requests through planning/TDD/debugging/review/QA gates
- When creating TODOs for execution
- When coordinating Superpowers, gstack, Matt Pocock skills, or llm-council-plus

**What it does**:
- Host discovery and capability matrix creation
- Skill loading precedence and fallback handling
- Task routing through appropriate workflow gates
- TODO ledger management
- Non-negotiable contract enforcement (no fake completions, no unverified claims)

## How Skills Load in Cline

Cline automatically discovers and loads skills from this `.cline/skills/` directory. Skills in this location are:

- **Project-scoped** (only available in this workspace)
- **Loaded before global skills** (when there's a conflict, project skills take precedence)
- **Shareable** (other agents and team members get the same skill definitions)
- **Version-controlled** (can be tracked in git for consistency)

## Using Project Skills

### Via skill loading in Claude Code / Cline:

```text
1. Start any task by referencing the skill name or workflow
2. Cline will automatically discover the skill from `.cline/skills/`
3. The skill is applied according to its activation conditions
```

### Example: Orchestrion workflow

When you need to build, refactor, debug, or deploy:

1. Cline reads `orchestrion-universal-agent-router.md`
2. Skill performs host discovery → skill discovery → task routing
3. Executes through appropriate gates (planning → TDD → review → QA → verification)

## Skill File Format

Skills are Markdown files with YAML frontmatter:

```yaml
---
name: skill-name
description: >
  Brief description of what this skill does
---

# Full documentation in Markdown
```

- `name`: Machine-readable identifier
- `description`: One-liner for skill discovery
- Content: Full methodology, workflows, and fallbacks

## Adding New Project Skills

To add a new project-level skill:

1. Create a `.md` file in `.cline/skills/`
2. Include YAML frontmatter with `name` and `description`
3. Document the skill methodology, workflows, and activations
4. Commit to version control

## Project Context

- **Repo**: unifyapps-fdse-assignment
- **Project Type**: Python agentic onboarding system
- **Skills Focus**: Universal agent orchestration (host-neutral)
- **Maintained by**: Prax

## References

- Global Cline skills: `~/.cline/skills/`
- Global Codex skills: `~/.codex/skills/`
- Orchestrion skill GitHub: https://github.com/skills-repo/orchestrion-universal-agent-router

---

**Last updated**: 2026-05-24
**Version**: 1.0
