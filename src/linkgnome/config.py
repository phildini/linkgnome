"""Configuration management for LinkGnome."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "linkgnome"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.toml"
DEFAULT_PERIOD_HOURS = 24
DEFAULT_PAGE_SIZE = 42


class MastodonConfig(BaseModel):
    """Mastodon configuration."""

    enabled: bool = False
    instance_url: str = ""
    client_id: str = ""
    client_secret: str = ""
    access_token: str = ""


class BlueskyConfig(BaseModel):
    """Bluesky configuration."""

    enabled: bool = False
    handle: str = ""
    app_password: str = ""


class LinkgnomeSettings(BaseSettings):
    """Main settings for LinkGnome."""

    model_config = SettingsConfigDict(
        env_prefix="LINKGNOME_",
        env_file=".env",
    )

    mastodon: MastodonConfig = Field(default_factory=MastodonConfig)
    bluesky: BlueskyConfig = Field(default_factory=BlueskyConfig)
    period_hours: int = DEFAULT_PERIOD_HOURS
    page_size: int = DEFAULT_PAGE_SIZE
    cache_ttl_seconds: int = 600

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            file_secret_settings,
            env_settings,
            dotenv_settings,
        )


class ConfigManager:
    """Manages loading and saving configuration."""

    def __init__(self, config_path: Path | None = None):
        self.config_path = config_path or DEFAULT_CONFIG_FILE
        self._settings: LinkgnomeSettings | None = None

    def load(self) -> LinkgnomeSettings:
        """Load settings from config file."""
        if self._settings is not None:
            return self._settings

        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        if not self.config_path.exists():
            self._settings = LinkgnomeSettings()
            return self._settings

        class TomlSettings(LinkgnomeSettings):
            model_config = SettingsConfigDict(
                env_prefix="LINKGNOME_",
                env_file=".env",
            )

            @classmethod
            def settings_customise_sources(
                cls,
                settings_cls: type[BaseSettings],
                init_settings: PydanticBaseSettingsSource,
                env_settings: PydanticBaseSettingsSource,
                dotenv_settings: PydanticBaseSettingsSource,
                file_secret_settings: PydanticBaseSettingsSource,
            ) -> tuple[PydanticBaseSettingsSource, ...]:
                return (
                    TomlConfigSettingsSource(settings_cls, cls.config_path),
                    env_settings,
                    dotenv_settings,
                )

            @property
            def config_path(self) -> Path:
                return Path(_get_toml_path())

        try:
            toml_data = _parse_toml_file(self.config_path)
            self._settings = LinkgnomeSettings(**toml_data)
        except Exception:
            self._settings = LinkgnomeSettings()

        return self._settings

    def save(self, settings: LinkgnomeSettings) -> None:
        """Save settings to config file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        data = settings.model_dump(mode="json")
        toml_content = _dict_to_toml(data)
        self.config_path.write_text(toml_content)
        self._settings = settings

    def get(self) -> LinkgnomeSettings:
        """Get current settings, loading if necessary."""
        if self._settings is None:
            self.load()
        return self._settings


def _get_toml_path() -> str:
    return str(DEFAULT_CONFIG_FILE)


def _parse_toml_file(path: Path) -> dict[str, Any]:
    """Parse a TOML file manually (minimal implementation)."""
    import tomllib

    with open(path, "rb") as f:
        return tomllib.load(f)


def _dict_to_toml(data: dict[str, Any], indent: int = 0) -> str:
    """Convert a dict to TOML string."""
    lines = []
    prefix = "    " * indent

    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}[{key}]")
            lines.append(_dict_to_toml(value, indent))
            lines.append("")
        elif isinstance(value, bool):
            lines.append(f"{prefix}{key} = {str(value).lower()}")
        elif isinstance(value, int):
            lines.append(f"{prefix}{key} = {value}")
        elif isinstance(value, str):
            escaped = value.replace('"', '\\"')
            lines.append(f'{prefix}{key} = "{escaped}"')
        else:
            lines.append(f"{prefix}{key} = {value!r}")

    return "\n".join(lines)
