"""Deferred V27/V27.2 runtime hooks.

``app.models.chat`` imports service helpers while Python is still loading the
``app.services`` package. Importing the heavier clinical modules directly from
package ``__init__`` would therefore create cycles. This finder waits until each
target module has executed normally, then installs narrow, idempotent adapters.
"""

from __future__ import annotations

import importlib.abc
import importlib.machinery
import sys
from types import ModuleType
from typing import Any


_ANSWER_TARGET = "app.services.answer_agents"
_REASONER_TARGET = "app.services.contextual_clinical_reasoner"
_ANSWERING_TARGET = "app.services.answering"
_CHAT_TARGET = "app.services.chat"
_TARGETS = {_ANSWER_TARGET, _REASONER_TARGET, _ANSWERING_TARGET, _CHAT_TARGET}
_MARKER = "_medguard_v27_runtime_import_hook"


def _install_reasoner_priority(module: ModuleType) -> None:
    from app.services.episode_delta_reasoning import install_episode_delta_reasoning
    from app.services.multi_domain_episode_reasoning import install_multi_domain_episode_reasoning

    install_episode_delta_reasoning(module)
    install_multi_domain_episode_reasoning(module)


def _install_answering_patch(module: ModuleType) -> None:
    from app.services.v27_2_answering_patch import install_v27_2_answering_patch

    install_v27_2_answering_patch(module)


def _install_chat_patch(module: ModuleType) -> None:
    from app.services.conversation_intelligence import install_chat_conversation_intelligence
    from app.services.medication_conversation_policy import install_medication_conversation_policy

    # Conversation intelligence owns context scoping/result enrichment first.
    # The medication policy then wraps that response path narrowly so missing-
    # information prompts remain contextual without bypassing Writer/Reviewer.
    install_chat_conversation_intelligence(module)
    install_medication_conversation_policy(module)


class _PostLoadLoader(importlib.abc.Loader):
    def __init__(self, wrapped: Any, fullname: str) -> None:
        self.wrapped = wrapped
        self.fullname = fullname

    def create_module(self, spec):  # type: ignore[no-untyped-def]
        creator = getattr(self.wrapped, "create_module", None)
        return creator(spec) if creator else None

    def exec_module(self, module: ModuleType) -> None:
        self.wrapped.exec_module(module)
        if self.fullname == _REASONER_TARGET:
            _install_reasoner_priority(module)
            return
        if self.fullname == _ANSWERING_TARGET:
            _install_answering_patch(module)
            return
        if self.fullname == _CHAT_TARGET:
            _install_chat_patch(module)
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
    reasoner = sys.modules.get(_REASONER_TARGET)
    if reasoner is not None and hasattr(reasoner, "build_contextual_reasoning_frame"):
        _install_reasoner_priority(reasoner)

    answering = sys.modules.get(_ANSWERING_TARGET)
    if answering is not None and hasattr(answering, "build_grounded_answer"):
        _install_answering_patch(answering)

    chat = sys.modules.get(_CHAT_TARGET)
    if chat is not None and hasattr(chat, "orchestrate_chat"):
        _install_chat_patch(chat)

    answer_agents = sys.modules.get(_ANSWER_TARGET)
    if answer_agents is not None and hasattr(answer_agents, "AnswerAgentPipeline"):
        from app.services.v27_runtime_patch import install_v27_runtime_fallback

        install_v27_runtime_fallback()

    if any(getattr(finder, _MARKER, False) for finder in sys.meta_path):
        return
    sys.meta_path.insert(0, _V27RuntimeFinder())
