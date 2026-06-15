"""Model registry — ModelEntry schema and ModelRegistry with JSON persistence."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from prysm.config.paths import get_models_path, ensure_dirs


class ModelEntry(BaseModel):
    """A single model entry in the registry."""

    # Identity
    id: str                                 # Unique ID (e.g., "my-codellama", "openai/gpt-4o")
    name: str                               # Human-readable name
    provider: str = "local"                 # "local", "openai", "anthropic", "ollama", ...

    # Source (for local models)
    path: Optional[str] = None              # File path (for local .gguf models)
    hf_repo: Optional[str] = None           # Hugging Face repo (for HF models)

    # Cloud provider config
    api_base: Optional[str] = None          # Custom base URL
    model_name: Optional[str] = None        # Provider's model ID (e.g., "gpt-4o")

    # Runtime binding
    runtime: Optional[str] = None           # Override runtime (auto-detect if None)
    runtime_params: dict = Field(default_factory=dict)  # Runtime-specific params

    # Model metadata
    description: str = ""
    context_length: int = 4096
    capabilities: list[str] = Field(default_factory=lambda: ["chat"])  # chat, tools, vision, streaming

    # State
    loaded: bool = False
    default: bool = False

    # Timestamps
    added_at: str = ""
    last_used: Optional[str] = None

    @property
    def is_cloud(self) -> bool:
        """Whether this is a cloud/API-based model."""
        return self.provider not in ("local", "ollama")

    @property
    def is_local(self) -> bool:
        """Whether this is a local model file."""
        return self.provider == "local"


class ModelRegistry:
    """Manages the model registry — a JSON file with CRUD operations."""

    def __init__(self, path: Optional[Path] = None):
        self.path = path or get_models_path()
        self._models: dict[str, ModelEntry] = {}
        self._load()

    # ── CRUD Operations ──────────────────────────────────────────────────────

    def add(self, entry: ModelEntry) -> ModelEntry:
        """Add a model to the registry."""
        if not entry.added_at:
            entry.added_at = datetime.now().isoformat()
        self._models[entry.id] = entry
        self._save()
        return entry

    def get(self, model_id: str) -> Optional[ModelEntry]:
        """Get a model by ID."""
        return self._models.get(model_id)

    def remove(self, model_id: str) -> bool:
        """Remove a model from the registry."""
        if model_id in self._models:
            del self._models[model_id]
            self._save()
            return True
        return False

    def list_all(self) -> list[ModelEntry]:
        """List all registered models."""
        return list(self._models.values())

    def list_by_provider(self, provider: str) -> list[ModelEntry]:
        """List models for a specific provider."""
        return [m for m in self._models.values() if m.provider == provider]

    def list_loaded(self) -> list[ModelEntry]:
        """List loaded models."""
        return [m for m in self._models.values() if m.loaded]

    def set_default(self, model_id: str) -> Optional[ModelEntry]:
        """Set a model as the default (clears others)."""
        model = self._models.get(model_id)
        if not model:
            return None
        for m in self._models.values():
            m.default = False
        model.default = True
        self._save()
        return model

    def get_default(self) -> Optional[ModelEntry]:
        """Get the default model."""
        for m in self._models.values():
            if m.default:
                return m
        return None

    def mark_used(self, model_id: str) -> None:
        """Mark a model as recently used."""
        model = self._models.get(model_id)
        if model:
            model.last_used = datetime.now().isoformat()
            self._save()

    def update(self, model_id: str, **updates) -> Optional[ModelEntry]:
        """Update fields on a model entry."""
        model = self._models.get(model_id)
        if not model:
            return None
        for key, value in updates.items():
            if hasattr(model, key):
                setattr(model, key, value)
        self._save()
        return model

    def count(self) -> int:
        """Number of registered models."""
        return len(self._models)

    # ── Persistence ──────────────────────────────────────────────────────────

    def _load(self) -> None:
        """Load models from JSON file."""
        if not self.path.exists():
            self._models = {}
            return
        try:
            with open(self.path, "r") as f:
                data = json.load(f)
            self._models = {
                mid: ModelEntry(**m) for mid, m in data.items()
            }
        except (json.JSONDecodeError, OSError, TypeError):
            self._models = {}

    def _save(self) -> None:
        """Save models to JSON file."""
        ensure_dirs()
        data = {
            mid: m.model_dump() for mid, m in self._models.items()
        }
        with open(self.path, "w") as f:
            json.dump(data, f, indent=2, default=str)
