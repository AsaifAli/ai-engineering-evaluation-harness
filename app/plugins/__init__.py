"""Plugin contracts and registries for extensible AI project integrations."""

from .contracts import ProjectAdapterPlugin
from .registry import adapter_names, create_adapter, register_adapter

__all__ = [
    "ProjectAdapterPlugin",
    "adapter_names",
    "create_adapter",
    "register_adapter",
]
