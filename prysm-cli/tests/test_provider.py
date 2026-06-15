"""Tests for Phase 2 — Model Registry, Provider Registry, Credential Manager."""

import json
import os
from unittest.mock import MagicMock, patch
from pathlib import Path

import pytest

from prysm.models import ModelEntry, ModelRegistry, ProviderConfig, ProviderRegistry, CredentialManager
from prysm.models.provider import TIER_1_PROVIDERS, TIER_2_COMPATIBLE


# ═══════════════════════════════════════════════════════════════════════════════
# ModelEntry Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestModelEntry:
    """Tests for the ModelEntry Pydantic model."""

    def test_minimal_entry(self):
        """Minimal model entry with only required fields."""
        m = ModelEntry(id="test-model", name="Test Model")
        assert m.id == "test-model"
        assert m.name == "Test Model"
        assert m.provider == "local"
        assert m.context_length == 4096
        assert m.capabilities == ["chat"]

    def test_cloud_detection(self):
        """is_cloud should be True for non-local providers."""
        m = ModelEntry(id="openai/gpt-4o", name="GPT-4o", provider="openai")
        assert m.is_cloud is True
        assert m.is_local is False

    def test_local_detection(self):
        """is_local should be True for local provider."""
        m = ModelEntry(id="my-model", name="My Model", provider="local")
        assert m.is_local is True
        assert m.is_cloud is False

    def test_ollama_is_not_cloud(self):
        """Ollama models are not cloud models."""
        m = ModelEntry(id="ollama/llama3", name="Llama 3", provider="ollama")
        assert m.is_cloud is False

    def test_full_entry(self):
        """Model entry with all fields populated."""
        m = ModelEntry(
            id="deepseek/deepseek-chat",
            name="DeepSeek Chat",
            provider="deepseek",
            api_base="https://api.deepseek.com",
            model_name="deepseek-chat",
            context_length=65536,
            capabilities=["chat", "tools", "streaming"],
            default=True,
        )
        assert m.api_base == "https://api.deepseek.com"
        assert m.context_length == 65536
        assert m.default is True
        assert m.loaded is False

    def test_runtime_params(self):
        """Runtime params should be a dict."""
        m = ModelEntry(
            id="local/codellama",
            name="CodeLlama",
            provider="local",
            path="/models/codellama.gguf",
            runtime="llama-cpp",
            runtime_params={"n_gpu_layers": -1, "n_ctx": 4096},
        )
        assert m.runtime == "llama-cpp"
        assert m.runtime_params["n_gpu_layers"] == -1


