"""Tests for the configuration management."""

import tempfile
from pathlib import Path
from linkgnome.config import ConfigManager, LinkgnomeSettings


class TestConfigManager:
    """Tests for the ConfigManager class."""

    def test_load_default_config(self):
        """Test loading creates defaults when no config file exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            manager = ConfigManager(config_path=config_path)
            settings = manager.load()

            assert settings.mastodon.enabled is False
            assert settings.bluesky.enabled is False
            assert settings.period_hours == 24
            assert settings.page_size == 42

    def test_save_and_load_config(self):
        """Test saving and loading a configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            manager = ConfigManager(config_path=config_path)

            settings = LinkgnomeSettings()
            settings.mastodon.enabled = True
            settings.mastodon.instance_url = "https://mastodon.social"
            settings.period_hours = 48

            manager.save(settings)

            loaded = manager.load()
            assert loaded.mastodon.enabled is True
            assert loaded.mastodon.instance_url == "https://mastodon.social"
            assert loaded.period_hours == 48

    def test_config_file_created(self):
        """Test that saving creates the config file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "subdir" / "config.toml"
            manager = ConfigManager(config_path=config_path)

            settings = LinkgnomeSettings()
            manager.save(settings)

            assert config_path.exists()

    def test_parse_period_hours(self):
        """Test parsing period strings."""
        from linkgnome.setup import _parse_period_hours

        assert _parse_period_hours("24h") == 24
        assert _parse_period_hours("7d") == 168
        assert _parse_period_hours("48") == 48
        assert _parse_period_hours("1h") == 1

    def test_extract_domain(self):
        """Test domain extraction from URLs."""
        from linkgnome.setup import _extract_domain

        assert _extract_domain("https://mastodon.social") == "mastodon.social"
        assert _extract_domain("http://example.com/path") == "example.com"
        assert _extract_domain("") == ""
        assert _extract_domain("mastodon.social") == "mastodon.social"

    def test_dict_to_toml(self):
        """Test dictionary to TOML conversion."""
        from linkgnome.config import _dict_to_toml

        data = {
            "mastodon": {
                "enabled": True,
                "instance_url": "https://example.com",
            },
            "period_hours": 24,
        }
        toml_str = _dict_to_toml(data)

        assert "[mastodon]" in toml_str
        assert "enabled = true" in toml_str
        assert 'instance_url = "https://example.com"' in toml_str
        assert "period_hours = 24" in toml_str
