import logging
import os
from typing import Any, Literal

from src.config import Settings

logger = logging.getLogger(__name__)

CredentialMode = Literal["default", "managed"]


def resolve_credential_mode(settings: Settings) -> CredentialMode:
    """Choose DefaultAzureCredential (local) vs ManagedIdentityCredential (Azure)."""
    explicit = os.getenv("AZURE_CREDENTIAL_MODE", "auto").strip().lower()
    if explicit in {"default", "defaultazurecredential", "dac"}:
        return "default"
    if explicit in {"managed", "managedidentity", "mi"}:
        return "managed"

    if settings.is_production or os.getenv("WEBSITE_SITE_NAME"):
        return "managed"
    return "default"


def describe_credential_choice(settings: Settings) -> dict[str, Any]:
    mode = resolve_credential_mode(settings)
    return {
        "credential": (
            "DefaultAzureCredential" if mode == "default" else "ManagedIdentityCredential"
        ),
        "azure_credential_mode": os.getenv("AZURE_CREDENTIAL_MODE", "auto"),
        "environment": settings.environment,
        "is_production": settings.is_production,
        "website_site_name": os.getenv("WEBSITE_SITE_NAME"),
        "azure_client_id_set": bool(os.getenv("AZURE_CLIENT_ID")),
    }


def build_async_credential(settings: Settings):
    mode = resolve_credential_mode(settings)
    details = describe_credential_choice(settings)
    logger.info("Azure async credential selected", extra=details)

    if mode == "managed":
        from azure.identity.aio import ManagedIdentityCredential

        client_id = os.getenv("AZURE_CLIENT_ID")
        if client_id:
            return ManagedIdentityCredential(client_id=client_id)
        return ManagedIdentityCredential()

    from azure.identity.aio import DefaultAzureCredential

    return DefaultAzureCredential()


def build_sync_credential(settings: Settings):
    mode = resolve_credential_mode(settings)
    details = describe_credential_choice(settings)
    logger.info("Azure sync credential selected", extra=details)

    if mode == "managed":
        from azure.identity import ManagedIdentityCredential

        client_id = os.getenv("AZURE_CLIENT_ID")
        if client_id:
            return ManagedIdentityCredential(client_id=client_id)
        return ManagedIdentityCredential()

    from azure.identity import DefaultAzureCredential

    return DefaultAzureCredential()
