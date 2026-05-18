"""FastAPI app that simulates an undocumented legacy CRM.

What it does:

* Exposes ``POST /v0/customer.upsert`` with a deliberately *minimal* OpenAPI
  surface — no schema docs in the path operation; you have to read the source
  to figure it out (mimics "undocumented legacy API" from the prompt).
* Honours the ``Idempotency-Key`` header. A request with a key we have already
  seen returns ``status="duplicate"`` with the original ``crm_record_id``.
* Injects faults — 429 on ``CRM_FAULT_RATE_429`` of requests, 503 on
  ``CRM_FAULT_RATE_503``, plus optional latency. This is what makes the
  client's resilience layer demonstrably real, not theoretical.
* Exposes ``GET /health`` for the docker-compose healthcheck.
* Exposes ``GET /v0/admin/records`` (read-only) so a curious reviewer can see
  what landed.

Persistence is in-memory only; restart wipes it. That's intentional — the
audit log on the *client* side is the source of truth, not the CRM. (Mirrors
the real-world dynamic where a vendor's legacy system is unreliable and the
integration team owns the audit trail.)
"""

from __future__ import annotations

import os
import random
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

# --- Config (read once on app start) ----------------------------------------


def _f(env: str, default: float) -> float:
    try:
        return float(os.environ.get(env, default))
    except (TypeError, ValueError):
        return default


def _i(env: str, default: int) -> int:
    try:
        return int(os.environ.get(env, default))
    except (TypeError, ValueError):
        return default


FAULT_RATE_429 = max(0.0, min(1.0, _f("CRM_FAULT_RATE_429", 0.10)))
FAULT_RATE_503 = max(0.0, min(1.0, _f("CRM_FAULT_RATE_503", 0.05)))
LATENCY_MIN_MS = max(0, _i("CRM_LATENCY_MS_MIN", 20))
LATENCY_MAX_MS = max(LATENCY_MIN_MS, _i("CRM_LATENCY_MS_MAX", 120))


# --- App -------------------------------------------------------------------


app = FastAPI(
    title="Legacy CRM",
    version="v0",
    description=(
        "Hostile vendor API circa 2014. Tolerates `Idempotency-Key`, "
        "occasionally returns 429 and 503. Don't ask for a Swagger spec."
    ),
    openapi_url="/openapi.json",
    docs_url="/docs",
)


# In-memory store. Seeded by `Idempotency-Key` so a replay never mutates twice.
# Two dicts:
#   _by_key       — key → record id (for the dedup short-circuit)
#   _by_record    — record id → full record (for `GET /v0/admin/records`)
_by_key: dict[str, str] = {}
_by_record: dict[str, dict[str, Any]] = {}
_seq = 0


def _next_id() -> str:
    global _seq
    _seq += 1
    return f"crm-{_seq:06d}"


# --- Fault injection -------------------------------------------------------


def _inject_latency() -> None:
    if LATENCY_MAX_MS <= 0:
        return
    delay_ms = random.randint(LATENCY_MIN_MS, LATENCY_MAX_MS)  # noqa: S311 - not crypto
    time.sleep(delay_ms / 1000)


def _maybe_fail() -> None:
    """Raise HTTPException 429/503 with the configured probabilities.

    Order matters: 503 first (rarer), then 429. The two are independent rolls
    so the combined fault rate is roughly ``FAULT_RATE_429 + FAULT_RATE_503``.
    """
    r = random.random()  # noqa: S311 - not crypto
    if r < FAULT_RATE_503:
        raise HTTPException(status_code=503, detail="upstream temporarily unavailable")
    if r < FAULT_RATE_503 + FAULT_RATE_429:
        # Send a Retry-After header to model what real CRMs do.
        raise HTTPException(
            status_code=429,
            detail="rate limit exceeded",
            headers={"Retry-After": "1"},
        )


# --- Endpoints --------------------------------------------------------------


@app.get("/health", include_in_schema=False)
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v0/admin/records")
def list_records() -> dict[str, Any]:
    """Read-only — handy for ad-hoc inspection. Returns the full in-memory store."""
    return {"count": len(_by_record), "records": list(_by_record.values())}


@app.post("/v0/customer.upsert")
async def customer_upsert(
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> JSONResponse:
    """Upsert a customer record.

    Quirks (intentional, mirroring real legacy systems):

    * ``Idempotency-Key`` is required. Missing → 422.
    * Body must contain ``customer_id`` and ``email``. Missing → 422.
    * Body may contain extra fields; they are stored verbatim.
    * 5-15% of requests return 429/503 (configurable).
    """
    _inject_latency()
    _maybe_fail()

    body = await request.json()

    if not idempotency_key:
        raise HTTPException(status_code=422, detail="missing Idempotency-Key header")
    if "customer_id" not in body or "email" not in body:
        raise HTTPException(status_code=422, detail="customer_id and email are required")

    # --- idempotency short-circuit ---
    if idempotency_key in _by_key:
        record_id = _by_key[idempotency_key]
        return JSONResponse(
            status_code=200,
            content={
                "customer_id": body["customer_id"],
                "status": "duplicate",
                "crm_record_id": record_id,
                "received_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            },
        )

    # --- mutate ---
    is_update = any(r.get("customer_id") == body["customer_id"] for r in _by_record.values())
    record_id = _next_id()
    _by_record[record_id] = {
        "crm_record_id": record_id,
        "customer_id": body["customer_id"],
        "email": body["email"],
        "name": body.get("name"),
        "phone": body.get("phone"),
        "company": body.get("company"),
        "address": body.get("address"),
        "notes": body.get("notes", ""),
        "received_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "idempotency_key": idempotency_key,
        "internal_uuid": str(uuid.uuid4()),
    }
    _by_key[idempotency_key] = record_id

    return JSONResponse(
        status_code=201 if not is_update else 200,
        content={
            "customer_id": body["customer_id"],
            "status": "updated" if is_update else "created",
            "crm_record_id": record_id,
            "received_at": _by_record[record_id]["received_at"],
        },
    )


# --- entry point for `mock-crm` console script ----------------------------


def main() -> None:
    """Run the server. Used by the ``mock-crm`` console script."""
    import uvicorn

    uvicorn.run(
        "mock_crm.server:app",
        host=os.environ.get("CRM_HOST", "127.0.0.1"),
        port=int(os.environ.get("CRM_PORT", "8765")),
        reload=False,
    )


if __name__ == "__main__":  # pragma: no cover
    main()
