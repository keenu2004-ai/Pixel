"""
Abstract Base Driver for PIXEL Plugin Sandboxes.
"""

from abc import ABC, abstractmethod

from packages.contracts.ecosystem import (
    PluginCapability,
    PluginExecutionRequest,
    PluginExecutionResult,
    PluginManifest,
)


class BaseSandboxDriver(ABC):
    """Abstract sandbox driver governing execution boundaries and isolation."""

    @abstractmethod
    async def execute(
        self,
        manifest: PluginManifest,
        plugin_code_dir: str,
        request: PluginExecutionRequest,
        granted_capabilities: list[PluginCapability],
    ) -> PluginExecutionResult:
        """Execute a sandboxed action with capability validation and strict resource isolation."""
        pass

    @abstractmethod
    async def terminate_all(self) -> None:
        """Terminate all active sandbox instances."""
        pass
