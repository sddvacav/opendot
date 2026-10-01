# Five controlled callable scenarios

Run `PYTHONPATH=src python -B examples/callable-execution/demo.py` from the repository
root. With the package installed, run the script with that environment's Python.
The example invokes actual pure Python callables and asserts success, permission
refusal, an allowed retry, a non-idempotent no-retry failure, and deny-only guard
refusal. Output is synthetic JSON on stdout. No files, services, models, native
backends, or devices are accessed by the handlers.

See [the API and its limits](../../docs/callable-execution.md). The example is finite
and does not demonstrate durable execution, sandboxing, or a model-driven agent.
