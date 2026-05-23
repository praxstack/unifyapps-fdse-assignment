# Loom recording script — UnifyApps FDSE assignment

> **Target:** 60–90 seconds. Single take. The recruiter is watching this on a phone.
>
> **What you're recording:** terminal showing `make mock-crm` + `make run-mock-llm` + the summary table, with you narrating in the camera bubble.

---

## Before you hit record

- [ ] Terminal A ready: `cd ~/Documents/workspace/unifyapps-fdse-assignment && source .venv/bin/activate` (then **don't** run anything yet)
- [ ] Terminal B ready: same dir + `source .venv/bin/activate` (don't run anything)
- [ ] Browser tab open to https://github.com/praxstack/unifyapps-fdse-assignment
- [ ] Terminal font ~16-18pt
- [ ] Loom set to "Screen + Cam", HD, 3-second countdown
- [ ] Run `pkill -f "uvicorn mock_crm"; rm -f data/onboard.db` once before recording so state is fresh
- [ ] Close Slack, calendar notifications, anything that can ping mid-record

## Take a breath. Hit record. Smile. You've got this.

---

## The 75-second script (memorize beats, not exact words)

### Beat 1 — Hook (0:00 – 0:08)

**You say (in camera bubble, looking at camera):**
> "Hi, I'm Prakhar. The UnifyApps FDSE assignment was: ingest messy customer data from S3, parse it with an LLM, and reliably push it to a flaky legacy CRM. Here's it running end-to-end in under a second."

**Your screen:** README open at the top. Mermaid diagram visible.

> **Why:** opens with the problem, not your name + life story. Recruiters skim — first 8 seconds decide whether they keep watching.

---

### Beat 2 — Start the mock CRM (0:08 – 0:18)

**You say:**
> "First terminal — I'm starting the mock legacy CRM. It's a FastAPI server that's deliberately hostile: it returns a 429 on 10% of requests and a 503 on another 5%, mimicking a real undocumented vendor API."

**You type in Terminal A:**
```
make mock-crm
```

**Wait ~2 seconds** for `Uvicorn running on http://127.0.0.1:8765`.

> **Why:** narrating *why* the CRM is hostile is the seniority signal. "I built a fault-injecting mock so my resilience layer is demonstrably real, not theoretical."

---

### Beat 3 — Switch to terminal B + run the pipeline (0:18 – 0:48)

**You say:**
> "Second terminal — I run the orchestrator against eight messy fixtures: emails, JSON, OCR scans, CSV, freeform notes."

**You type in Terminal B:**
```
make run-mock-llm
```

**As output streams (~2-5 seconds), you say** (don't read the screen verbatim — narrate over it):
> "You'll see HTTP 429s come back, the client retries with exponential backoff and jitter, and they succeed on the next attempt. One record is deliberately malformed — partial email, no TLD — and it's caught by the Pydantic validator and routed cleanly. One record is a re-send of an earlier one — same idempotency key, the CRM returns 200 with status=duplicate, no double-insert."

> **Why:** you're calling out *what's interesting* in the log stream as it scrolls. The recruiter's brain ties retry + idempotency + validation directly to the patterns you claim in the README.

---

### Beat 4 — Land on the summary table (0:48 – 1:00)

**You say** (pointing at the table):
> "Eight ingested. Six succeeded. One duplicate caught by the idempotency key. One parse-failed. Zero in the DLQ. Total wall time: under three seconds against a downstream that 5xx-ed three times."

> **Why:** the numbers do the talking. Don't add adjectives.

---

### Beat 5 — Close (1:00 – 1:15)

**You say** (camera bubble, brief eye contact):
> "Repo is in the README — circuit breaker, DLQ replay, audit log, security threat model, 76 tests passing in CI. I'd love to walk you through the design choices on a call."

**Your screen:** Click on the README's "Architecture" section briefly, then the badge bar showing CI ✅.

> **Why:** the close asks for the screen explicitly. Most candidates end with "thanks" — you end with a soft CTA.

---

## Total time: ~75 seconds

If your first take is 95 seconds, **that's fine** — Loom auto-trims silence and you can use their built-in trim tool. Aim for "under 100 seconds." Don't redo it five times trying to hit 75; the second take is always worse than the first take.

---

## After recording

1. In Loom, click **Edit Video** → trim any dead space at the start/end
2. Click **Share** → copy the link
3. Set sharing to **"Anyone with the link"** (default)
4. Optional: download the MP4 (Loom Free supports this) and host on YouTube as **"Unlisted"** — gets you a `youtu.be/...` link that embeds inline in GitHub README. Loom links show as a *thumbnail* on GitHub but don't auto-play; YouTube embeds inline.

---

## Two-line README embed (I'll add this for you once you have the link)

```markdown
## Demo (90 seconds)

[![Watch the demo](https://img.shields.io/badge/Loom-▶_90s_walkthrough-625df5?logo=loom)](YOUR_LOOM_URL_HERE)
```

Drops right under the TL;DR section in README.md. One ask — one click.

---

## Common mistakes to avoid

- **Don't read your bullet points.** Recruiters can see the screen. Narrate *why*, not *what*.
- **Don't apologize for stumbles.** "Uhhh let me show you the…" — cut it. One stumble is fine; talking about it is fatal.
- **Don't show your full screen.** Crop to the terminal + browser. They don't need to see your wallpaper or other apps.
- **Don't go over 2 minutes.** Mobile-watching attention drops off a cliff at 90s. If you have a deeper version, that's for the on-site.
- **Don't run it without `LLM_PROVIDER=mock`.** A real OpenAI call in the demo means your key flashes on screen for a millisecond. The Makefile target handles this automatically.

---

## After you have the Loom link, ping me (or paste the URL) and I'll:

1. Add the embed badge to the top of README.md
2. Commit + push it
3. Update the assignment-submission email template to mention "90-second walkthrough at the top"
