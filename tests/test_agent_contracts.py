"""Synthetic metadata contracts; no agent, model, provider, or native execution."""
from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, asdict, fields, replace
import hashlib
import importlib.util
import json
from pathlib import Path
import pickle

import pytest

from opendot_engineering.core import AgentManifest, ArtifactRef, Capability
from opendot_engineering.core import contracts


def capability():
    return Capability("summarize", "1", 0.9, 0.0, 0.25,
                      frozenset({"text:read"}), frozenset({"local"}))


def manifest():
    return AgentManifest("summary-agent", "Summarize supplied text",
                         frozenset({"summarize"}), frozenset({"read-text"}),
                         frozenset({"send-message"}), "text/v1", "summary/v1")


def test_canonical_export_identity():
    assert AgentManifest is contracts.AgentManifest
    assert Capability is contracts.Capability
    assert ArtifactRef is contracts.ArtifactRef
    assert not hasattr(contracts, "DotManifest")
    assert AgentManifest.__module__ == Capability.__module__ == contracts.__name__


def test_capability_field_order_annotations_defaults():
    assert [(f.name, f.type) for f in fields(Capability)] == [
        ("name", "str"), ("version", "str"), ("reliability", "float"),
        ("cost", "float"), ("latency", "float"),
        ("permissions", "frozenset[str]"), ("tags", "frozenset[str]"),
    ]
    value = Capability("summarize", "1", 1.0, 0.0, 0.0)
    assert value.permissions == value.tags == frozenset()
    assert value.validate() is None


def test_manifest_field_order_annotations_defaults():
    assert [(f.name, f.type) for f in fields(AgentManifest)] == [
        ("agent_id", "str"), ("purpose", "str"),
        ("capabilities", "frozenset[str]"), ("allowed_tools", "frozenset[str]"),
        ("denied_tools", "frozenset[str]"), ("input_schema", "str"),
        ("output_schema", "str"), ("max_turns", "int"), ("max_cost", "float"),
        ("memory_scope", "str"), ("oracle", "str"),
    ]
    value = manifest()
    assert (value.max_turns, value.max_cost, value.memory_scope, value.oracle) == (
        20, 5.0, "session", "default")
    assert value.validate() is None


@pytest.mark.parametrize("factory", [capability, manifest])
def test_frozen_equality_hash_and_asdict_roundtrip(factory):
    value = factory()
    assert value == factory() and hash(value) == hash(factory())
    data = asdict(value)
    assert type(value)(**data) == value
    with pytest.raises(FrozenInstanceError):
        setattr(value, fields(value)[0].name, "changed")
    assert pickle.loads(pickle.dumps(value)) == value
    assert type(pickle.loads(pickle.dumps(value))) is type(value)


@pytest.mark.parametrize("factory", [capability, manifest])
def test_json_requires_explicit_frozenset_projection(factory):
    value = factory()
    with pytest.raises(TypeError):
        json.dumps(asdict(value))
    data = {key: sorted(item) if isinstance(item, frozenset) else item
            for key, item in asdict(value).items()}
    restored = json.loads(json.dumps(data, allow_nan=False))
    for field in fields(value):
        if isinstance(getattr(value, field.name), frozenset):
            restored[field.name] = frozenset(restored[field.name])
    assert type(value)(**restored) == value


@pytest.mark.parametrize("field", ["name", "version"])
def test_capability_descriptors_reject_blank_and_wrong_types(field):
    for bad in ("", " \t\n", None, 0, False, b"text", [], {}):
        with pytest.raises(ValueError, match=field):
            replace(capability(), **{field: bad}).validate()


@pytest.mark.parametrize("field", ["agent_id", "purpose", "input_schema",
                                    "output_schema", "memory_scope", "oracle"])
def test_manifest_descriptors_reject_blank_and_wrong_types(field):
    for bad in ("", " \t\n", None, 0, False, b"text", [], {}):
        with pytest.raises(ValueError, match=field):
            replace(manifest(), **{field: bad}).validate()