# ═══════════════════════════════════════════════════════════════════════════════
# ModelRegistry Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestModelRegistry:
    """Tests for the ModelRegistry CRUD operations."""

    @pytest.fixture
    def registry(self, temp_dir):
        """Create a registry with a temp file path."""
        path = temp_dir / "models.json"
        return ModelRegistry(path=path)

    def test_empty_registry(self, registry):
        """Fresh registry should be empty."""
        assert registry.count() == 0
        assert registry.list_all() == []

    def test_add_model(self, registry):
        """Adding a model should increase count."""
        m = ModelEntry(id="test", name="Test Model")
        registry.add(m)
        assert registry.count() == 1

    def test_get_model(self, registry):
        """Getting a model should return it."""
        m = ModelEntry(id="test", name="Test Model")
        registry.add(m)
        retrieved = registry.get("test")
        assert retrieved is not None
        assert retrieved.name == "Test Model"

    def test_get_nonexistent(self, registry):
        """Getting a non-existent model should return None."""
        assert registry.get("nonexistent") is None

    def test_remove_model(self, registry):
        """Removing a model should decrease count."""
        m = ModelEntry(id="test", name="Test Model")
        registry.add(m)
        assert registry.remove("test") is True
        assert registry.count() == 0

    def test_remove_nonexistent(self, registry):
        """Removing a non-existent model should return False."""
        assert registry.remove("nonexistent") is False

    def test_list_by_provider(self, registry):
        """Listing by provider should filter correctly."""
        registry.add(ModelEntry(id="openai/gpt4", name="GPT-4", provider="openai"))
        registry.add(ModelEntry(id="openai/gpt4-mini", name="GPT-4 Mini", provider="openai"))
        registry.add(ModelEntry(id="anthropic/claude", name="Claude", provider="anthropic"))

        openai_models = registry.list_by_provider("openai")
        assert len(openai_models) == 2
        assert len(registry.list_by_provider("anthropic")) == 1

    def test_list_loaded(self, registry):
        """Listing loaded models should work."""
        registry.add(ModelEntry(id="m1", name="M1", loaded=True))
        registry.add(ModelEntry(id="m2", name="M2", loaded=False))
        assert len(registry.list_loaded()) == 1

    def test_set_default(self, registry):
        """Setting a default should clear others."""
        registry.add(ModelEntry(id="a", name="A"))
        registry.add(ModelEntry(id="b", name="B"))
        registry.set_default("b")

        assert registry.get("b").default is True
        assert registry.get("a").default is False

    def test_get_default(self, registry):
        """Getting default should return the right model."""
        registry.add(ModelEntry(id="a", name="A"))
        registry.add(ModelEntry(id="b", name="B", default=True))
        default = registry.get_default()
        assert default is not None
        assert default.id == "b"

    def test_get_default_none(self, registry):
        """Getting default when none set should return None."""
        assert registry.get_default() is None

    def test_update_model(self, registry):
        """Updating a model should change fields."""
        registry.add(ModelEntry(id="test", name="Test"))
        registry.update("test", name="Updated", context_length=8192)
        updated = registry.get("test")
        assert updated.name == "Updated"
        assert updated.context_length == 8192

    def test_update_nonexistent(self, registry):
        """Updating a non-existent model should return None."""
        assert registry.update("nonexistent", name="X") is None

    def test_mark_used(self, registry):
        """Marking a model as used should set last_used."""
        registry.add(ModelEntry(id="test", name="Test"))
        registry.mark_used("test")
        assert registry.get("test").last_used is not None

    def test_persistence(self, temp_dir):
        """Registry should persist to disk and reload."""
        path = temp_dir / "models.json"
        r1 = ModelRegistry(path=path)
        r1.add(ModelEntry(id="persist-test", name="Persistence Test"))
        r1.add(ModelEntry(id="another", name="Another"))

        # Create a new registry pointing to the same file
        r2 = ModelRegistry(path=path)
        assert r2.count() == 2
        assert r2.get("persist-test").name == "Persistence Test"

    def test_corrupted_file_handling(self, temp_dir):
        """A corrupted models.json should not crash."""
        path = temp_dir / "models.json"
        path.write_text("{corrupted json")
        registry = ModelRegistry(path=path)
        assert registry.count() == 0

    def test_empty_file_handling(self, temp_dir):
        """An empty models.json should not crash."""
        path = temp_dir / "models.json"
        path.write_text("")
        registry = ModelRegistry(path=path)
        assert registry.count() == 0


# ═══════════════════════════════════════════════════════════════════════════════
# ProviderConfig Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestProviderConfig:
    """Tests for ProviderConfig Pydantic model."""

    def test_default_config(self):
        """Default provider config should have sensible defaults."""
        cfg = ProviderConfig(provider_id="openai")
        assert cfg.enabled is True
        assert cfg.max_concurrency == 5
        assert cfg.timeout_seconds == 120

    def test_custom_config(self):
        """Custom provider config should override defaults."""
        cfg = ProviderConfig(
            provider_id="custom",
            api_base="https://custom.api.com/v1",
            rate_limit=10,
            proxy="http://proxy:8080",
        )
        assert cfg.api_base == "https://custom.api.com/v1"
        assert cfg.rate_limit == 10
        assert cfg.proxy == "http://proxy:8080"


# ═══════════════════════════════════════════════════════════════════════════════
# ProviderRegistry Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestProviderRegistry:
    """Tests for the static ProviderRegistry."""

    def test_known_providers_include_openai(self):
        """OpenAI should be a known provider."""
        assert ProviderRegistry.is_known("openai")

    def test_known_providers_include_anthropic(self):
        """Anthropic should be a known provider."""
        assert ProviderRegistry.is_known("anthropic")

    def test_known_providers_include_openrouter(self):
        """OpenRouter should be a known provider."""
        assert ProviderRegistry.is_known("openrouter")

    def test_unknown_provider(self):
        """Unknown provider should not be recognized."""
        assert ProviderRegistry.is_known("nonexistent") is False

    def test_get_provider_info(self):
        """Getting provider info should return metadata."""
        info = ProviderRegistry.get_provider_info("openai")
        assert info is not None
        assert info["name"] == "OpenAI"
        assert "gpt-4o" in info["models"]

    def test_get_provider_info_nonexistent(self):
        """Getting info for unknown provider should return None."""
        assert ProviderRegistry.get_provider_info("nonexistent") is None

    def test_tier_classification(self):
        """Providers should be classified into tiers."""
        assert ProviderRegistry.get_tier("openai") == "bundled"
        assert ProviderRegistry.get_tier("openrouter") == "compatible"
        assert ProviderRegistry.get_tier("nonexistent") is None

    def test_known_providers_count(self):
        """There should be at least some known providers."""
        providers = ProviderRegistry.get_known_providers()
        assert len(providers) >= 8  # 3 tier 1 + 5 tier 2


