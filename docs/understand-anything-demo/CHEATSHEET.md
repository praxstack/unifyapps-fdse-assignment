# Understand-Anything cheat sheet for `praxstack/unifyapps-fdse-assignment`

> Generated 2026-05-23. Tool already installed system-wide (`~/.understand-anything/repo/` + symlinks in `~/.cline/skills/`).

---

## What's in this folder

- `CHEATSHEET.md` — this file
- `crm_client.structure.json` — real output from running the deterministic structure extractor on `src/agentic_onboard/crm_client.py`. Shows what tree-sitter pulls out before the LLM wraps it in summaries. **4 classes, 7 methods, 21 call-graph edges, all in milliseconds, zero LLM cost.**

---

## Why I'm not running `/understand` for you in this Cline session

The full pipeline is a 7-phase multi-agent flow:

| Phase | Cost | What it does |
|---|---|---|
| 0 — Pre-flight | free | git + plugin root checks (✅ done) |
| 0.5 — Ignore config | free | generates `.understandignore` (✅ done by Cline-VSC if started) |
| 1 — SCAN | 1 LLM call | discovers files, detects languages/frameworks |
| **2 — ANALYZE** | **5 parallel subagent LLM calls × ceil(N/25) batches** | the expensive part. Each subagent processes 20-30 files. |
| 3 — Assemble review | 1 LLM call | merges + validates the batch outputs |
| 4 — Architecture | 1 LLM call | groups files into layers |
| 5 — Tour | 1 LLM call | builds an ordered onboarding tour |
| 6 — Review | 1 LLM call | final validation |
| 7 — Save | free | writes `knowledge-graph.json` + opens dashboard |

Cline-VSC's `Task` primitive doesn't natively support Claude Code-style parallel subagent dispatch. Simulating it in one chat thread blows the context window mid-run. **Claude Code is the right place to run this.**

---

## How to run `/understand` in Claude Code (2 min, then walk away for 10 min)

```bash
# 1. Open a new Claude Code session in the project
cd /Users/praxlannister/Documents/workspace/unifyapps-fdse-assignment
claude

# 2. In the Claude Code prompt, run:
/understand
```

That's it. Claude Code will:

1. Use Phase 0's pre-flight (the plugin is already built, so this is instant)
2. Generate `.understand-anything/.understandignore` and ask you to confirm — review it, just say "yes go"
3. Dispatch 1 SCAN subagent → finds your 12 source files, 8 sample fixtures, 10 test files
4. Dispatch ~3 ANALYZE subagents in parallel (20-30 files per batch) — this is where most of the time goes
5. Run the rest of the pipeline → writes `knowledge-graph.json`
6. Auto-launch `/understand-dashboard` — opens an interactive web UI in your browser

**Expected wall time:** 8-12 min for this repo. Tokens: ~500K-800K (~$2-4 on Claude Sonnet via Claude Code's quota).

---

## Top-3 commands to actually use afterwards

```bash
# Best onboarding artifact for the recruiter
/understand-onboard
# → generates a step-by-step learning path through your code, ordered by dependency

# Deep-dive your most interesting file
/understand-explain src/agentic_onboard/crm_client.py
# → plain-English explanation of every class + method, plus connection to the rest of the codebase

# Pre-PR impact analysis (try this on your next change)
/understand-diff
# → analyzes uncommitted changes and shows the ripple effect on the graph
```

---

## Optional: pre-build the graph and commit it

The graph is just JSON — you can commit it once and recruiters skip the pipeline:

```bash
# After /understand finishes
git add .understand-anything/
git commit -m "docs: add knowledge graph for navigation"
git push
```

If you do this, add a section to your README:

```markdown
## Explore the codebase visually

This repo ships with an [Understand-Anything](https://github.com/Lum1104/Understand-Anything) knowledge graph. Open it interactively:

```bash
git clone https://github.com/praxstack/unifyapps-fdse-assignment
cd unifyapps-fdse-assignment

# Install Understand-Anything (if not already)
curl -fsSL https://raw.githubusercontent.com/Lum1104/Understand-Anything/main/install.sh | bash -s claude

# Launch the dashboard (uses the committed graph — no re-analysis needed)
/understand-dashboard
```

This is a *very* high-signal addition to your assignment submission for UnifyApps — they're a tool company themselves, they'll appreciate seeing you adopt sharp dev tools and integrate them into your delivery story.

---

## If things break

```bash
# Reinstall
rm -rf ~/.understand-anything ~/.understand-anything-plugin ~/.cline/skills/understand*
curl -fsSL https://raw.githubusercontent.com/Lum1104/Understand-Anything/main/install.sh | bash -s cline

# Rebuild the TS core (after a repo update)
cd ~/.understand-anything-plugin && pnpm install --force && pnpm --filter @understand-anything/core build

# Force a fresh graph (delete cached state)
rm -rf .understand-anything/
/understand --full
```

---

## What the deterministic extractor pulled from `crm_client.py`

Look at `crm_client.structure.json` in this folder. The interesting parts:

```json
{
  "classes": [
    { "name": "CRMClient", "startLine": 69, "endLine": 209,
      "methods": ["__init__", "__enter__", "__exit__", "close", "breaker", "upsert", "_do_upsert"] },
    { "name": "CRMError", "..." },
    { "name": "CRMRetriableError", "..." },
    { "name": "CRMPermanentError", "..." }
  ],
  "callGraph": [
    { "caller": "upsert", "callee": "self._breaker.before_call", "lineNumber": 132 },
    { "caller": "upsert", "callee": "Retrying", "lineNumber": 137 },
    { "caller": "upsert", "callee": "stop_after_attempt", "lineNumber": 138 },
    { "caller": "upsert", "callee": "wait_exponential_jitter", "lineNumber": 139 },
    { "caller": "upsert", "callee": "self._do_upsert", "..." },
    { "caller": "_do_upsert", "callee": "self._client.post", "..." },
    ...
  ]
}
```

This is the literal tree-sitter parse — exact, deterministic, free. The `/understand` pipeline takes 12 of these (one per source file), feeds them into 5 parallel LLM agents, and the agents add: `summary` per class/method, `tags` like `["resilience", "http-client", "idempotency"]`, layer assignment ("Application / CRM client"), tour position ("Step 4: Resilient external calls"), and `complexity: moderate`. Then it cross-links them via the call edges.

---

## Tips that aren't in the README

1. **Run `/understand --review` after `/understand`** — re-runs just the LLM graph reviewer phase against the existing graph, catches inconsistencies the first run might have missed. About 1/10th the cost of a full run.

2. **Watch out for the auto-update hook** — the README mentions `/understand --auto-update`. This installs a post-commit hook that re-runs incremental analysis on every commit. Useful for active projects, expensive for one-off submissions. Skip for this assignment.

3. **The `language` flag is great for non-English audiences** — `/understand --language ja` localizes node summaries + dashboard UI to Japanese. Not relevant for UnifyApps but worth knowing.

4. **Dashboard is just a static SPA** — `.understand-anything/dashboard/` is a vanilla web app you can serve with any HTTP server. After running once, the dashboard works offline.
