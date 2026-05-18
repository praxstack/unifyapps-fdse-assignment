"""LLM parser: ``RawDocument`` → ``ParsedCustomer``.

Two implementations behind the same ``Parser`` Protocol:

* :class:`OpenRouterParser` — real LLM via OpenRouter (the OpenAI Python SDK
  is wire-compatible). Uses *structured outputs* so the LLM is forced to emit
  JSON that matches our Pydantic schema; we still re-validate with Pydantic
  on receipt because LLMs occasionally violate the schema (and a defensive
  re-validation costs nothing).
* :class:`MockParser` — deterministic regex over the document body. Zero API
  calls, zero key requirements; runs in CI for free, and lets a recruiter
  clone-and-run the repo without an LLM key.

The orchestrator picks one at startup based on ``settings.llm_provider``.
"""

from __future__ import annotations

import json
import re
from typing import Protocol

from pydantic import ValidationError

from .logging_config import get_logger
from .schemas import ParsedCustomer, RawDocument
from .settings import Settings

log = get_logger(__name__)


class ParseError(Exception):
    """Raised when the LLM output cannot be coerced into a valid ``ParsedCustomer``."""


class Parser(Protocol):
    """Contract: ``parse(doc) -> ParsedCustomer`` or raises ``ParseError``."""

    def parse(self, doc: RawDocument) -> ParsedCustomer: ...


# --- System prompt (real LLM) -----------------------------------------------

_SYSTEM_PROMPT = """\
You are a strict data extraction agent for a customer-onboarding pipeline.

Given a raw, possibly messy document, extract the customer record into the
schema you have been given. Rules:

1. Never invent data. If a field is not present in the document, return null.
2. ``customer_id`` must be a stable identifier you can derive from the document
   (an email address slugified, an internal CRM id if visible, or a hash of
   name+email). It does not need to look human-readable.
3. ``confidence`` is your self-reported certainty in the extraction:
     - 0.95+  perfectly clean structured input
     - 0.80   minor cleanup needed
     - <0.80  ambiguous, partial, or contradictory — the orchestrator will
              route this record to a human review queue.
4. Phone numbers are optional. Strip formatting; keep digits and an optional +.
5. Reply with the JSON object only — no commentary, no markdown fences.
"""

_USER_TEMPLATE = """\
SOURCE_ID: {source_id}
FORMAT: {format}
---
{body}
"""


# --- Real implementation ----------------------------------------------------


class OpenRouterParser:
    """Calls OpenRouter (OpenAI-compatible API) for structured extraction.

    The OpenAI SDK's ``client.beta.chat.completions.parse(... response_format=Model)``
    coerces the LLM output through our Pydantic schema server-side via the
    JSON Schema we ship with the request.
    """

    def __init__(self, settings: Settings):
        if settings.openrouter_api_key is None:
            raise RuntimeError("LLM_PROVIDER=openrouter requires OPENROUTER_API_KEY in the env")
        # Import here so that ``LLM_PROVIDER=mock`` runs do not require the openai SDK.
        from openai import OpenAI

        self._client = OpenAI(
            base_url=settings.openrouter_base_url,
            api_key=settings.openrouter_api_key.get_secret_value(),
            # Tell OpenRouter who is asking — surfaces in their dashboard.
            default_headers={
                "HTTP-Referer": "https://github.com/praxstack/unifyapps-fdse-assignment",
                "X-Title": "agentic-onboard",
            },
        )
        self._model = settings.openrouter_model

    def parse(self, doc: RawDocument) -> ParsedCustomer:
        user = _USER_TEMPLATE.format(
            source_id=doc.source_id,
            format=doc.format.value,
            body=doc.body,
        )
        try:
            completion = self._client.beta.chat.completions.parse(
                model=self._model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user},
                ],
                response_format=ParsedCustomer,
                temperature=0.0,  # determinism for reproducible runs
                max_tokens=500,
            )
        except Exception as exc:  # network, 5xx, schema rejection
            log.warning("llm.error", source_id=doc.source_id, error=str(exc))
            raise ParseError(f"LLM request failed: {exc}") from exc

        parsed = completion.choices[0].message.parsed
        if parsed is None:
            raise ParseError("LLM returned no parsed object")
        # Force the source_id to match — even if the model invented one.
        return parsed.model_copy(update={"source_id": doc.source_id})


# --- Deterministic fallback (CI / no-key local) -----------------------------


_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# Match a sequence of digits + separators (parens, dashes, dots, spaces) then
# strip everything but digits and the optional leading + before yielding.
_PHONE_RE = re.compile(r"\+?[\d][\d\s().\-]{6,}\d")