# ═══════════════════════════════════════════════════════════════════════════════
# CredentialManager Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestCredentialManager:
    """Tests for CredentialManager with mocked keyring."""

    @pytest.fixture
    def mgr(self, temp_dir):
        """Create a CredentialManager with a temp path and mocked keyring."""
        providers_path = temp_dir / "providers.json"
        return CredentialManager(providers_path=providers_path)

    def test_get_no_key(self, mgr):
        """Getting a key that doesn't exist should return None."""
        with patch.object(mgr, "_keyring_available", False):
            assert mgr.get("nonexistent") is None

    def test_set_and_get_via_file(self, mgr):
        """Setting and getting a key via file should work."""
        with patch.object(mgr, "_keyring_available", False):
            mgr.set("test_provider", "sk-test-key", storage="file")
            key = mgr.get("test_provider")
            assert key == "sk-test-key"

    def test_set_and_get_via_keyring(self, mgr):
        """Setting and getting a key via keyring should work."""
        with patch.object(mgr, "_keyring_available", True):
            with patch("keyring.set_password") as mock_set:
                mgr.set("openai", "sk-keyring-test")
                mock_set.assert_called_once_with(
                    CredentialManager.SERVICE_NAME, "openai", "sk-keyring-test"
                )

    def test_env_var_fallback(self, mgr, monkeypatch):
        """Getting should fall back to env var."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env-test")
        with patch.object(mgr, "_keyring_available", False):
            key = mgr.get("openai")
            assert key == "sk-env-test"

    def test_prysm_env_var(self, mgr, monkeypatch):
        """PRYSM_ prefixed env var should also work."""
        monkeypatch.setenv("PRYSM_OPENAI_API_KEY", "sk-prysm-env")
        with patch.object(mgr, "_keyring_available", False):
            key = mgr.get("openai")
            assert key == "sk-prysm-env"

    def test_delete_removes_key(self, mgr):
        """Deleting a key should remove it from file storage."""
        with patch.object(mgr, "_keyring_available", False):
            mgr.set("test", "sk-test", storage="file")
            assert mgr.get("test") == "sk-test"
            mgr.delete("test")
            assert mgr.get("test") is None

    def test_list_providers_empty(self, mgr):
        """Listing providers with none configured should return empty-ish."""
        with patch.object(mgr, "_keyring_available", False):
            with patch.dict(os.environ, {}, clear=True):
                providers = mgr.list_providers()
                # Should list known providers but none with keys
                assert any(p["has_key"] is False for p in providers)

    def test_list_providers_with_config(self, mgr):
        """Listing providers should show which have keys."""
        with patch.object(mgr, "_keyring_available", False):
            mgr.set("openai", "sk-test", storage="file")
            providers = mgr.list_providers()
            openai_info = next(p for p in providers if p["provider"] == "openai")
            assert openai_info["has_key"] is True
            assert openai_info["source"] == "file"

    def test_persistence_to_file(self, temp_dir):
        """Credentials should persist across CredentialManager instances."""
        path = temp_dir / "providers.json"
        mgr1 = CredentialManager(providers_path=path)
        with patch.object(mgr1, "_keyring_available", False):
            mgr1.set("test", "sk-persist", storage="file")

        mgr2 = CredentialManager(providers_path=path)
        with patch.object(mgr2, "_keyring_available", False):
            assert mgr2.get("test") == "sk-persist"

    def test_env_var_map(self):
        """ENV_VAR_MAP should have expected providers."""
        assert CredentialManager.ENV_VAR_MAP["openai"] == "OPENAI_API_KEY"
        assert CredentialManager.ENV_VAR_MAP["anthropic"] == "ANTHROPIC_API_KEY"
