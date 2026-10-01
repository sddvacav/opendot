"""Validate descriptive metadata only; no agent or tool execution."""
from dataclasses import asdict
import json

from opendot_engineering import __version__
from opendot_engineering.core import AgentManifest, Capability


def _json_record(value):
    return {key: sorted(item) if isinstance(item, frozenset) else item
            for key, item in asdict(value).items()}


def demonstrate():
    capability = Capability(
        name="summarize-text", version="1", reliability=0.9, cost=0.0,
        latency=0.1, permissions=frozenset({"text:read"}), tags=frozenset({"local"}),
    )
    manifest = AgentManifest(
        agent_id="local-summary", purpose="Describe a text-summary task",
        capabilities=frozenset({capability.name}), allowed_tools=frozenset({"read-text"}),
        denied_tools=frozenset({"send-message"}), input_schema="text/v1",
        output_schema="summary/v1", max_turns=1, max_cost=0.0,
    )
    capability.validate()
    manifest.validate()
    return {
        "package_version": __version__, "metadata_valid": True,
        "capability": _json_record(capability), "manifest": _json_record(manifest),
        "agent_execution_performed": False, "runtime_enforcement_provided": False,
    }


if __name__ == "__main__":
    print(json.dumps(demonstrate(), indent=2, sort_keys=True, allow_nan=False))
