"""Schema validation + idempotency-key derivation."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from agentic_onboard.schemas import CRMUpsertRequest, ParsedCustomer


def _valid_parsed(**overrides: object) -> ParsedCustomer:
    base = {
        "source_id": "fixture/01.eml",
        "customer_id": "cust-1",
        "name": "Aditi Sharma",
        "email": "aditi@example.com",
        "confidence": 0.95,
    }
    base.update(overrides)
    return ParsedCustomer.model_validate(base)


class TestParsedCustomer:
    def test_minimal_valid_record(self) -> None:
        c = _valid_parsed()
        assert c.email == "aditi@example.com"
        assert c.phone is None

    def test_invalid_email_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _valid_parsed(email="not-an-email")

    def test_confidence_must_be_in_range(self) -> None:
        with pytest.raises(ValidationError):
            _valid_parsed(confidence=1.5)
        with pytest.raises(ValidationError):
            _valid_parsed(confidence=-0.1)

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("+91 98100 12345", "+919810012345"),
            ("(080) 4123-7700", "8041237700"),  # Indian STD prefix dropped
            ("022-6611-9988", "2266119988"),
            ("+1.415.555.0119", "+14155550119"),
            ("00 44 20 7946 0958", "442079460958"),  # international 00 prefix
        ],
    )
    def test_phone_normalisation(self, raw: str, expected: str) -> None:
        c = _valid_parsed(phone=raw)
        assert c.phone == expected

    def test_phone_blank_becomes_none(self) -> None:
        c = _valid_parsed(phone="")
        assert c.phone is None


class TestCRMUpsertRequest:
    def test_dedup_key_is_deterministic(self) -> None:
        a = CRMUpsertRequest.from_parsed(_valid_parsed())
        b = CRMUpsertRequest.from_parsed(_valid_parsed())
        assert a.dedup_key == b.dedup_key
        assert len(a.dedup_key) == 64  # sha256 hex

    def test_dedup_key_changes_when_payload_changes(self) -> None:
        a = CRMUpsertRequest.from_parsed(_valid_parsed(name="Aditi"))
        b = CRMUpsertRequest.from_parsed(_valid_parsed(name="Aditya"))
        assert a.dedup_key != b.dedup_key

    def test_dedup_key_stable_across_optional_fields(self) -> None:
        a = CRMUpsertRequest.from_parsed(_valid_parsed(phone=None))
        b = CRMUpsertRequest.from_parsed(_valid_parsed(phone=""))
        # Both empty-equivalent → same key.
        assert a.dedup_key == b.dedup_key

    @given(
        name=st.text(min_size=1, max_size=50).filter(lambda s: s.strip() and len(s.strip()) <= 50)
    )
    def test_property_dedup_key_is_64_hex_chars(self, name: str) -> None:
        c = _valid_parsed(name=name)
        req = CRMUpsertRequest.from_parsed(c)
        assert len(req.dedup_key) == 64
        assert all(ch in "0123456789abcdef" for ch in req.dedup_key)
