"""Agentic onboarding pipeline: S3 → LLM parser → resilient legacy CRM client.

Public surface:

- ``settings`` — application configuration loaded from env / .env.
- ``orchestrator.run`` — end-to-end pipeline entry point.
- ``schemas`` — Pydantic models for the typed contract between LLM, parser, and CRM.
- ``cli.app`` — Typer CLI exposed as the ``agentic-onboard`` console script.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
