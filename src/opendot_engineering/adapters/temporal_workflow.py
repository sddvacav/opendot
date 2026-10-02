"""Optional, fixed non-local Activity scheduling for the ADR 004 reference profile.

Import explicitly from a consumer-owned Workflow using the qualified Temporal
SDK 1.34.0. Version/API qualification belongs to trusted bootstrap, outside
Workflow execution. This module neither loads the worker nor resolves artifacts.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy


async def execute_reference(
    request: dict[str, Any], *, task_queue: str
) -> dict[str, Any]:
    """Await one fixed non-local Activity, returning its response unchanged.

    The consumer supplies a stable, trusted queue and calls this helper at most
    once per Workflow run. The consumer must also exclude retry/resubmit and
    new-run loops; the fixed Activity ID is not global duplicate suppression.
    SDK failures propagate without rescheduling or resolving the response ref.
    """
    return await workflow.execute_activity(
        "opendot.synthetic.reference.v1",
        request,
        task_queue=task_queue,
        activity_id="opendot-synthetic-reference-v1",
        retry_policy=RetryPolicy(maximum_attempts=1),
        start_to_close_timeout=timedelta(seconds=10),
        schedule_to_close_timeout=timedelta(seconds=60),
    )
