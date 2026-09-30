"""Service package bootstrap for MedGuard V27.1."""

from app.services.v27_import_hook import install_v27_answer_agent_hook

install_v27_answer_agent_hook()
