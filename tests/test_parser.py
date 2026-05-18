"""MockParser behaviour. The OpenRouterParser is exercised by integration tests."""

from __future__ import annotations

import pytest

from agentic_onboard.parser import MockParser, ParseError
from agentic_onboard.schemas import DocumentFormat, RawDocument


def _doc(body: str, fmt: DocumentFormat = DocumentFormat.FREEFORM_TEXT) -> RawDocument:
    return RawDocument(source_id="t/1.txt", format=fmt, body=body)


class TestMockParser:
    def test_extracts_from_email_thread(self) -> None:
        body = (
            "From: Aditi Sharma <aditi.sharma@northwind-corp.example>\n"
            "Subject: hello\n\n"
            "Name: Aditi Sharma\n"
            "Company: Northwind Logistics\n"
            "Phone: +91 98100 12345\n"
        )
        parsed = MockParser().parse(_doc(body, DocumentFormat.EMAIL))
        assert parsed.email == "aditi.sharma@northwind-corp.example"
        assert parsed.name == "Aditi Sharma"
        assert parsed.company == "Northwind Logistics"
        assert parsed.phone == "+919810012345"
        assert parsed.confidence >= 0.85

    def test_extracts_from_json(self) -> None:
        body = (
            '{"id": "ACME-1", "customer_name": "Vikram", '
            '"email_address": "v@a.example", "tel": "(080) 4123-7700"}'
        )
        parsed = MockParser().parse(_doc(body, DocumentFormat.JSON_BLOB))
        assert parsed.customer_id == "ACME-1"
        assert parsed.name == "Vikram"
        assert parsed.email == "v@a.example"
        # (080) is the Indian STD prefix → leading-zero strip leaves 8041237700
        assert parsed.phone == "8041237700"

    def test_falls_back_to_email_local_part_for_name(self) -> None:
        body = "send onboarding details to john.doe@example.com please"
        parsed = MockParser().parse(_doc(body))
        assert parsed.name == "John Doe"

    def test_no_email_raises(self) -> None:
        with pytest.raises(ParseError, match="no email"):
            MockParser().parse(_doc("just a message with no contact"))

    def test_invalid_email_routes_to_parse_error(self) -> None:
        body = "name: Jay\nemail: jay@example"  # incomplete TLD
        with pytest.raises(ParseError):
            MockParser().parse(_doc(body))

    def test_lower_confidence_when_no_company_or_address(self) -> None:
        body = "name: bob\nemail: bob@example.com"
        parsed = MockParser().parse(_doc(body))
        assert parsed.confidence == 0.85

    def test_higher_confidence_when_address_present(self) -> None:
        body = "name: bob\nemail: bob@example.com\naddress: 1 Main St"
        parsed = MockParser().parse(_doc(body))
        assert parsed.confidence == 0.92

    def test_json_with_nested_fields_works(self) -> None:
        body = (
            '{"customer_id":"X","email":"x@y.example","name":"X Y","_meta":{"source":"crm-export"}}'
        )
        parsed = MockParser().parse(_doc(body, DocumentFormat.JSON_BLOB))
        assert parsed.customer_id == "X"
