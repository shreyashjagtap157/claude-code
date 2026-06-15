"""Provider configuration — ProviderConfig, ProviderRegistry, CredentialManager."""

import json
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

from pydantic import BaseModel, Field

from prysm.config.paths import get_providers_path, ensure_dirs


# ═══════════════════════════════════════════════════════════════════════════════
# Provider Configuration
# ═══════════════════════════════════════════════════════════════════════════════

class ProviderConfig(BaseModel):
    """Configuration for a cloud/API provider."""

    provider_id: str                         # "openai", "anthropic", "openrouter", etc.
    enabled: bool = True
    api_base: Optional[str] = None           # Custom base URL
    organization: Optional[str] = None       # For org-scoped APIs
    rate_limit: Optional[int] = None         # Requests per minute
    max_concurrency: int = 5
    timeout_seconds: int = 120
    proxy: Optional[str] = None             # HTTP/HTTPS proxy


# ═══════════════════════════════════════════════════════════════════════════════
# Credential Manager
# ═══════════════════════════════════════════════════════════════════════════════

CREDENTIAL_SERVICE = "prysm"


class CredentialManager:
    """Manages API credentials with OS keyring as primary storage.

    Storage priority: OS Keyring → Environment variables → File fallback
    """

    SERVICE_NAME = CREDENTIAL_SERVICE

    # Well-known provider env var names
    ENV_VAR_MAP: dict[str, str] = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "google": "GOOGLE_API_KEY",
        "groq": "GROQ_API_KEY",
        "together": "TOGETHER_API_KEY",
        "mistral": "MISTRAL_API_KEY",
        "cohere": "COHERE_API_KEY",
        "azure": "AZURE_API_KEY",
    }

    def __init__(self, providers_path: Optional[Path] = None):
        self.providers_path = providers_path or get_providers_path()
        self._keyring_available = self._check_keyring()

    def get(self, provider: str) -> Optional[str]:
        """Get credential: keyring → env var → file fallback.

        Args:
            provider: Provider ID (e.g., "openai", "anthropic").

        Returns:
            API key string or None if not found.
        """
        # 1. OS Keyring
        if self._keyring_available:
            try:
                import keyring
                key = keyring.get_password(self.SERVICE_NAME, provider)
                if key:
                    return key
            except Exception:
                pass

        # 2. Environment variable
        env_key = self._get_env_var_name(provider)
        if env_val := os.environ.get(env_key):
            return env_val

        # Also check generic PRYSM_ prefixed env var
        prysm_env_key = f"PRYSM_{provider.upper()}_API_KEY"
        if env_val := os.environ.get(prysm_env_key):
            return env_val

        # 3. File fallback
        return self._get_from_file(provider)

    def set(self, provider: str, key: str, storage: str = "keyring") -> bool:
        """Store a credential.

        Args:
            provider: Provider ID.
            key: API key value.
            storage: Storage backend: "keyring" or "file".

        Returns:
            True if stored successfully.
        """
        if storage == "keyring" and self._keyring_available:
            try:
                import keyring
                keyring.set_password(self.SERVICE_NAME, provider, key)
                return True
            except Exception:
                pass

        # Fallback to file
        return self._set_in_file(provider, key)

    def delete(self, provider: str) -> bool:
        """Delete a credential from all storage backends."""
        if self._keyring_available:
            try:
                import keyring
                keyring.delete_password(self.SERVICE_NAME, provider)
            except Exception:
                pass

        # Remove from file
        providers = self._load_providers_file()
        if provider in providers:
            providers[provider].pop("api_key", None)
            self._save_providers_file(providers)
            return True
        return False

    def list_providers(self) -> list[dict]:
        """List all configured providers with their key status."""
        result = []

        # Check keyring
        # (keyring doesn't support listing, so we use env vars + file)

        # Check env vars
        for provider_id, env_var in self.ENV_VAR_MAP.items():
            status = "env" if os.environ.get(env_var) else None
            prysm_env = f"PRYSM_{provider_id.upper()}_API_KEY"
            if not status and os.environ.get(prysm_env):
                status = "env"
            result.append({
                "provider": provider_id,
                "has_key": status is not None,
                "source": status or None,
            })

        # Check file
        providers = self._load_providers_file()
        for provider_id in providers:
            existing = next((r for r in result if r["provider"] == provider_id), None)
            if existing:
                if not existing["has_key"] and providers[provider_id].get("api_key"):
                    existing["has_key"] = True
                    existing["source"] = "file"
            else:
                result.append({
                    "provider": provider_id,
                    "has_key": bool(providers[provider_id].get("api_key")),
                    "source": "file" if providers[provider_id].get("api_key") else None,
                })

        return result

    def _get_env_var_name(self, provider: str) -> str:
        """Get the standard env var name for a provider."""
        return self.ENV_VAR_MAP.get(provider, f"{provider.upper()}_API_KEY")

    def _get_from_file(self, provider: str) -> Optional[str]:
        """Read API key from providers.json fallback."""
        providers = self._load_providers_file()
        return providers.get(provider, {}).get("api_key")

    def _set_in_file(self, provider: str, key: str) -> bool:
        """Write API key to providers.json.

        Warning: Stores the key in plaintext. OS keyring is preferred.
        """
        logger.warning("Storing API key for '%s' in plaintext file (keyring unavailable)", provider)
        providers = self._load_providers_file()
        if provider not in providers:
            providers[provider] = {}
        providers[provider]["api_key"] = key
        self._save_providers_file(providers)
        return True

    def _load_providers_file(self) -> dict:
        """Load the providers.json file."""
        if not self.providers_path.exists():
            return {}
        try:
            with open(self.providers_path, "r") as f:
                data = json.load(f)
            return data.get("providers", data)
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_providers_file(self, providers: dict) -> None:
        """Save to providers.json."""
        ensure_dirs()
        data = {
            "storage_backend": "keyring",
            "providers": providers,
        }
        with open(self.providers_path, "w") as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def _check_keyring() -> bool:
        """Check if the keyring backend is available."""
        try:
            import keyring
            keyring.get_keyring()
            return True
        except Exception:
            return False


