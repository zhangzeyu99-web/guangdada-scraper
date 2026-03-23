"""Configuration loader for guangdada-scraper.

Reads from ``config.yaml`` with ``GDD_`` environment-variable overrides,
following the same pattern used by heartbeat-manager.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


_ENV_PREFIX = "GDD_"

_DEFAULT_CONFIG_PATHS = [
    Path("config.yaml"),
    Path("config.yml"),
    Path(os.path.expanduser("~/.config/guangdada-scraper/config.yaml")),
]


@dataclass
class ScraperConfig:
    headless: bool = True
    timeout_ms: int = 30000
    cookie_reuse: bool = True
    user_agent: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScraperConfig:
        return cls(
            headless=bool(data.get("headless", True)),
            timeout_ms=int(data.get("timeout_ms", 30000)),
            cookie_reuse=bool(data.get("cookie_reuse", True)),
            user_agent=str(data.get("user_agent", "")),
        )


@dataclass
class OutputConfig:
    base_dir: str = "output/guangdada"
    image_format: str = "original"
    report_format: str = "md"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OutputConfig:
        return cls(
            base_dir=str(data.get("base_dir", "output/guangdada")),
            image_format=str(data.get("image_format", "original")),
            report_format=str(data.get("report_format", "md")),
        )


@dataclass
class AnalysisConfig:
    basic_enabled: bool = True
    llm_enabled: bool = False
    llm_model: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AnalysisConfig:
        return cls(
            basic_enabled=bool(data.get("basic_enabled", True)),
            llm_enabled=bool(data.get("llm_enabled", False)),
            llm_model=str(data.get("llm_model", "")),
        )


@dataclass
class FeishuConfig:
    enabled: bool = False
    mode: str = "notify"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FeishuConfig:
        return cls(
            enabled=bool(data.get("enabled", False)),
            mode=str(data.get("mode", "notify")),
        )


@dataclass
class AppConfig:
    scraper: ScraperConfig = field(default_factory=ScraperConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    feishu: FeishuConfig = field(default_factory=FeishuConfig)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AppConfig:
        return cls(
            scraper=ScraperConfig.from_dict(data.get("scraper", {})),
            output=OutputConfig.from_dict(data.get("output", {})),
            analysis=AnalysisConfig.from_dict(data.get("analysis", {})),
            feishu=FeishuConfig.from_dict(data.get("feishu", {})),
        )


def _apply_env_overrides(cfg: AppConfig) -> None:
    """Override config values with ``GDD_*`` environment variables."""
    env_map: dict[str, tuple[Any, str, type]] = {
        "HEADLESS": (cfg.scraper, "headless", bool),
        "TIMEOUT_MS": (cfg.scraper, "timeout_ms", int),
        "COOKIE_REUSE": (cfg.scraper, "cookie_reuse", bool),
        "USER_AGENT": (cfg.scraper, "user_agent", str),
        "OUTPUT_DIR": (cfg.output, "base_dir", str),
        "IMAGE_FORMAT": (cfg.output, "image_format", str),
        "LLM_ENABLED": (cfg.analysis, "llm_enabled", bool),
        "LLM_MODEL": (cfg.analysis, "llm_model", str),
        "FEISHU_ENABLED": (cfg.feishu, "enabled", bool),
        "FEISHU_MODE": (cfg.feishu, "mode", str),
    }
    for suffix, (obj, attr, cast) in env_map.items():
        value = os.environ.get(f"{_ENV_PREFIX}{suffix}")
        if value is not None:
            if cast is bool:
                setattr(obj, attr, value.lower() in ("1", "true", "yes"))
            else:
                setattr(obj, attr, cast(value))


def load_config(config_path: str | Path | None = None) -> AppConfig:
    """Load configuration from YAML file with env-var overrides.

    Resolution order:
    1. Explicit *config_path* argument
    2. ``GDD_CONFIG`` environment variable
    3. Default search paths
    """
    path: Path | None = None

    if config_path:
        path = Path(config_path)
    elif os.environ.get(f"{_ENV_PREFIX}CONFIG"):
        path = Path(os.environ[f"{_ENV_PREFIX}CONFIG"])
    else:
        for candidate in _DEFAULT_CONFIG_PATHS:
            if candidate.exists():
                path = candidate
                break

    raw: dict[str, Any] = {}
    if path and path.exists():
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}

    cfg = AppConfig.from_dict(raw)
    _apply_env_overrides(cfg)
    return cfg