@pytest.mark.parametrize("factory,field", [
    (capability, "permissions"), (capability, "tags"),
    (manifest, "capabilities"), (manifest, "allowed_tools"), (manifest, "denied_tools"),
])
def test_sets_require_immutable_nonblank_string_elements(factory, field):
    for bad in (set(), {"text"}, [], (), "text", None,
                frozenset({""}), frozenset({" \n"}), frozenset({1}),
                frozenset({None}), frozenset({"valid", b"wrong"})):
        with pytest.raises(ValueError, match=field):
            replace(factory(), **{field: bad}).validate()
    assert replace(factory(), **{field: frozenset()}).validate() is None


@pytest.mark.parametrize("factory,field", [
    (capability, "reliability"), (capability, "cost"),
    (capability, "latency"), (manifest, "max_cost"),
])
def test_numbers_reject_nonfinite_negative_boolean_and_wrong_types(factory, field):
    for bad in (float("nan"), float("inf"), -float("inf"), -0.01, -1,
                True, False, "1", None, complex(1, 0), [], {}):
        with pytest.raises(ValueError, match=field):
            replace(factory(), **{field: bad}).validate()
    for valid in (0, 0.0, -0.0, 1, 1.0):
        assert replace(factory(), **{field: valid}).validate() is None


def test_reliability_upper_bound():
    for bad in (1.000001, 2, 10**400):
        with pytest.raises(ValueError, match="reliability"):
            replace(capability(), reliability=bad).validate()


def test_finite_unbounded_numeric_metadata():
    for field in ("cost", "latency"):
        assert replace(capability(), **{field: 10**400}).validate() is None
    assert replace(manifest(), max_cost=10**400).validate() is None


def test_max_turns_requires_positive_nonboolean_integer():
    for bad in (0, -1, True, False, 1.0, 1.5, float("nan"), float("inf"), "2", None):
        with pytest.raises(ValueError, match="max_turns"):
            replace(manifest(), max_turns=bad).validate()
    for valid in (1, 20, 10**400):
        assert replace(manifest(), max_turns=valid).validate() is None


def test_tool_allow_and_deny_sets_must_be_disjoint():
    with pytest.raises(ValueError, match="both allowed and denied"):
        replace(manifest(), denied_tools=frozenset({"read-text"})).validate()
    assert replace(manifest(), allowed_tools=frozenset(), denied_tools=frozenset()).validate() is None


def test_validation_is_explicit_not_constructor_enforcement():
    invalid = Capability("", "1", float("nan"), -1.0, 0.0)
    with pytest.raises(ValueError):
        invalid.validate()
    invalid_manifest = replace(manifest(), max_turns=False)
    with pytest.raises(ValueError):
        invalid_manifest.validate()
    # frozen=True is shallow: construction accepts wrong types until validate().
    mutable = set()
    shallow = replace(capability(), tags=mutable)
    mutable.add("changed")
    assert shallow.tags == {"changed"}
    with pytest.raises(ValueError, match="tags"):
        shallow.validate()


def test_valid_strings_are_not_normalized_or_resolved():
    value = replace(manifest(), agent_id=" agent ", input_schema="unresolved-schema",
                    memory_scope="custom", oracle="custom", capabilities=frozenset({" unknown "}))
    assert value.validate() is None
    assert value.agent_id == " agent " and value.capabilities == frozenset({" unknown "})


def test_artifact_reference_source_body_unchanged():
    source = Path(contracts.__file__).read_text()
    tree = ast.parse(source)
    node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "ArtifactRef")
    raw = "\n".join(source.splitlines()[node.decorator_list[0].lineno - 1:node.end_lineno]) + "\n"
    assert hashlib.sha256(raw.encode()).hexdigest() == "f2335b4d0b2bb66bd70c66347ee7f9cc54c9805025d53f65893d7e2bc9a48b3c"


def test_metadata_example_runs_real_public_contracts():
    path = Path(__file__).resolve().parents[1] / "examples/agent-contracts/demo.py"
    spec = importlib.util.spec_from_file_location("metadata_example", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.Capability is Capability and module.AgentManifest is AgentManifest
    result = module.demonstrate()
    assert result["metadata_valid"] is True
    assert result["agent_execution_performed"] is False
    assert result["runtime_enforcement_provided"] is False
    assert result["manifest"]["agent_id"] == "local-summary"
    json.dumps(result, allow_nan=False)