def _normalize_phone(raw: str | None) -> str | None:
    """Drop separators so the schema's E.164-ish regex accepts the result."""
    if raw is None:
        return None
    cleaned = "".join(ch for ch in raw if ch.isdigit() or ch == "+")
    return cleaned or None


_NAME_RE = re.compile(r"(?:^|\b)(?:Name|Full Name|Customer)\s*[:=]\s*([^\n,;]+)", re.IGNORECASE)
_COMPANY_RE = re.compile(
    r"(?:^|\b)(?:Company|Org|Employer|Account)\s*[:=]\s*([^\n,;]+)", re.IGNORECASE
)
_ADDRESS_RE = re.compile(r"(?:^|\b)(?:Address|Addr)\s*[:=]\s*([^\n;]+)", re.IGNORECASE)
_NAME_FROM_EMAIL_RE = re.compile(r"From:\s*([^<\n]+)\s*<", re.IGNORECASE)


class MockParser:
    """Pure-Python regex parser. Used in CI and as the no-key fallback.

    Trades LLM intelligence for determinism: every input produces the same
    output every run, which makes test assertions exact and CI free.
    Confidence is heuristic — present required fields → 0.92, missing optional
    → 0.85, missing required → forced parse failure.
    """

    def parse(self, doc: RawDocument) -> ParsedCustomer:
        body = doc.body
        # Sniff JSON first — many "messy" inputs are actually JSON with bad keys.
        if doc.format.value == "json_blob" or body.lstrip().startswith("{"):
            try:
                obj = json.loads(body)
                return self._from_json(doc, obj)
            except (json.JSONDecodeError, ValidationError, ParseError):
                # Fall through to the regex path below.
                pass

        email_match = _EMAIL_RE.search(body)
        if email_match is None:
            raise ParseError("no email found in document")
        email = email_match.group(0)

        name = self._first_capture(_NAME_RE, body) or self._first_capture(_NAME_FROM_EMAIL_RE, body)
        if name is None:
            # Synthesise from the email local-part as a last resort.
            local = email.split("@", 1)[0]
            name = local.replace(".", " ").replace("_", " ").title()

        phone_match = _PHONE_RE.search(body)
        phone = phone_match.group(0) if phone_match else None
        company = self._first_capture(_COMPANY_RE, body)
        address = self._first_capture(_ADDRESS_RE, body)

        confidence = 0.92 if (company or address) else 0.85

        try:
            return ParsedCustomer(
                source_id=doc.source_id,
                customer_id=email,  # email is the natural stable id
                name=name.strip(),
                email=email,
                phone=phone,
                company=company,
                address=address,
                notes=f"format={doc.format.value}",
                confidence=confidence,
            )
        except ValidationError as exc:
            raise ParseError(f"schema validation failed: {exc.errors()[0]}") from exc

    # --- helpers ---

    @staticmethod
    def _first_capture(pat: re.Pattern[str], body: str) -> str | None:
        m = pat.search(body)
        if m is None:
            return None
        return m.group(1).strip() or None

    def _from_json(self, doc: RawDocument, obj: dict[str, object]) -> ParsedCustomer:
        # Accept a small grab-bag of common key spellings.
        def pick(*keys: str) -> str | None:
            for k in keys:
                v = obj.get(k)
                if isinstance(v, str) and v.strip():
                    return v.strip()
            return None

        email = pick("email", "Email", "EMAIL", "email_address", "mail")
        if email is None:
            raise ParseError("no email key in JSON document")
        name = pick("name", "full_name", "fullName", "customer_name") or email.split("@", 1)[0]

        try:
            return ParsedCustomer(
                source_id=doc.source_id,
                customer_id=str(obj.get("id") or obj.get("customer_id") or email),
                name=name,
                email=email,
                phone=pick("phone", "phone_number", "tel", "mobile"),
                company=pick("company", "org", "organization", "employer"),
                address=pick("address", "addr", "street_address"),
                notes=pick("notes", "comment") or f"format={doc.format.value}",
                confidence=0.95,
            )
        except ValidationError as exc:
            raise ParseError(f"JSON schema validation failed: {exc.errors()[0]}") from exc


# --- Factory ----------------------------------------------------------------


def build_parser(settings: Settings) -> Parser:
    """Return the parser selected by ``settings.llm_provider``."""
    if settings.llm_provider == "openrouter":
        return OpenRouterParser(settings)
    if settings.llm_provider == "mock":
        return MockParser()
    raise ValueError(f"unknown llm_provider: {settings.llm_provider!r}")
