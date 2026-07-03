"""Tests for Fabric JSON sanitization (e.g. // comments in truncated replies)."""

from src.services.fabric_response_formatter import _extract_json_object


def test_extract_json_strips_line_comments() -> None:
    raw = """{
  "total_contracts_expiring_next_quarter": 150,
  "agreements": [
    {"agreement_num": "A1", "agreement_description": "Desc 1"}
    // ...additional records omitted
  ]
}
File(s) result_0.json were generated."""
    payload = _extract_json_object(raw)
    assert payload is not None
    assert payload["total_contracts_expiring_next_quarter"] == 150
    assert payload["agreements"][0]["agreement_num"] == "A1"
