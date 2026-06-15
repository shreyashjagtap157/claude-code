"""Pydantic models for all PRYSM configuration."""

from pydantic import BaseModel, Field
from typing import Optional


class UIConfig(BaseModel):
    """UI rendering configuration."""
    theme: str = "auto"
    streaming: bool = True
    show_thinking: bool = True
    status_bar: bool = True


class AgentConfig(BaseModel):
    """Agent loop configuration."""
    max_turns: int = 25
    context_window: int = 8192
    auto_summarize: bool = True


class PermissionConfig(BaseModel):
    """Permission system configuration."""
    ask: list[str] = Field(default_factory=lambda: ["Bash"])
    deny: list[str] = Field(default_factory=list)
    allow: list[str] = Field(default_factory=list)
    bash_allowlist: list[str] = Field(default_factory=list)


class SandboxConfig(BaseModel):
    """Sandbox configuration."""
    enabled: bool = False
    auto_allow_bash_if_sandboxed: bool = False
    allowed_domains: list[str] = Field(default_factory=list)
    read_only_paths: list[str] = Field(default_factory=list)
    max_bash_timeout: int = 30
    max_bash_memory_mb: int = 512


class PrysmConfig(BaseModel):
    """Root configuration model for PRYSM."""

    model: str = ""
    runtime: str = "auto"

    ui: UIConfig = UIConfig()
    agent: AgentConfig = AgentConfig()
    permissions: PermissionConfig = PermissionConfig()
    sandbox: SandboxConfig = SandboxConfig()