# ═══════════════════════════════════════════════════════════════════════════════
# Provider Registry
# ═══════════════════════════════════════════════════════════════════════════════

TIER_1_PROVIDERS = {
    "openai": {
        "name": "OpenAI",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "o3-mini", "o4-mini"],
        "api_base": "https://api.openai.com/v1",
        "website": "https://platform.openai.com/api-keys",
    },
    "anthropic": {
        "name": "Anthropic",
        "models": ["claude-sonnet-4", "claude-haiku-3"],
        "api_base": "https://api.anthropic.com",
        "website": "https://console.anthropic.com/",
    },
    "google": {
        "name": "Google Gemini",
        "models": ["gemini-2.0-flash", "gemini-2.0-pro"],
        "api_base": "https://generativelanguage.googleapis.com/v1beta",
        "website": "https://aistudio.google.com/apikey",
    },
}

TIER_2_COMPATIBLE = {
    "openrouter": {
        "name": "OpenRouter",
        "models": ["100+ models"],
        "api_base": "https://openrouter.ai/api/v1",
        "website": "https://openrouter.ai/keys",
    },
    "deepseek": {
        "name": "DeepSeek",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "api_base": "https://api.deepseek.com",
        "website": "https://platform.deepseek.com/api_keys",
    },
    "groq": {
        "name": "Groq",
        "models": ["llama3-70b", "llama3-8b", "mixtral-8x7b"],
        "api_base": "https://api.groq.com/openai/v1",
        "website": "https://console.groq.com/keys",
    },
    "together": {
        "name": "Together AI",
        "models": ["mixtral-8x22b", "llama-3-70b"],
        "api_base": "https://api.together.xyz/v1",
        "website": "https://api.together.xyz/settings/api-keys",
    },
    "mistral": {
        "name": "Mistral AI",
        "models": ["mistral-large", "mistral-small", "codestral"],
        "api_base": "https://api.mistral.ai/v1",
        "website": "https://console.mistral.ai/api-keys/",
    },
}


class ProviderRegistry:
    """Registry of known providers with metadata."""

    @staticmethod
    def get_known_providers() -> dict[str, dict]:
        """Get all known providers (tier 1 + tier 2)."""
        return {**TIER_1_PROVIDERS, **TIER_2_COMPATIBLE}

    @staticmethod
    def get_provider_info(provider_id: str) -> Optional[dict]:
        """Get metadata for a specific provider."""
        return ProviderRegistry.get_known_providers().get(provider_id)

    @staticmethod
    def is_known(provider_id: str) -> bool:
        """Check if a provider ID is known."""
        return provider_id in ProviderRegistry.get_known_providers()

    @staticmethod
    def get_tier(provider_id: str) -> Optional[str]:
        """Get the tier of a provider."""
        if provider_id in TIER_1_PROVIDERS:
            return "bundled"
        if provider_id in TIER_2_COMPATIBLE:
            return "compatible"
        return None
