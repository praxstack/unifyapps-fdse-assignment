"""Pydantic models that flow through the pipeline.

Type contract:

    RawDocument (raw bytes/text from "S3")
        │
        ▼
    ParsedCustomer (LLM output, validated)
        │
        ▼
    CRMUpsertRequest (mapper output, with idempotency key)
        │
        ▼
    CRMUpsertResponse (CRM result)

All models are :class:`pydantic.BaseModel` v2. Validators are intentionally
*strict*: an invalid email is treated as a parse failure (routes to human
review queue), not silently coerced. The pipeline relies on this strictness —
a malformed record that gets through here would crash the CRM client without
landing in the DLQ.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator

# --- Primitives ---

# Phone numbers are E.164-ish: optional leading +, 7-15 digits. Real-world data is
# messy (spaces, dashes, parens) so the validator on `ParsedCustomer.phone`
# normalizes before this constraint is checked.
PhoneStr = Annotated[
    str,
    StringConstraints(strip_whitespace=True, pattern=r"^\+?[1-9]\d{6,14}$"),
]

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


# --- Enums ---


class DocumentFormat(StrEnum):
    """Source format of a raw document. Drives the LLM prompt's example block."""

    EMAIL = "email"
    CSV_ROW = "csv_row"
    JSON_BLOB = "json_blob"
    SCANNED_OCR = "scanned_ocr"
    FREEFORM_TEXT = "freeform_text"


class RecordStatus(StrEnum):
    """Terminal status assigned by the orchestrator. Persisted to the audit log."""

    SUCCESS = "success"
    DLQ = "dlq"
    HUMAN_REVIEW = "human_review"
    PARSE_FAILED = "parse_failed"


# --- Models ---


class RawDocument(BaseModel):
    """A single object as ingested. Format-tagged so the parser can branch."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_id: NonEmptyStr = Field(description="Stable id; for S3 this is the object key.")
    format: DocumentFormat
    body: str = Field(description="Raw text payload. May be very messy — that is the point.")
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ParsedCustomer(BaseModel):
    """The LLM's structured output, validated.

    Confidence < 0.8 routes to ``human_review`` instead of the CRM.
    """

    model_config = ConfigDict(extra="forbid")

    source_id: NonEmptyStr
    customer_id: NonEmptyStr
    name: NonEmptyStr
    email: EmailStr
    phone: PhoneStr | None = None
    company: NonEmptyStr | None = None
    address: NonEmptyStr | None = None
    notes: str = ""
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Parser self-reported confidence; < 0.8 → human review.",
    )

    @field_validator("phone", mode="before")
    @classmethod
    def _normalize_phone(cls, v: str | None) -> str | None:
        """Strip spaces, dashes, parens, dots; collapse leading zeros.

        Real-world data ships ``(080) 4123-7700`` (Indian STD prefix), ``00 44
        20 …`` (international 00-prefix), or just ``+91-9876543210``. The
        E.164-ish regex on this field requires the leading digit be 1-9, so
        we drop any run of leading zeros (after stripping separators) so all
        three shapes parse.
        """
        if v is None or v == "":
            return None
        cleaned = "".join(ch for ch in str(v) if ch.isdigit() or ch == "+")
        if not cleaned:
            return None
        if cleaned.startswith("+"):
            return cleaned
        # Strip leading zeros (00-international or 0-trunk prefixes).
        stripped = cleaned.lstrip("0")
        return stripped or None


class CRMUpsertRequest(BaseModel):
    """Wire-level request body sent to the CRM.

    The ``dedup_key`` is the load-bearing piece for idempotency — a sha256 of
    customer_id plus the canonical-form payload. Replays produce the same key,
    and the CRM short-circuits to a 200 with ``status="duplicate"``.
    """

    model_config = ConfigDict(extra="forbid")

    customer_id: NonEmptyStr
    name: NonEmptyStr
    email: EmailStr
    phone: PhoneStr | None = None
    company: NonEmptyStr | None = None
    address: NonEmptyStr | None = None
    notes: str = ""
    dedup_key: NonEmptyStr = Field(description="sha256 over (customer_id || canonical payload).")

    @classmethod
    def from_parsed(cls, parsed: ParsedCustomer) -> CRMUpsertRequest:
        """Project a ``ParsedCustomer`` into the CRM payload, computing the dedup key."""
        canonical = (
            f"{parsed.customer_id}|{parsed.name}|{parsed.email}|"
            f"{parsed.phone or ''}|{parsed.company or ''}|"
            f"{parsed.address or ''}|{parsed.notes}"
        )
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return cls(
            customer_id=parsed.customer_id,
            name=parsed.name,
            email=parsed.email,
            phone=parsed.phone,
            company=parsed.company,
            address=parsed.address,
            notes=parsed.notes,
            dedup_key=digest,
        )


class CRMUpsertResponse(BaseModel):
    """Response envelope from the CRM. ``status`` is the actionable signal."""

    model_config = ConfigDict(extra="forbid")

    customer_id: NonEmptyStr
    status: NonEmptyStr  # "created" | "updated" | "duplicate"
    crm_record_id: NonEmptyStr
    received_at: datetime


class PipelineResult(BaseModel):
    """End-of-run summary returned by the orchestrator and printed by the CLI."""

    model_config = ConfigDict(extra="forbid")

    run_id: NonEmptyStr
    total: int
    succeeded: int
    duplicates: int
    human_review: int
    parse_failed: int
    dlq: int
    duration_ms: int
