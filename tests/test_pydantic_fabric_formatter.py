import pytest

from src.config import Settings
from src.schemas.fabric.contract_expiry import ContractExpiryAgentResponse
from src.services.fabric_response_formatter import (
    FabricResponseProcessor,
    build_fabric_response_formatter,
)


@pytest.mark.asyncio
async def test_fabric_json_validator_preserves_fabric_data() -> None:
    formatter = FabricResponseProcessor(Settings())
    raw = (
        '{"total_contracts_expiring_next_quarter": 56, "agreements": ['
        '{"agreement_num": "AGRMNT001", "agreement_description": "Product Support Renewal"}'
        ']}\nFile(s) result_0.json were generated.'
    )

    result = await formatter.format(
        raw_reply=raw,
        response_class=ContractExpiryAgentResponse,
        agent_id="contract_expiry_p15",
    )

    assert result.extracted_json["total_contracts_expiring_next_quarter"] == 56
    assert result.structured.total_contract_expiring_next_quarter == 56
    assert result.data_source == "fabric_json"
    assert result.structured.agreements[0].agreement_num == "AGRMNT001"


def test_build_fabric_response_formatter_uses_processor() -> None:
    formatter = build_fabric_response_formatter(Settings())
    assert isinstance(formatter, FabricResponseProcessor)


@pytest.mark.asyncio
async def test_empty_json_returns_default() -> None:
    formatter = FabricResponseProcessor(Settings())
    result = await formatter.format(
        raw_reply="{}",
        response_class=ContractExpiryAgentResponse,
        agent_id="contract_expiry_p15",
    )
    assert result.data_source == "fabric_default"
    assert result.structured.total_contract_expiring_next_quarter == 0
