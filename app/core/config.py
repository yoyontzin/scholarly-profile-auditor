"""Carga de configuración: .env + config.yaml + snii_reference_params.yaml."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class EnvSettings(BaseSettings):
    """Variables de entorno. Prefijo SPA_."""

    user_email: str = Field(default="anonymous@example.org", alias="SPA_USER_EMAIL")
    output_dir: Path = Field(default=Path("./out"), alias="SPA_OUTPUT_DIR")
    db_path: Path = Field(default=Path("./data/spa.duckdb"), alias="SPA_DB_PATH")
    log_level: str = Field(default="INFO", alias="SPA_LOG_LEVEL")
    enable_scholar: bool = Field(default=True, alias="SPA_ENABLE_SCHOLAR")
    http_timeout: int = Field(default=20, alias="SPA_HTTP_TIMEOUT")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data


class AppConfig:
    """Configuración compuesta y materializada para todo el pipeline."""

    def __init__(
        self,
        env: EnvSettings | None = None,
        config_path: Path | None = None,
        snii_path: Path | None = None,
    ) -> None:
        self.env = env or EnvSettings()
        cfg_root = Path(__file__).resolve().parents[2] / "config"
        self.config_path = config_path or cfg_root / "config.yaml"
        self.snii_path = snii_path or cfg_root / "snii_reference_params.yaml"
        self.config: dict[str, Any] = _load_yaml(self.config_path)
        self.snii_params: dict[str, Any] = _load_yaml(self.snii_path)

    # Helpers de acceso seguro (no fail-loud por keys ausentes)
    def http(self) -> dict[str, Any]:
        return dict(self.config.get("http", {}))

    def rate_limits(self) -> dict[str, float]:
        return dict(self.config.get("rate_limits", {}))

    def scoring_weights(self) -> dict[str, float]:
        return dict(self.config.get("scoring", {}).get("weights", {}))

    def scoring_thresholds(self) -> dict[str, float]:
        s = self.config.get("scoring", {})
        return {
            "confirm_threshold": float(s.get("confirm_threshold", 0.65)),
            "ambiguous_threshold": float(s.get("ambiguous_threshold", 0.40)),
            "require_stable_id_for_confirm": bool(
                s.get("require_stable_id_for_confirm", True)
            ),
        }

    def dedupe_params(self) -> dict[str, Any]:
        return dict(self.config.get("dedupe", {}))

    def scholar_enabled(self) -> bool:
        return self.env.enable_scholar and bool(
            self.config.get("scholar", {}).get("enabled", True)
        )


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    """Singleton perezoso. Tests pueden invalidar con get_config.cache_clear()."""
    return AppConfig()
