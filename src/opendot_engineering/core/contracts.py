# Extraction and documentation changes: OpenDot Engineering contributors, 2026
# SPDX-License-Identifier: Apache-2.0
# Extracted canonical contracts; see docs/PROVENANCE.md for changes.

from __future__ import annotations

import math
import re
from dataclasses import dataclass

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class ArtifactRef:
    artifact_id: str
    uri: str
    mime_type: str
    size_bytes: int
    sha256: str
    schema_version: str = "1.0.0"
    producer: str = "unknown"
    task_id: str = "unknown"
    source_refs: tuple[str, ...] = ()
    integrity_verified: bool = False

    def validate(self) -> None:
        if not self.artifact_id.startswith("sha256:") or not self.uri.startswith("artifact://sha256/"):
            raise ValueError("artifact must use SHA-256 content addressing")
        if self.size_bytes < 0 or not _SHA256.match(self.sha256):
            raise ValueError("invalid artifact size or SHA-256")
        if self.artifact_id.removeprefix("sha256:") != self.sha256:
            raise ValueError("artifact_id does not match SHA-256")
        if self.uri.rsplit("/", 1)[-1] != self.sha256:
            raise ValueError("artifact URI does not match SHA-256")


def _validate_descriptor(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-blank string")


def _validate_string_set(value: frozenset[str], field: str) -> None:
    if not isinstance(value, frozenset):
        raise ValueError(f"{field} must be a frozenset of non-blank strings")
    for item in value:
        _validate_descriptor(item, field)


def _validate_number(value: float, field: str, upper: float | None = None) -> None:
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or (isinstance(value, float) and not math.isfinite(value))
            or value < 0 or (upper is not None and value > upper)):
        limit = "non-negative" if upper is None else f"in [0,{upper:g}]"
        raise ValueError(f"{field} must be a finite {limit} number")


@dataclass(frozen=True)
class Capability:
    name: str
    version: str
    reliability: float
    cost: float
    latency: float
    permissions: frozenset[str] = frozenset()
    tags: frozenset[str] = frozenset()

    def validate(self) -> None:
        _validate_descriptor(self.name, "name")
        _validate_descriptor(self.version, "version")
        _validate_number(self.reliability, "reliability", upper=1.0)
        _validate_number(self.cost, "cost")
        _validate_number(self.latency, "latency")
        _validate_string_set(self.permissions, "permissions")
        _validate_string_set(self.tags, "tags")


@dataclass(frozen=True)
class AgentManifest:
    agent_id: str
    purpose: str
    capabilities: frozenset[str]
    allowed_tools: frozenset[str]
    denied_tools: frozenset[str]
    input_schema: str
    output_schema: str
    max_turns: int = 20
    max_cost: float = 5.0
    memory_scope: str = "session"
    oracle: str = "default"

    def validate(self) -> None:
        for field in ("agent_id", "purpose", "input_schema", "output_schema",
                      "memory_scope", "oracle"):
            _validate_descriptor(getattr(self, field), field)
        for field in ("capabilities", "allowed_tools", "denied_tools"):
            _validate_string_set(getattr(self, field), field)
        if self.allowed_tools & self.denied_tools:
            raise ValueError("a tool cannot be both allowed and denied")
        if isinstance(self.max_turns, bool) or not isinstance(self.max_turns, int) or self.max_turns <= 0:
            raise ValueError("max_turns must be a positive integer")
        _validate_number(self.max_cost, "max_cost")
