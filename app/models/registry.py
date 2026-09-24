from __future__ import annotations

from pydantic import BaseModel, Field


class ModelDescriptor(BaseModel):
    name: str
    version: str
    license: str
    purpose: str
    active: bool = True


class ModelsResponse(BaseModel):
    models: list[ModelDescriptor] = Field(default_factory=list)
