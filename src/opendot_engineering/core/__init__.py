# Copyright 2026 OpenDot Engineering contributors
# SPDX-License-Identifier: Apache-2.0
"""Canonical local artifacts and descriptive contracts; no agent runtime."""

from .artifacts import ArtifactIntegrityError, ArtifactStore
from .contracts import AgentManifest, ArtifactRef, Capability

__all__ = ["AgentManifest", "ArtifactIntegrityError", "ArtifactRef", "ArtifactStore", "Capability"]
