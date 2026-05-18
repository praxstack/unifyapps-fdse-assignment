"""Typer CLI: ``agentic-onboard`` console script.

Three subcommands:

* ``run <path>``       — ingest from a directory and push everything through.
* ``dlq``              — list every DLQ entry from the audit DB.
* ``dlq-replay``       — re-attempt every DLQ entry (idempotency makes this safe).
* ``audit <run_id>``   — print the audit-log timeline for a given run.

Output uses :mod:`rich` for a polished summary table — not because we love
chrome, but because the recruiter is going to ``python -m agentic_onboard run``
once and the first impression has to be unambiguous.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .ingest import FileIngester
from .logging_config import configure_logging, get_logger
from .orchestrator import build_default, replay_dlq
from .schemas import PipelineResult
from .settings import get_settings

app = typer.Typer(
    name="agentic-onboard",
    help="S3 → LLM → resilient legacy CRM. UnifyApps FDSE assignment.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()
log = get_logger(__name__)


# --- run ------------------------------------------------------------------


@app.command("run")
def run_cmd(
    samples: Path = typer.Argument(  # noqa: B008
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        help="Directory of input documents (acts as the S3 bucket).",
    ),
    json_logs: bool = typer.Option(
        False, "--json-logs", help="Emit logs as JSON (for shipping to a SIEM)."
    ),
) -> None:
    """Ingest every file under SAMPLES, parse with the LLM, push to the CRM."""
    settings = get_settings()
    configure_logging(settings.log_level, json_logs=json_logs)

    ingester = FileIngester(samples)
    orch, audit, crm = build_default(settings=settings, ingester=ingester)
    try:
        result = orch.run()
    finally:
        crm.close()
        audit.close()

    _print_summary(result, settings_summary=_render_settings(settings))
    # Non-zero exit if anything ended up in the DLQ — useful for CI.
    raise typer.Exit(code=1 if result.dlq else 0)


# --- dlq ------------------------------------------------------------------


dlq_app = typer.Typer(help="Inspect or replay the dead-letter queue.")
app.add_typer(dlq_app, name="dlq")


@dlq_app.command("list")
def dlq_list_cmd() -> None:
    """Print every DLQ entry across all runs."""
    settings = get_settings()
    configure_logging(settings.log_level)
    from .audit import open_default

    audit = open_default(settings.database_url)
    try:
        rows = audit.dlq_list()
    finally:
        audit.close()

    if not rows:
        console.print("[green]DLQ is empty.[/green]")
        return

    table = Table(title="DLQ", show_lines=False)
    table.add_column("id", justify="right")
    table.add_column("run_id")
    table.add_column("source_id")
    table.add_column("customer_id")
    table.add_column("attempts", justify="right")
    table.add_column("last_error", overflow="fold", max_width=60)
    table.add_column("last_tried_at")
    for row in rows:
        table.add_row(
            str(row["id"]),
            row["run_id"][:8],
            row["source_id"],
            row["customer_id"] or "",
            str(row["attempt_count"]),
            row["last_error"],
            row["last_tried_at"],
        )
    console.print(table)


@dlq_app.command("replay")
def dlq_replay_cmd(
    run_id: str = typer.Option(None, "--run-id", help="Replay only entries from this run."),
) -> None:
    """Re-attempt every DLQ entry. Idempotency keys make this safe."""
    settings = get_settings()
    configure_logging(settings.log_level)
    from .audit import open_default
    from .crm_client import CRMClient

    audit = open_default(settings.database_url)
    crm = CRMClient(settings)
    try:
        succeeded, still_failing = replay_dlq(
            settings=settings, crm=crm, audit=audit, run_id=run_id
        )
    finally:
        crm.close()
        audit.close()

    console.print(
        f"[green]succeeded:[/green] {succeeded}    [red]still failing:[/red] {still_failing}"
    )
    raise typer.Exit(code=1 if still_failing else 0)


# --- audit ----------------------------------------------------------------


@app.command("audit")
def audit_cmd(run_id: str = typer.Argument(..., help="Run id from a previous `run`.")) -> None:
    """Print the per-step audit log for a given run."""
    settings = get_settings()
    configure_logging(settings.log_level)
    from .audit import open_default

    audit = open_default(settings.database_url)
    try:
        rows = audit.list_audit(run_id)
    finally:
        audit.close()

    table = Table(title=f"audit_log for run {run_id[:8]}", show_lines=False)
    for col in ("id", "source_id", "customer_id", "step", "status", "occurred_at", "detail"):
        table.add_column(col, overflow="fold")
    for row in rows:
        table.add_row(
            str(row["id"]),
            row["source_id"],
            row["customer_id"] or "",
            row["step"],
            row["status"],
            row["occurred_at"],
            row["detail"] or "",
        )
    console.print(table)


# --- helpers --------------------------------------------------------------


def _print_summary(result: PipelineResult, *, settings_summary: str) -> None:
    """The terminal summary the recruiter sees at end of run."""
    table = Table(
        title=f"Pipeline run {result.run_id[:8]} — {result.duration_ms} ms",
        show_lines=False,
    )
    table.add_column("metric", style="bold")
    table.add_column("count", justify="right")
    table.add_row("total ingested", str(result.total))
    table.add_row("[green]succeeded[/green]", str(result.succeeded))
    table.add_row("[blue]duplicates (idempotent)[/blue]", str(result.duplicates))
    table.add_row("[yellow]human review[/yellow]", str(result.human_review))
    table.add_row("[yellow]parse failed[/yellow]", str(result.parse_failed))
    table.add_row("[red]DLQ[/red]", str(result.dlq))
    console.print(table)
    console.print(f"[dim]{settings_summary}[/dim]")


def _render_settings(s: object) -> str:
    """One-liner summary of the active config — without leaking the API key."""
    return (
        f"llm_provider={getattr(s, 'llm_provider', '?')} | "
        f"crm={getattr(s, 'crm_base_url', '?')} | "
        f"retries={getattr(s, 'retry_max_attempts', '?')} | "
        f"breaker={getattr(s, 'circuit_breaker_threshold', '?')}/"
        f"{getattr(s, 'circuit_breaker_reset_s', '?')}s"
    )


if __name__ == "__main__":  # pragma: no cover
    app()
