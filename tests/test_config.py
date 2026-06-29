import os
from pathlib import Path

import pytest

from src.config import (
    project_root,
    resolve_dotenv_path,
    resolve_project_path,
    should_load_dotenv,
)


def test_project_root_points_at_repo_root() -> None:
    root = project_root()
    assert (root / "pyproject.toml").is_file()
    assert (root / "src" / "config.py").is_file()


def test_resolve_project_path_from_relative() -> None:
    resolved = resolve_project_path("config/agent_registry.yaml")
    assert Path(resolved).is_file()


def test_should_load_dotenv_locally_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LOAD_DOTENV", raising=False)
    monkeypatch.delenv("WEBSITE_SITE_NAME", raising=False)
    assert should_load_dotenv() is True


def test_should_not_load_dotenv_on_azure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WEBSITE_SITE_NAME", "my-web-app")
    assert should_load_dotenv() is False


def test_load_dotenv_can_be_forced_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WEBSITE_SITE_NAME", raising=False)
    monkeypatch.setenv("LOAD_DOTENV", "false")
    assert should_load_dotenv() is False


def test_resolve_dotenv_path_skips_on_azure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WEBSITE_SITE_NAME", "my-web-app")
    assert resolve_dotenv_path() is None
