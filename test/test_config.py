"""Tests for the configuration loader."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.config import AppConfig, load_config


@pytest.fixture()
def config_file(tmp_path: Path) -> Path:
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "scraper:\n"
        "  headless: false\n"
        "  timeout_ms: 5000\n"
        "output:\n"
        "  base_dir: /tmp/gdd\n"
        "analysis:\n"
        "  llm_enabled: true\n"
        "  llm_model: gpt-4o\n"
        "feishu:\n"
        "  enabled: true\n"
        "  mode: both\n",
        encoding="utf-8",
    )
    return cfg


class TestLoadConfig:
    def test_defaults(self, tmp_path: Path) -> None:
        cfg = load_config(tmp_path / "nonexistent.yaml")
        assert cfg.scraper.headless is True
        assert cfg.scraper.timeout_ms == 30000
        assert cfg.output.base_dir == "output/guangdada"
        assert cfg.analysis.llm_enabled is False
        assert cfg.feishu.enabled is False

    def test_from_file(self, config_file: Path) -> None:
        cfg = load_config(config_file)
        assert cfg.scraper.headless is False
        assert cfg.scraper.timeout_ms == 5000
        assert cfg.output.base_dir == "/tmp/gdd"
        assert cfg.analysis.llm_enabled is True
        assert cfg.analysis.llm_model == "gpt-4o"
        assert cfg.feishu.enabled is True
        assert cfg.feishu.mode == "both"

    def test_env_override(self, config_file: Path, monkeypatch) -> None:
        monkeypatch.setenv("GDD_HEADLESS", "true")
        monkeypatch.setenv("GDD_OUTPUT_DIR", "/override/dir")
        monkeypatch.setenv("GDD_LLM_ENABLED", "false")
        cfg = load_config(config_file)
        assert cfg.scraper.headless is True
        assert cfg.output.base_dir == "/override/dir"
        assert cfg.analysis.llm_enabled is False

    def test_env_bool_variants(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("GDD_HEADLESS", "yes")
        cfg = load_config(tmp_path / "nope.yaml")
        assert cfg.scraper.headless is True

        monkeypatch.setenv("GDD_HEADLESS", "0")
        cfg = load_config(tmp_path / "nope.yaml")
        assert cfg.scraper.headless is False
