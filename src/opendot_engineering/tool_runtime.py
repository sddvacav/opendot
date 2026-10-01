"""OpenDot's bounded callable-only execution profile.

Modified extraction: excludes non-callable backends and durable orchestration.
The existing callable algorithm, six contracts, and deny-only guard are retained.
See docs/callable-execution.md for behavior, attribution, and limitations.
"""

from __future__ import annotations

import concurrent.futures
import copy
import hashlib
import json
import math
import os
import threading
import time
import uuid
from contextvars import copy_context
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any, Callable


class ToolRisk(StrEnum):
    READ_ONLY = "read_only"
    REVERSIBLE_WRITE = "reversible_write"
    IRREVERSIBLE_WRITE = "irreversible_write"


class BreakerState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass(frozen=True)
class ToolSpec:
    tool_id: str
    version: str
    input_schema: str
    output_schema: str
    risk: ToolRisk
    timeout_s: float = 60.0
    max_retries: int = 2
    idempotent: bool = True
    permissions: frozenset[str] = frozenset()
    semantic_validator: Callable[[Any], bool] | None = field(default=None, compare=False, repr=False)

    def validate(self) -> None:
        if not all((self.tool_id, self.version, self.input_schema, self.output_schema)):
            raise ValueError("tool identity and schemas are required")
        if (isinstance(self.timeout_s, bool) or not isinstance(self.timeout_s, (int, float))
                or not math.isfinite(self.timeout_s) or self.timeout_s <= 0
                or isinstance(self.max_retries, bool) or not isinstance(self.max_retries, int)
                or self.max_retries < 0):
            raise ValueError("invalid timeout or retry policy")
        if (not isinstance(self.permissions, (set, frozenset, tuple, list))
                or any(not isinstance(permission, str) or not permission for permission in self.permissions)):
            raise ValueError("permissions must be a finite collection of names")
        if not isinstance(self.idempotent, bool):
            raise ValueError("idempotent must be a boolean")
        if self.risk == ToolRisk.IRREVERSIBLE_WRITE and self.idempotent:
            raise ValueError("irreversible writes cannot be declared idempotent")


@dataclass(frozen=True)
class _ObservedToolExecution:
    """Live ToolRuntime observation, never reconstructed from worker JSON.

    This proves the dispatch/context boundary, not OS sandbox enforcement or
    model/provider diversity. Trusted Python owners remain inside the boundary.
    """

    execution_id: str
    execution_kind: str
    worker_pid: int
    dispatcher_pid: int
    input_sha256: str
    review_target_sha256: str | None
    read_only_declared: bool
    registration_sha256: str | None = None


@dataclass(frozen=True)
class ToolCallReceipt:
    call_id: str
    tool_id: str
    tool_version: str
    status: str
    attempts: int
    latency_s: float
    input_hash: str
    output_hash: str | None
    semantic_valid: bool
    error_type: str | None = None
    breaker_state: BreakerState = BreakerState.CLOSED
    execution_observation: _ObservedToolExecution | None = field(default=None, compare=False, repr=False)
    execution_liveness: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.call_id or not self.tool_id or self.attempts <= 0 or self.latency_s < 0:
            raise ValueError("invalid tool receipt")
        if self.status not in {"COMPLETED", "FAILED", "BLOCKED"}:
            raise ValueError("invalid tool receipt status")
        if len(self.input_hash) != 64 or (self.output_hash is not None and len(self.output_hash) != 64):
            raise ValueError("receipt hashes must be SHA-256")


@dataclass
class ToolHealth:
    success_ewma: float = 1.0
    semantic_ewma: float = 1.0
    latency_ewma: float = 0.0
    calls: int = 0
    consecutive_failures: int = 0
    breaker_state: BreakerState = BreakerState.CLOSED
    opened_at: float | None = None
    half_open_probe_in_flight: bool = False

    @property
    def reliability(self) -> float:
        latency_penalty = 1.0 / (1.0 + max(0.0, self.latency_ewma) / 60.0)
        return max(0.0, min(1.0, (self.success_ewma * self.semantic_ewma * latency_penalty) ** (1.0 / 3.0)))


