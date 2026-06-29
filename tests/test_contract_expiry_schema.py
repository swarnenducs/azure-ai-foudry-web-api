import pytest

from src.schemas.fabric.contract_expiry import ContractExpiryAgentResponse
from src.schemas.fabric.loader import resolve_response_class


def test_contract_expiry_response_class_resolves() -> None:
    model = resolve_response_class("ContractExpiryAgentResponse")
    assert model is ContractExpiryAgentResponse


def test_contract_expiry_parses_expected_json() -> None:
    payload = {
        "answer": "12 contracts expire next quarter.",
        "total_contract_expiring_next_quarter": 12,
        "agreements": [
            {
                "agreement_num": "AGR-1001",
                "agreement_description": "Office lease renewal",
            }
        ],
    }
    parsed = ContractExpiryAgentResponse.model_validate(payload)
    assert parsed.total_contract_expiring_next_quarter == 12
    assert parsed.agreements[0].agreement_num == "AGR-1001"


def test_contract_expiry_accepts_fabric_typos() -> None:
    payload = {
        "answer": "Summary",
        "total_contract_expiring_next_quater": 3,
        "agrrements": [
            {
                "aggrement_num": "AGR-9",
                "aggrement_description": "Vendor contract",
            }
        ],
    }
    parsed = ContractExpiryAgentResponse.model_validate(payload)
    assert parsed.total_contract_expiring_next_quarter == 3
    assert parsed.agreements[0].agreement_num == "AGR-9"
