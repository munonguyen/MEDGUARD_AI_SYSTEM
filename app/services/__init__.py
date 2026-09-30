"""Service package runtime hooks for MedGuard V27.1."""

from app.services.v27_runtime_patch import install_v27_runtime_fallback

install_v27_runtime_fallback()