class _ObservedToolTimeout(TimeoutError):
    def __init__(self, message: str, liveness: dict[str, Any]):
        super().__init__(message)
        self.liveness = liveness


@dataclass(frozen=True)
class _GuardBinding:
    """Captured deny-only embedding authority, supplied by the trusted owner."""

    current_context: Callable[[], Any]
    control_error: type[Exception]

    def check(self) -> None:
        try:
            context = self.current_context()
        except self.control_error:
            raise
        except Exception as exc:
            raise self.control_error("current-context resolver failed; refusing callable dispatch") from exc
        if context is not None:
            raise self.control_error("callable-only dispatch is forbidden in a bound control context")


class ToolRuntime:
    """One callable registry, dispatch, receipt, and in-memory health owner.

    Standalone mode cannot discover an unknown ambient ContextVar. Embeddings
    must request guarded mode and supply the trusted resolver and actual control
    exception class. The binding only refuses execution; it implements no control
    or durable observation and never clears an external execution hold.
    """

    def __init__(
        self, *, failure_threshold: int = 3, recovery_timeout_s: float = 30.0,
        ewma_alpha: float = 0.25, guarded_embedding: bool = False,
        current_context_resolver: Callable[[], Any] | None = None,
        control_error: type[Exception] | None = None,
    ):
        if (type(failure_threshold) is not int or failure_threshold < 1
                or not self._finite_number(recovery_timeout_s) or recovery_timeout_s < 0
                or not self._finite_number(ewma_alpha) or not 0.0 < ewma_alpha <= 1.0):
            raise ValueError("invalid tool runtime policy")
        if type(guarded_embedding) is not bool:
            raise ValueError("guarded_embedding must be a boolean")
        if guarded_embedding:
            if (not callable(current_context_resolver) or not isinstance(control_error, type)
                    or not issubclass(control_error, Exception) or control_error is Exception):
                raise ValueError("guarded embedding requires a resolver and a specific control error class")
            binding = _GuardBinding(current_context_resolver, control_error)
        else:
            if current_context_resolver is not None or control_error is not None:
                raise ValueError("embedding authorities require guarded_embedding=True")
            binding = None
        self._guard_binding = binding
        self.failure_threshold = failure_threshold
        self.recovery_timeout_s = recovery_timeout_s
        self.ewma_alpha = ewma_alpha
        self._specs: dict[str, ToolSpec] = {}
        self._handlers: dict[str, Callable[[dict[str, Any]], Any]] = {}
        self._health: dict[str, ToolHealth] = {}
        # Private ownership bookkeeping, under the same lock as existing health.
        # No parallel registry, scheduler, execution store, or public health field.
        self._probe_owners: dict[str, object] = {}
        self._health_generations: dict[str, int] = {}
        self._lock = threading.Lock()

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "_guard_binding" and hasattr(self, name):
            raise AttributeError("guarded embedding binding is immutable")
        super().__setattr__(name, value)

    def __delattr__(self, name: str) -> None:
        if name == "_guard_binding":
            raise AttributeError("guarded embedding binding is immutable")
        super().__delattr__(name)

    @staticmethod
    def _finite_number(value: Any) -> bool:
        return (not isinstance(value, bool) and isinstance(value, (int, float))
                and math.isfinite(value))

    @staticmethod
    def _check_guard(binding: _GuardBinding | None) -> None:
        if binding is not None:
            binding.check()

    def register(self, spec: ToolSpec, handler: Callable[[dict[str, Any]], Any]) -> None:
        spec.validate()
        if not callable(handler):
            raise TypeError("tool handler must be callable")
        # Store and dispatch the same detached permission contract.
        snapshot = replace(spec, permissions=frozenset(spec.permissions))
        snapshot.validate()
        with self._lock:
            if snapshot.tool_id in self._specs:
                raise ValueError(f"tool already registered: {snapshot.tool_id}")
            self._specs[snapshot.tool_id] = snapshot
            self._handlers[snapshot.tool_id] = handler
            self._health[snapshot.tool_id] = ToolHealth()
            self._health_generations[snapshot.tool_id] = 0

    def register_backend(self, spec: ToolSpec, backend: Any) -> None:
        """Compatibility refusal: this profile has no non-callable backend path."""
        raise NotImplementedError("Unsupported: this profile registers callables only")

    def _dispatch(
        self, spec: ToolSpec, payload: dict[str, Any], call_id: str, input_hash: str,
        *, handler: Callable[[dict[str, Any]], Any], registration: str,
        execution_id: str,
    ) -> tuple[Any, _ObservedToolExecution]:
        return handler(payload), _ObservedToolExecution(
            execution_id=execution_id,
            execution_kind="in_process",
            worker_pid=os.getpid(),
            dispatcher_pid=os.getpid(),
            input_sha256=input_hash,
            review_target_sha256=None,
            read_only_declared=spec.risk == ToolRisk.READ_ONLY,
            registration_sha256=registration,
        )

    def health(self, tool_id: str) -> ToolHealth:
        with self._lock:
            if tool_id not in self._health:
                raise LookupError(f"unknown tool: {tool_id}")
            return ToolHealth(**self._health[tool_id].__dict__)

    def reliability(self, tool_id: str) -> float:
        return self.health(tool_id).reliability

    def can_retry(self, tool_id: str, receipt: ToolCallReceipt) -> bool:
        """Predicate only: no durable blockade against a separate execute call."""
        with self._lock:
            if tool_id not in self._specs:
                raise LookupError(f"unknown tool: {tool_id}")
            spec = self._specs[tool_id]
        return (
            receipt.status == "FAILED"
            and spec.idempotent
            and receipt.error_type != "TimeoutError"
            and not receipt.execution_liveness.get("reconciliation_required", False)
        )

    def replay_safety_signature(self, tool_id: str) -> str | None:
        """Identify declared idempotence; does not prove effect idempotence."""
        with self._lock:
            spec = self._specs.get(tool_id)
        if spec is None or spec.idempotent is not True:
            return None
        return self._registration_signature(spec)

    def registration_signature(self, tool_id: str) -> str | None:
        """Hash the detached registration, not callable code or dispatch authority."""
        with self._lock:
            spec = self._specs.get(tool_id)
        return None if spec is None else self._registration_signature(spec)

    def _registration_signature(self, spec: ToolSpec) -> str:
        return self._hash_json({
            "backend_binding": {"kind": "callable"},
            "tool_id": spec.tool_id,
            "version": spec.version,
            "input_schema": spec.input_schema,
            "output_schema": spec.output_schema,
            "risk": str(spec.risk),
            "idempotent": spec.idempotent,
            "permissions": sorted(spec.permissions),
            "timeout_s": spec.timeout_s,
            "max_retries": spec.max_retries,
        })

    def _release_probe(self, tool_id: str, token: object) -> None:
        """Called under _lock; an old invocation cannot retire a newer probe."""
        if self._probe_owners.get(tool_id) is token:
            del self._probe_owners[tool_id]
            self._health[tool_id].half_open_probe_in_flight = False

    def _update_health(
        self, tool_id: str, *, success: bool, semantic_valid: bool,
        latency_s: float, probe_token: object | None, generation: int,
    ) -> None:
        """Called under _lock; stale settlements cannot change probe authority."""
        row = self._health[tool_id]
        alpha = self.ewma_alpha
        row.calls += 1
        row.success_ewma = alpha * float(success) + (1.0 - alpha) * row.success_ewma
        row.semantic_ewma = alpha * float(semantic_valid) + (1.0 - alpha) * row.semantic_ewma
        row.latency_ewma = alpha * latency_s + (1.0 - alpha) * row.latency_ewma
        owner = self._probe_owners.get(tool_id)
        if (self._health_generations[tool_id] != generation
                or (owner is not None and owner is not probe_token)):
            return
        if probe_token is not None:
            self._release_probe(tool_id, probe_token)
        if success and semantic_valid:
            row.consecutive_failures = 0
            row.breaker_state = BreakerState.CLOSED
            row.opened_at = None
        else:
            row.consecutive_failures += 1
            if row.consecutive_failures >= self.failure_threshold:
                row.breaker_state = BreakerState.OPEN
                row.opened_at = time.monotonic()

    def _allow_call(self, tool_id: str, token: object) -> bool:
        """Called under _lock with this invocation's opaque token."""
        row = self._health[tool_id]
        if row.breaker_state == BreakerState.CLOSED:
            return True
        if row.breaker_state == BreakerState.OPEN:
            elapsed = 0.0 if row.opened_at is None else time.monotonic() - row.opened_at
            if elapsed >= self.recovery_timeout_s:
                row.breaker_state = BreakerState.HALF_OPEN
            else:
                return False
        if row.breaker_state == BreakerState.HALF_OPEN:
            if row.half_open_probe_in_flight:
                return False
            row.half_open_probe_in_flight = True
            self._probe_owners[tool_id] = token
            self._health_generations[tool_id] += 1
            return True
        return False

    @staticmethod
    def _hash_json(value: Any) -> str:
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode()
        return hashlib.sha256(encoded).hexdigest()

    def execute(
        self, tool_id: str, payload: dict[str, Any], *,
        granted_permissions: frozenset[str] = frozenset(),
        approval_token: str | None = None, backoff_base_s: float = 0.0,
        attempt_limit: int | None = None,
    ) -> tuple[Any | None, ToolCallReceipt]:
        total_start = time.monotonic()
        with self._lock:
            binding = self._guard_binding
            original_spec = self._specs.get(tool_id)
            handler = self._handlers.get(tool_id)
        # Before conversion hooks, payload copying/hashing, and health admission.
        self._check_guard(binding)
        if original_spec is None:
            raise LookupError(f"unknown tool: {tool_id}")
        spec = replace(original_spec, permissions=frozenset(original_spec.permissions))
        control_errors = () if binding is None else (binding.control_error,)
        if attempt_limit is not None and (type(attempt_limit) is not int or attempt_limit < 1):
            raise ValueError("attempt_limit must be an exact positive int or None")
        configured_attempts = 1 + (spec.max_retries if spec.idempotent else 0)
        if type(configured_attempts) is not int or configured_attempts < 1:
            raise ValueError("computed attempt count must be an exact positive int")
        max_attempts = configured_attempts if attempt_limit is None else min(configured_attempts, attempt_limit)
        if type(max_attempts) is not int or max_attempts < 1:
            raise ValueError("computed attempt count must be an exact positive int")
        if not self._finite_number(backoff_base_s) or backoff_base_s < 0:
            raise ValueError("backoff_base_s must be finite and nonnegative")
        registration = self._registration_signature(spec)
        missing = spec.permissions - granted_permissions
        payload_baseline = copy.deepcopy(payload)
        input_hash = self._hash_json(payload_baseline)
        call_id = hashlib.sha256(f"{tool_id}:{spec.version}:{input_hash}:{time.time_ns()}".encode()).hexdigest()[:24]
        if missing or (spec.risk == ToolRisk.IRREVERSIBLE_WRITE and not approval_token):
            receipt = ToolCallReceipt(
                call_id=call_id, tool_id=tool_id, tool_version=spec.version,
                status="BLOCKED", attempts=1, latency_s=time.monotonic() - total_start,
                input_hash=input_hash, output_hash=None, semantic_valid=False,
                error_type="PermissionDenied" if missing else "ApprovalRequired",
                breaker_state=self.health(tool_id).breaker_state,
            )
            receipt.validate()
            return None, receipt
        token = object()
        with self._lock:
            allowed = self._allow_call(tool_id, token)
            probe_token = token if self._probe_owners.get(tool_id) is token else None
            generation = self._health_generations[tool_id]
            breaker_state = self._health[tool_id].breaker_state
        if not allowed:
            receipt = ToolCallReceipt(
                call_id=call_id, tool_id=tool_id, tool_version=spec.version,
                status="BLOCKED", attempts=1, latency_s=time.monotonic() - total_start,
                input_hash=input_hash, output_hash=None, semantic_valid=False,
                error_type="CircuitOpen", breaker_state=breaker_state,
            )
            receipt.validate()
            return None, receipt
        try:
            last_error: Exception | None = None
            preparation_s = time.monotonic() - total_start
            attempts = 0
            execution_liveness: dict[str, Any] = {}
            for attempt in range(max_attempts):
                attempts = attempt + 1
                try:
                    start = time.monotonic()
                    allowance = spec.timeout_s - (preparation_s if attempt == 0 else 0.0)
                    if allowance <= 0:
                        raise _ObservedToolTimeout("tool preparation exhausted the first attempt allowance", {
                            "execution_kind": "in_process", "timed_out": True,
                            "dispatch_started": False, "termination_observed": False,
                            "termination_scope": "not_started", "reconciliation_required": False,
                        })
                    dispatch_spec = replace(spec, timeout_s=allowance)
                    dispatch_args = (dispatch_spec, copy.deepcopy(payload_baseline), call_id, input_hash)
                    execution_id = uuid.uuid4().hex
                    dispatch_options = {"handler": handler, "registration": registration, "execution_id": execution_id}
                    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                    future = None
                    submission_entered = False
                    # Retained before submit; a lost submit handle cannot erase
                    # the actual wrapper's independent completion signal.
                    completion = concurrent.futures.Future()
                    dispatch_outcome_observed = False
                    dispatch_error: BaseException | None = None
                    try:
                        def observed_dispatch():
                            if not completion.set_running_or_notify_cancel():
                                raise concurrent.futures.CancelledError()
                            try:
                                # Runs inside the exact copied dispatch context.
                                self._check_guard(binding)
                                value = self._dispatch(*dispatch_args, **dispatch_options)
                            except BaseException as exc:
                                completion.set_exception(exc)
                                raise
                            completion.set_result(value)
                            return value

                        dispatch_context = copy_context()
                        submission_entered = True
                        future = pool.submit(dispatch_context.run, observed_dispatch)
                        try:
                            output, execution_observation = future.result(timeout=dispatch_spec.timeout_s)
                            dispatch_outcome_observed = True
                        except control_errors:
                            raise
                        except concurrent.futures.TimeoutError as exc:
                            # Establish no-retry liveness before any fallible
                            # cancellation/completion observation.
                            execution_liveness = {
                                "execution_id": execution_id, "execution_kind": "in_process",
                                "timed_out": True, "termination_observed": False,
                                "termination_scope": "in_process_handler",
                                "descendant_termination_observed": False,
                                "reconciliation_required": True,
                            }
                            try:
                                future.cancel()
                                execution_liveness["termination_observed"] = future.done()
                            except control_errors:
                                raise
                            except Exception as observation_error:
                                execution_liveness["observation_error_type"] = type(observation_error).__name__
                            raise _ObservedToolTimeout(
                                f"tool timed out after {dispatch_spec.timeout_s:.3f}s", execution_liveness) from exc
                        except BaseException as exc:
                            # Future.done() alone cannot distinguish a handler
                            # failure from interruption of result delivery after
                            # that handler finished. Only the wrapper-owned
                            # completion's identical exception proves this is the
                            # actual dispatch failure eligible for ordinary retry.
                            if completion.done() and not completion.cancelled():
                                dispatch_outcome_observed = completion.exception(timeout=0) is exc
                            raise
                    except BaseException as exc:
                        dispatch_error = exc
                        raise
                    finally:
                        try:
                            if (not execution_liveness.get("reconciliation_required", False)
                                    and submission_entered and not dispatch_outcome_observed):
                                execution_liveness = {
                                    "execution_id": execution_id, "execution_kind": "in_process",
                                    "submission_entered": submission_entered,
                                    "return_handle_observed": future is not None,
                                    "timed_out": False, "termination_observed": False,
                                    "termination_scope": "in_process_handler",
                                    "descendant_termination_observed": False,
                                    "reconciliation_required": True,
                                }
                        finally:
                            # Neither shutdown nor Future completion proves no
                            # external effects or descendant termination.
                            try:
                                pool.shutdown(wait=False, cancel_futures=True)
                            except BaseException as cleanup_error:
                                # Cleanup failure cannot turn an observed success
                                # or known handler failure into a repeat dispatch.
                                # Nor may it replace a canonical control refusal.
                                if not execution_liveness:
                                    execution_liveness.update({
                                        "execution_id": execution_id, "execution_kind": "in_process",
                                        "submission_entered": submission_entered,
                                        "return_handle_observed": future is not None,
                                        "timed_out": False, "termination_observed": False,
                                        "termination_scope": "in_process_handler",
                                        "descendant_termination_observed": False,
                                    })
                                execution_liveness["reconciliation_required"] = True
                                execution_liveness["cleanup_error_type"] = type(cleanup_error).__name__
                                if (dispatch_error is None or
                                        (isinstance(dispatch_error, Exception)
                                         and not isinstance(dispatch_error, control_errors) and
                                         (isinstance(cleanup_error, control_errors)
                                          or not isinstance(cleanup_error, Exception)))):
                                    raise
                                # Otherwise the already-active primary exception
                                # continues unchanged after this finally block.
                    latency = time.monotonic() - start
                    semantic_valid = True if spec.semantic_validator is None else bool(spec.semantic_validator(output))
                    if not semantic_valid:
                        raise ValueError("tool output failed semantic validation")
                    output_hash = self._hash_json(output)
                    with self._lock:
                        self._update_health(tool_id, success=True, semantic_valid=True,
                            latency_s=latency, probe_token=probe_token, generation=generation)
                        breaker_state = self._health[tool_id].breaker_state
                    receipt = ToolCallReceipt(
                        call_id=call_id, tool_id=tool_id, tool_version=spec.version,
                        status="COMPLETED", attempts=attempts, latency_s=time.monotonic() - total_start,
                        input_hash=input_hash, output_hash=output_hash, semantic_valid=True,
                        breaker_state=breaker_state, execution_observation=execution_observation,
                    )
                    receipt.validate()
                    return output, receipt
                except control_errors:
                    raise
                except Exception as exc:  # noqa: BLE001 - callable boundary
                    last_error = exc
                    if isinstance(exc, _ObservedToolTimeout):
                        execution_liveness = exc.liveness
                    with self._lock:
                        self._update_health(tool_id, success=False, semantic_valid=False,
                            latency_s=time.monotonic() - total_start, probe_token=probe_token, generation=generation)
                    if isinstance(exc, TimeoutError) or execution_liveness.get("reconciliation_required", False):
                        break
                    if attempt + 1 < max_attempts and backoff_base_s > 0:
                        time.sleep(backoff_base_s * (2 ** attempt))
            assert last_error is not None
            with self._lock:
                breaker_state = self._health[tool_id].breaker_state
            receipt = ToolCallReceipt(
                call_id=call_id, tool_id=tool_id, tool_version=spec.version,
                status="FAILED", attempts=attempts, latency_s=time.monotonic() - total_start,
                input_hash=input_hash, output_hash=None, semantic_valid=False,
                error_type="TimeoutError" if isinstance(last_error, TimeoutError) else type(last_error).__name__,
                breaker_state=breaker_state, execution_liveness=execution_liveness,
            )
            receipt.validate()
            return None, receipt
        finally:
            with self._lock:
                self._release_probe(tool_id, token)
