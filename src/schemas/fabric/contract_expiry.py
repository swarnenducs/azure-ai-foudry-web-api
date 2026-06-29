from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

from src.schemas.fabric.base import FabricAgentResponseBase


class ContractAgreement(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    agreement_num: str = Field(
        ...,
        validation_alias=AliasChoices("agreement_num", "aggrement_num"),
        description="Agreement or contract number",
    )
    agreement_description: str = Field(
        ...,
        validation_alias=AliasChoices(
            "agreement_description",
            "aggrement_description",
        ),
        description="Short description of the agreement",
    )


class ContractExpiryAgentResponse(FabricAgentResponseBase):
    total_contract_expiring_next_quarter: int = Field(
        ...,
        validation_alias=AliasChoices(
            "total_contract_expiring_next_quarter",
            "total_contract_expiring_next_quater",
            "total_contracts_expiring_next_quarter",
            "total_contracts_expiring_next_quater",
        ),
        description="Count of contracts expiring in the next quarter",
    )
    agreements: list[ContractAgreement] = Field(
        default_factory=list,
        validation_alias=AliasChoices("agreements", "agrrements"),
        description="Contracts expiring in the next quarter",
    )

    @model_validator(mode="before")
    @classmethod
    def _default_answer_from_count(cls, data: object) -> object:
        if not isinstance(data, dict) or "answer" in data:
            return data
        payload = dict(data)
        count = (
            payload.get("total_contracts_expiring_next_quarter")
            or payload.get("total_contract_expiring_next_quarter")
            or payload.get("total_contract_expiring_next_quater")
            or payload.get("total_contracts_expiring_next_quater")
        )
        if count is None and isinstance(payload.get("agreements"), list):
            count = len(payload["agreements"])
        if count is not None:
            payload["answer"] = f"{count} contracts expire next quarter."
        else:
            payload["answer"] = "Contract expiry summary from Fabric."
        return payload
