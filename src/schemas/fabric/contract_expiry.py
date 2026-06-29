from pydantic import AliasChoices, BaseModel, ConfigDict, Field

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
        ),
        description="Count of contracts expiring in the next quarter",
    )
    agreements: list[ContractAgreement] = Field(
        default_factory=list,
        validation_alias=AliasChoices("agreements", "agrrements"),
        description="Contracts expiring in the next quarter",
    )
