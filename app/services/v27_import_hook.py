"""Deferred V27.1 AnswerAgent runtime hook.

``app.models.chat`` imports a service helper while Python is still loading the
``app.services`` package. Importing ``answer_agents`` directly from package
``__init__`` would therefore create a cycle. This finder wraps only the
``answer_agents`` loader and installs the V27.1 contract-aware fallback adapter
after that module has executed normally.
"""

from __future__ import annotations

import importlib.abc
import importlib.machinery
import sys
from types import ModuleType
from typing import Any


_TARGET = "app.services.answer_agents"
_MARKER = "_medguard_v27_runtime_import_hook"


class _PostLoadLoader(importlib.abc.Loader):
    def __init__(self, wrapped: Any) -> None:
        self.wrapped = wrapped

    def create_module(self, spec):  # type: ignore[no-untyped-def]
        creator = getattr(self.wrapped, "create_module", None)
        return creator(spec) if creator else None

    def exec_module(self, module: ModuleType) -> None:
        self.wrapped.exec_module(module)
        from app.services.v27_runtime_patch import install_v27_runtime_fallback

        install_v27_runtime_fallback()


class _V27RuntimeFinder(importlib.abc.MetaPathFinder):
    _medguard_v27_runtime_import_hook = True

    def find_spec(self, fullname: str, path=None, target=None):  # type: ignore[no-untyped-def]
        if fullname != _TARGET:
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec is None or spec.loader is None or isinstance(spec.loader, _PostLoadLoader):
            return spec
        spec.loader = _PostLoadLoader(spec.loader)
        return spec


def install_v27_answer_agent_hook() -> None:
    answer_agents = sys.modules.get(_TARGET)
    if answer_agents is not None and hasattr(answer_agents, "AnswerAgentPipeline"):
        from app.services.v27_runtime_patch import install_v27_runtime_fallback

        install_v27_runtime_fallback()
        return

    if any(getattr(finder, _MARKER, False) for finder in sys.meta_path):
        return
    sys.meta_path.insert(0, _V27RuntimeFinder())
