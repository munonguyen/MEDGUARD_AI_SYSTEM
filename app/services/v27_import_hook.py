"""Deferred V27.1 runtime hooks with no MedGuard model imports at package init.

``app.models.chat`` imports a small service helper while Python is still loading
``app.services``. Importing the clinical/agent modules directly from package
``__init__`` therefore creates a cycle. This finder wraps only the two V27.1
integration modules and applies tiny compatibility/runtime adapters *after* each
module has executed normally.
"""

from __future__ import annotations

import importlib.abc
import importlib.machinery
import sys
from functools import wraps
from types import ModuleType
from typing import Any


_ANSWER_TARGET = "app.services.answer_agents"
_CONTRACT_TARGET = "app.services.clinical_agent_contract"
_TARGETS = {_ANSWER_TARGET, _CONTRACT_TARGET}
_MARKER = "_medguard_v27_runtime_import_hook"


def _install_episode_builder_compat(module: ModuleType) -> None:
    """Adapt the legacy positional contract call to the V25 keyword-only API.

    ``build_clinical_episode_model`` is keyword-only and requires an episode id.
    V27.1's contract adapter historically passed just the messages positionally.
    Keep that call site backward compatible without changing the underlying V25
    episode builder or its public contract.
    """

    original = getattr(module, "build_clinical_episode_model", None)
    if original is None or getattr(original, "_v27_keyword_compat", False):
        return

    @wraps(original)
    def compatible(*args: Any, **kwargs: Any):
        if args:
            if len(args) != 1 or "messages" in kwargs:
                raise TypeError("clinical episode compatibility adapter accepts one positional messages argument")
            kwargs["messages"] = args[0]
        kwargs.setdefault("episode_id", "v27-contract-active-episode")
        return original(**kwargs)

    compatible._v27_keyword_compat = True  # type: ignore[attr-defined]
    module.build_clinical_episode_model = compatible


class _PostLoadLoader(importlib.abc.Loader):
    def __init__(self, wrapped: Any, fullname: str) -> None:
        self.wrapped = wrapped
        self.fullname = fullname

    def create_module(self, spec):  # type: ignore[no-untyped-def]
        creator = getattr(self.wrapped, "create_module", None)
        return creator(spec) if creator else None

    def exec_module(self, module: ModuleType) -> None:
        self.wrapped.exec_module(module)
        if self.fullname == _CONTRACT_TARGET:
            _install_episode_builder_compat(module)
            return

        if self.fullname == _ANSWER_TARGET:
            from app.services.v27_runtime_patch import install_v27_runtime_fallback

            install_v27_runtime_fallback()


class _V27RuntimeFinder(importlib.abc.MetaPathFinder):
    _medguard_v27_runtime_import_hook = True

    def find_spec(self, fullname: str, path=None, target=None):  # type: ignore[no-untyped-def]
        if fullname not in _TARGETS:
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec is None or spec.loader is None or isinstance(spec.loader, _PostLoadLoader):
            return spec
        spec.loader = _PostLoadLoader(spec.loader, fullname)
        return spec


def install_v27_answer_agent_hook() -> None:
    contract = sys.modules.get(_CONTRACT_TARGET)
    if contract is not None:
        _install_episode_builder_compat(contract)

    answer_agents = sys.modules.get(_ANSWER_TARGET)
    if answer_agents is not None and hasattr(answer_agents, "AnswerAgentPipeline"):
        from app.services.v27_runtime_patch import install_v27_runtime_fallback

        install_v27_runtime_fallback()

    if any(getattr(finder, _MARKER, False) for finder in sys.meta_path):
        return
    sys.meta_path.insert(0, _V27RuntimeFinder())
