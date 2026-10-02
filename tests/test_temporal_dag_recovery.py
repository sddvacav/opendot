"""ADR 008 frozen finite oracles. No service, network, native or lifetime work.

The literal vectors below were copied from the independently frozen design
manifest before executable adapter edits. Fabricated fixture records establish
schema/hash consistency only. The separate canonical-put observer tests capture
real local synthetic publications before Updates; neither is live-effect proof.
"""
from __future__ import annotations

import ast
import asyncio
import copy
from dataclasses import asdict, fields, replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, get_type_hints

import pytest

pytest.importorskip("temporalio", reason="explicit optional SDK qualification")
from temporalio import activity, workflow
from temporalio.common import Priority, RetryPolicy, TypedSearchAttributes
from temporalio.converter import DataConverter
from temporalio.exceptions import ApplicationError
from temporalio.testing import ActivityEnvironment

from opendot_engineering.adapters import temporal_activity as activity_module
from opendot_engineering.adapters import temporal_workflow as workflow_module
from opendot_engineering.core.artifacts import ArtifactStore
from opendot_engineering.core.contracts import ArtifactRef
from opendot_engineering.tool_runtime import ToolRuntime

FROZEN = {'fixture_mission_id': 'frozen-example',
 'fixture_namespace': 'synthetic',
 'fixture_workflow_id': 'opendot-dag2-frozen-example-19843079a5da00754ec1b5399962c33874b907eb4d0d6fcf55cd3be2f4dffb63',
 'fixture_workflow_run_id': '11111111-1111-4111-8111-111111111111',
 'nonpositive_output_pins': {'null': '74234e98afe7498fb5daf1f36ac2d78acc339464f950703b8c019892f982b90b'},
 'plan': {'b_transform': {'left': 'accepted_A.output', 'return_null': False, 'right': 1},
          'edges': [['A', 'B']],
          'handler_source_encoding': 'ast-source-segments:_validate_payload,bounded_sum,bounded_sum_valid;join=LF-LF;final=LF',
          'handler_source_sha256': 'a97dadac88bed7b09d2398516617216cb865ae97db411c12b72de01d7a78d1cb',
          'limits': {'accepted_updates': 2,
                     'activity_attempts': 1,
                     'activity_commands': 6,
                     'activity_executor_threads': 1,
                     'activity_slots': 1,
                     'application_retries': 0,
                     'execute_per_node': 1,
                     'nodes': 2,
                     'normal_inspect_per_node': 1,
                     'observation_seconds': 300,
                     'reconcile_inspect_per_node': 1,
                     'request_response_bytes': 4096,
                     'result_bytes': 16384,
                     'result_bytes_reserved': 32768,
                     'schedule_to_close_seconds': 60,
                     'seed_bytes': 256,
                     'start_to_close_seconds': 10,
                     'state_bytes': 16384,
                     'terminal_drain_seconds_max': 1,
                     'tool_attempts': 1,
                     'workflow_attempts': 1,
                     'workflows': 1},
          'profile': 'synthetic.dependent_sum.v1',
          'registration_sha256': '5f2b1e81954530f31c7d2c83b9c582883b8391190ebe13b69b8bf91f044cb0c3',
          'schema_version': 'opendot.temporal.dag-plan.v1',
          'schemas': {'effect': 'opendot.effect.v1',
                      'inspect': 'opendot.temporal.dag-inspect.v1',
                      'inspection': 'opendot.temporal.dag-inspection.v1',
                      'origin': 'opendot.temporal.dag-origin.v1',
                      'plan': 'opendot.temporal.dag-plan.v1',
                      'reconcile': 'opendot.temporal.dag-reconcile.v1',
                      'reconciliation': 'opendot.temporal.dag-reconciliation.v1',
                      'result': 'opendot.temporal.dag-result.v1',
                      'start': 'opendot.temporal.dag-start.v1',
                      'state': 'opendot.temporal.dag-state.v1',
                      'step': 'opendot.temporal.dag-step.v1',
                      'step_response': 'opendot.temporal.dag-step-response.v1'},
          'seed_producer': 'opendot.temporal.dag-seed.v1',
          'seed_sha256': '897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02',
          'seed_task_id': 'seed',
          'tasks': [{'input_payload_sha256': '897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02',
                     'node_id': 'A',
                     'output_sha256': 'ef2d127de37b942baad06145e54b0c619a1f22327b2ebbcfbec78f5564afe39d',
                     'parent': None},
                    {'input_payload_sha256': '6d23a7a66975efd35356848b1f69b848e99c3c76dc5a3740e35328d41c05440a',
                     'node_id': 'B',
                     'output_sha256': 'e7f6c011776e8db7cd330b54174fd76f7d0216b612387a5ffcfb81e6f0919683',
                     'parent': 'A'}],
          'tool_id': 'synthetic.bounded_sum'},
 'plan_canonical_bytes': '{"b_transform":{"left":"accepted_A.output","return_null":false,"right":1},"edges":[["A","B"]],"handler_source_encoding":"ast-source-segments:_validate_payload,bounded_sum,bounded_sum_valid;join=LF-LF;final=LF","handler_source_sha256":"a97dadac88bed7b09d2398516617216cb865ae97db411c12b72de01d7a78d1cb","limits":{"accepted_updates":2,"activity_attempts":1,"activity_commands":6,"activity_executor_threads":1,"activity_slots":1,"application_retries":0,"execute_per_node":1,"nodes":2,"normal_inspect_per_node":1,"observation_seconds":300,"reconcile_inspect_per_node":1,"request_response_bytes":4096,"result_bytes":16384,"result_bytes_reserved":32768,"schedule_to_close_seconds":60,"seed_bytes":256,"start_to_close_seconds":10,"state_bytes":16384,"terminal_drain_seconds_max":1,"tool_attempts":1,"workflow_attempts":1,"workflows":1},"profile":"synthetic.dependent_sum.v1","registration_sha256":"5f2b1e81954530f31c7d2c83b9c582883b8391190ebe13b69b8bf91f044cb0c3","schema_version":"opendot.temporal.dag-plan.v1","schemas":{"effect":"opendot.effect.v1","inspect":"opendot.temporal.dag-inspect.v1","inspection":"opendot.temporal.dag-inspection.v1","origin":"opendot.temporal.dag-origin.v1","plan":"opendot.temporal.dag-plan.v1","reconcile":"opendot.temporal.dag-reconcile.v1","reconciliation":"opendot.temporal.dag-reconciliation.v1","result":"opendot.temporal.dag-result.v1","start":"opendot.temporal.dag-start.v1","state":"opendot.temporal.dag-state.v1","step":"opendot.temporal.dag-step.v1","step_response":"opendot.temporal.dag-step-response.v1"},"seed_producer":"opendot.temporal.dag-seed.v1","seed_sha256":"897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02","seed_task_id":"seed","tasks":[{"input_payload_sha256":"897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02","node_id":"A","output_sha256":"ef2d127de37b942baad06145e54b0c619a1f22327b2ebbcfbec78f5564afe39d","parent":null},{"input_payload_sha256":"6d23a7a66975efd35356848b1f69b848e99c3c76dc5a3740e35328d41c05440a","node_id":"B","output_sha256":"e7f6c011776e8db7cd330b54174fd76f7d0216b612387a5ffcfb81e6f0919683","parent":"A"}],"tool_id":"synthetic.bounded_sum"}',
 'plan_sha256': '19843079a5da00754ec1b5399962c33874b907eb4d0d6fcf55cd3be2f4dffb63',
 'seed_ref': {'artifact_id': 'sha256:897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02',
              'integrity_verified': False,
              'mime_type': 'application/json',
              'producer': 'opendot.temporal.dag-seed.v1',
              'schema_version': '1.0.0',
              'sha256': '897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02',
              'size_bytes': 40,
              'source_refs': [],
              'task_id': 'seed',
              'uri': 'artifact://sha256/897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02'},
 'vectors': {'A': {'effect_id': 'sha256:85b56651dc0114baa5ad1068d538337dffa6848ecfb892e782f53006d9f5ba24',
                   'input_bytes': '{"left":2,"return_null":false,"right":3}',
                   'input_sha256': '897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02',
                   'origin_evidence_sha256': '980cc0c21a3d089c96833c9a7ba0fa479d470a741c4be4ef8456edf7670013ab',
                   'original_origin_record': {'capture_phase': 'original_put_return_before_response',
                                              'effect_id': 'sha256:85b56651dc0114baa5ad1068d538337dffa6848ecfb892e782f53006d9f5ba24',
                                              'execution_activity_id': 'dag2-execute-85b56651dc0114baa5ad1068d538337dffa6848ecfb892e782f53006d9f5ba24',
                                              'mission_id': 'frozen-example',
                                              'namespace': 'synthetic',
                                              'node_id': 'A',
                                              'origin_kind': 'trusted-single-operator-synthetic-put-observer',
                                              'original_result_ref': {'artifact_id': 'sha256:ac56ef93531558b0a770c283d0c3ecc1c1b1795468ffe7150065819e5178a07a',
                                                                      'integrity_verified': False,
                                                                      'mime_type': 'application/json',
                                                                      'producer': 'opendot.temporal.dag-result.v1',
                                                                      'schema_version': '1.0.0',
                                                                      'sha256': 'ac56ef93531558b0a770c283d0c3ecc1c1b1795468ffe7150065819e5178a07a',
                                                                      'size_bytes': 2223,
                                                                      'source_refs': ['sha256:897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02'],
                                                                      'task_id': '85b56651dc0114baa5ad1068d538337dffa6848ecfb892e782f53006d9f5ba24',
                                                                      'uri': 'artifact://sha256/ac56ef93531558b0a770c283d0c3ecc1c1b1795468ffe7150065819e5178a07a'},
                                              'plan_sha256': '19843079a5da00754ec1b5399962c33874b907eb4d0d6fcf55cd3be2f4dffb63',
                                              'schema_version': 'opendot.temporal.dag-origin.v1',
                                              'workflow_id': 'opendot-dag2-frozen-example-19843079a5da00754ec1b5399962c33874b907eb4d0d6fcf55cd3be2f4dffb63',
                                              'workflow_run_id': '11111111-1111-4111-8111-111111111111'},
                   'original_result_body': {'activity_id': 'dag2-execute-85b56651dc0114baa5ad1068d538337dffa6848ecfb892e782f53006d9f5ba24',
                                            'device_control_authority': False,
                                            'effect_id': 'sha256:85b56651dc0114baa5ad1068d538337dffa6848ecfb892e782f53006d9f5ba24',
                                            'independent_review': 'NOT_EVALUATED',
                                            'input_payload_sha256': '897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02',
                                            'mission_id': 'frozen-example',
                                            'namespace': 'synthetic',
                                            'node_id': 'A',
                                            'observation_provenance': 'serialized_runtime_report_not_live_proof',
                                            'output': 5,
                                            'owner_integration': 'NOT_EVALUATED',
                                            'parent_result_ref': None,
                                            'plan_sha256': '19843079a5da00754ec1b5399962c33874b907eb4d0d6fcf55cd3be2f4dffb63',
                                            'profile': 'synthetic.dependent_sum.v1',
                                            'receipt_report': {'attempts': 1,
                                                               'breaker_state': 'closed',
                                                               'call_id': 'aaaaaaaaaaaaaaaaaaaaaaaa',
                                                               'error_type': None,
                                                               'execution_liveness': {},
                                                               'execution_observation': {'dispatcher_pid': 101,
                                                                                         'execution_id': 'cccccccccccccccccccccccccccccccc',
                                                                                         'execution_kind': 'in_process',
                                                                                         'input_sha256': '897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02',
                                                                                         'read_only_declared': True,
                                                                                         'registration_sha256': '5f2b1e81954530f31c7d2c83b9c582883b8391190ebe13b69b8bf91f044cb0c3',
                                                                                         'review_target_sha256': None,
                                                                                         'worker_pid': 101},
                                                               'input_hash': '897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02',
                                                               'latency_s': 0.0,
                                                               'output_hash': 'ef2d127de37b942baad06145e54b0c619a1f22327b2ebbcfbec78f5564afe39d',
                                                               'semantic_valid': True,
                                                               'status': 'COMPLETED',
                                                               'tool_id': 'synthetic.bounded_sum',
                                                               'tool_version': '1'},
                                            'registration_sha256': '5f2b1e81954530f31c7d2c83b9c582883b8391190ebe13b69b8bf91f044cb0c3',
                                            'schema_version': 'opendot.temporal.dag-result.v1',
                                            'scientific_validity': False,
                                            'seed_ref': {'artifact_id': 'sha256:897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02',
                                                         'integrity_verified': False,
                                                         'mime_type': 'application/json',
                                                         'producer': 'opendot.temporal.dag-seed.v1',
                                                         'schema_version': '1.0.0',
                                                         'sha256': '897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02',
                                                         'size_bytes': 40,
                                                         'source_refs': [],
                                                         'task_id': 'seed',
                                                         'uri': 'artifact://sha256/897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02'},
                                            'workflow_id': 'opendot-dag2-frozen-example-19843079a5da00754ec1b5399962c33874b907eb4d0d6fcf55cd3be2f4dffb63',
                                            'workflow_run_id': '11111111-1111-4111-8111-111111111111'},
                   'original_result_ref': {'artifact_id': 'sha256:ac56ef93531558b0a770c283d0c3ecc1c1b1795468ffe7150065819e5178a07a',
                                           'integrity_verified': False,
                                           'mime_type': 'application/json',
                                           'producer': 'opendot.temporal.dag-result.v1',
                                           'schema_version': '1.0.0',
                                           'sha256': 'ac56ef93531558b0a770c283d0c3ecc1c1b1795468ffe7150065819e5178a07a',
                                           'size_bytes': 2223,
                                           'source_refs': ['sha256:897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02'],
                                           'task_id': '85b56651dc0114baa5ad1068d538337dffa6848ecfb892e782f53006d9f5ba24',
                                           'uri': 'artifact://sha256/ac56ef93531558b0a770c283d0c3ecc1c1b1795468ffe7150065819e5178a07a'},
                   'output_bytes': '5',
                   'output_sha256': 'ef2d127de37b942baad06145e54b0c619a1f22327b2ebbcfbec78f5564afe39d'},
             'B': {'effect_id': 'sha256:639ecb03da5d305b5feda86c6b0ac26b446ce803753a11866b206c68f671e77d',
                   'input_bytes': '{"left":5,"return_null":false,"right":1}',
                   'input_sha256': '6d23a7a66975efd35356848b1f69b848e99c3c76dc5a3740e35328d41c05440a',
                   'origin_evidence_sha256': '4706934b1088a939b19c363de42b0ea9567a9fa07d762c042465486a543dcd0e',
                   'original_origin_record': {'capture_phase': 'original_put_return_before_response',
                                              'effect_id': 'sha256:639ecb03da5d305b5feda86c6b0ac26b446ce803753a11866b206c68f671e77d',
                                              'execution_activity_id': 'dag2-execute-639ecb03da5d305b5feda86c6b0ac26b446ce803753a11866b206c68f671e77d',
                                              'mission_id': 'frozen-example',
                                              'namespace': 'synthetic',
                                              'node_id': 'B',
                                              'origin_kind': 'trusted-single-operator-synthetic-put-observer',
                                              'original_result_ref': {'artifact_id': 'sha256:adb5d50840b20d03149b27c6867f963736ae54a904658f6239e7e37666489204',
                                                                      'integrity_verified': False,
                                                                      'mime_type': 'application/json',
                                                                      'producer': 'opendot.temporal.dag-result.v1',
                                                                      'schema_version': '1.0.0',
                                                                      'sha256': 'adb5d50840b20d03149b27c6867f963736ae54a904658f6239e7e37666489204',
                                                                      'size_bytes': 2787,
                                                                      'source_refs': ['sha256:897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02',
                                                                                      'sha256:ac56ef93531558b0a770c283d0c3ecc1c1b1795468ffe7150065819e5178a07a'],
                                                                      'task_id': '639ecb03da5d305b5feda86c6b0ac26b446ce803753a11866b206c68f671e77d',
                                                                      'uri': 'artifact://sha256/adb5d50840b20d03149b27c6867f963736ae54a904658f6239e7e37666489204'},
                                              'plan_sha256': '19843079a5da00754ec1b5399962c33874b907eb4d0d6fcf55cd3be2f4dffb63',
                                              'schema_version': 'opendot.temporal.dag-origin.v1',
                                              'workflow_id': 'opendot-dag2-frozen-example-19843079a5da00754ec1b5399962c33874b907eb4d0d6fcf55cd3be2f4dffb63',
                                              'workflow_run_id': '11111111-1111-4111-8111-111111111111'},
                   'original_result_body': {'activity_id': 'dag2-execute-639ecb03da5d305b5feda86c6b0ac26b446ce803753a11866b206c68f671e77d',
                                            'device_control_authority': False,
                                            'effect_id': 'sha256:639ecb03da5d305b5feda86c6b0ac26b446ce803753a11866b206c68f671e77d',
                                            'independent_review': 'NOT_EVALUATED',
                                            'input_payload_sha256': '6d23a7a66975efd35356848b1f69b848e99c3c76dc5a3740e35328d41c05440a',
                                            'mission_id': 'frozen-example',
                                            'namespace': 'synthetic',
                                            'node_id': 'B',
                                            'observation_provenance': 'serialized_runtime_report_not_live_proof',
                                            'output': 6,
                                            'owner_integration': 'NOT_EVALUATED',
                                            'parent_result_ref': {'artifact_id': 'sha256:ac56ef93531558b0a770c283d0c3ecc1c1b1795468ffe7150065819e5178a07a',
                                                                  'integrity_verified': False,
                                                                  'mime_type': 'application/json',
                                                                  'producer': 'opendot.temporal.dag-result.v1',
                                                                  'schema_version': '1.0.0',
                                                                  'sha256': 'ac56ef93531558b0a770c283d0c3ecc1c1b1795468ffe7150065819e5178a07a',
                                                                  'size_bytes': 2223,
                                                                  'source_refs': ['sha256:897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02'],
                                                                  'task_id': '85b56651dc0114baa5ad1068d538337dffa6848ecfb892e782f53006d9f5ba24',
                                                                  'uri': 'artifact://sha256/ac56ef93531558b0a770c283d0c3ecc1c1b1795468ffe7150065819e5178a07a'},
                                            'plan_sha256': '19843079a5da00754ec1b5399962c33874b907eb4d0d6fcf55cd3be2f4dffb63',
                                            'profile': 'synthetic.dependent_sum.v1',
                                            'receipt_report': {'attempts': 1,
                                                               'breaker_state': 'closed',
                                                               'call_id': 'bbbbbbbbbbbbbbbbbbbbbbbb',
                                                               'error_type': None,
                                                               'execution_liveness': {},
                                                               'execution_observation': {'dispatcher_pid': 102,
                                                                                         'execution_id': 'dddddddddddddddddddddddddddddddd',
                                                                                         'execution_kind': 'in_process',
                                                                                         'input_sha256': '6d23a7a66975efd35356848b1f69b848e99c3c76dc5a3740e35328d41c05440a',
                                                                                         'read_only_declared': True,
                                                                                         'registration_sha256': '5f2b1e81954530f31c7d2c83b9c582883b8391190ebe13b69b8bf91f044cb0c3',
                                                                                         'review_target_sha256': None,
                                                                                         'worker_pid': 102},
                                                               'input_hash': '6d23a7a66975efd35356848b1f69b848e99c3c76dc5a3740e35328d41c05440a',
                                                               'latency_s': 0.0,
                                                               'output_hash': 'e7f6c011776e8db7cd330b54174fd76f7d0216b612387a5ffcfb81e6f0919683',
                                                               'semantic_valid': True,
                                                               'status': 'COMPLETED',
                                                               'tool_id': 'synthetic.bounded_sum',
                                                               'tool_version': '1'},
                                            'registration_sha256': '5f2b1e81954530f31c7d2c83b9c582883b8391190ebe13b69b8bf91f044cb0c3',
                                            'schema_version': 'opendot.temporal.dag-result.v1',
                                            'scientific_validity': False,
                                            'seed_ref': {'artifact_id': 'sha256:897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02',
                                                         'integrity_verified': False,
                                                         'mime_type': 'application/json',
                                                         'producer': 'opendot.temporal.dag-seed.v1',
                                                         'schema_version': '1.0.0',
                                                         'sha256': '897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02',
                                                         'size_bytes': 40,
                                                         'source_refs': [],
                                                         'task_id': 'seed',
                                                         'uri': 'artifact://sha256/897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02'},
                                            'workflow_id': 'opendot-dag2-frozen-example-19843079a5da00754ec1b5399962c33874b907eb4d0d6fcf55cd3be2f4dffb63',
                                            'workflow_run_id': '11111111-1111-4111-8111-111111111111'},
                   'original_result_ref': {'artifact_id': 'sha256:adb5d50840b20d03149b27c6867f963736ae54a904658f6239e7e37666489204',
                                           'integrity_verified': False,
                                           'mime_type': 'application/json',
                                           'producer': 'opendot.temporal.dag-result.v1',
                                           'schema_version': '1.0.0',
                                           'sha256': 'adb5d50840b20d03149b27c6867f963736ae54a904658f6239e7e37666489204',
                                           'size_bytes': 2787,
                                           'source_refs': ['sha256:897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02',
                                                           'sha256:ac56ef93531558b0a770c283d0c3ecc1c1b1795468ffe7150065819e5178a07a'],
                                           'task_id': '639ecb03da5d305b5feda86c6b0ac26b446ce803753a11866b206c68f671e77d',
                                           'uri': 'artifact://sha256/adb5d50840b20d03149b27c6867f963736ae54a904658f6239e7e37666489204'},
                   'output_bytes': '6',
                   'output_sha256': 'e7f6c011776e8db7cd330b54174fd76f7d0216b612387a5ffcfb81e6f0919683'}}}

# These contract values and selected outcomes are frozen independently of candidate code.
PLAN = '19843079a5da00754ec1b5399962c33874b907eb4d0d6fcf55cd3be2f4dffb63'
SOURCE_PIN = 'a97dadac88bed7b09d2398516617216cb865ae97db411c12b72de01d7a78d1cb'
REGISTRATION = '5f2b1e81954530f31c7d2c83b9c582883b8391190ebe13b69b8bf91f044cb0c3'
SEED_PIN = '897841afede3356db4d2763258fc87970f590343a6584db91183922fb63c8b02'
RUN_ID = '11111111-1111-4111-8111-111111111111'
MISSION = 'frozen-example'
WF_ID = 'opendot-dag2-frozen-example-' + PLAN
NAMESPACE = QUEUE = 'synthetic'
EFFECT_A = 'sha256:85b56651dc0114baa5ad1068d538337dffa6848ecfb892e782f53006d9f5ba24'
EFFECT_B = 'sha256:639ecb03da5d305b5feda86c6b0ac26b446ce803753a11866b206c68f671e77d'
SEED = FROZEN['seed_ref']
RESOURCE_LIMITS = {'execute_limit': 2, 'normal_inspect_limit': 2,
                   'reconcile_inspect_limit': 2, 'activity_command_limit': 6,
                   'result_bytes_reserved': 32768}
STATE_FIELDS = set('schema_version profile mission_id plan_sha256 seed_ref namespace workflow_id run_id revision mission_status admission_closed cancel_requested deadline_unix_ms nodes resources termination_status external_effect_authenticity scientific_validity device_control_authority independent_review owner_integration'.split())
NODE_FIELDS = set('effect_id status execute_reserved normal_inspect_reserved reconcile_inspect_reserved inspect_reserved candidate_result_ref accepted_result_ref parent_result_ref reason_code'.split())
INSPECTION_FIELDS = set('schema_version effect_id mode expected_revision status reason_code result_ref input_payload_sha256 output original_evidence_sha256'.split())
UPDATE_FIELDS = set('schema_version node_id effect_id status reason_code revision mission_status accepted_result_ref'.split())
# Exact published revision traces from ADR 008 section 6; no candidate-generated expected values.
NORMAL_REVISIONS = (1, 2, 3, 4, 5, 6, 7, 8, 9)
EXECUTION_UNKNOWN_REVISIONS = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10)
NORMAL_INSPECTION_UNKNOWN_REVISIONS = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11)
REFUSAL_ORDER = ('CANCELLED', 'OBSERVATION_DEADLINE', 'TERMINAL_CLOSED',
                 'INSPECTION_BUSY', 'STALE_REVISION', 'EFFECT_MISMATCH',
                 'STATE_NOT_UNKNOWN', 'INSPECTION_EXHAUSTED', 'CONFLICTING_CANDIDATE')

class IntSubclass(int):
    pass

class StrSubclass(str):
    pass

class DictSubclass(dict):
    pass

class ControlDenied(RuntimeError):
    pass

# Each negative is applied at a public endpoint, before any I/O or scheduling.
REF_MUTATIONS = [
    ('sha256', 'A' * 64), ('sha256', 'a' * 63), ('sha256', '/private/path'),
    ('artifact_id', 'sha256:' + '0' * 64), ('uri', 'https://example.invalid/result'),
    ('mime_type', 'text/plain'), ('schema_version', '2'),
    ('size_bytes', 0), ('size_bytes', True), ('size_bytes', 40.0),
    ('size_bytes', IntSubclass(40)), ('size_bytes', 16385),
    ('producer', 'foreign'), ('task_id', 'foreign'), ('source_refs', ()),
    ('source_refs', ['sha256:' + '0' * 64]), ('integrity_verified', True),
    ('integrity_verified', 0), ('sha256', StrSubclass(SEED_PIN)),
]
ACTIVITY_INFO_MUTATIONS = [
    *[('attempt', v) for v in (0, 2, True, 1.0, IntSubclass(1), None)],
    *[('is_local', v) for v in (True, 0, None)],
    ('retry_policy', None), ('retry_policy', SimpleNamespace(maximum_attempts=1)),
    *[('retry_policy', RetryPolicy(maximum_attempts=v)) for v in (0, 2, True, 1.0)],
    ('start_to_close_timeout', None), ('start_to_close_timeout', timedelta(seconds=9)),
    ('schedule_to_close_timeout', timedelta(seconds=59)),
    ('namespace', 'foreign'), ('task_queue', 'foreign'),
    ('workflow_id', 'foreign'), ('workflow_run_id', 'foreign'),
    ('activity_id', 'foreign'), ('activity_type', 'foreign'),
]
WORKFLOW_INFO_MUTATIONS = [
    ('attempt', 2), ('attempt', True), ('attempt', 1.0),
    ('retry_policy', None), ('retry_policy', RetryPolicy(maximum_attempts=2)),
    ('retry_policy', RetryPolicy(maximum_attempts=True)),
    ('run_timeout', timedelta(seconds=299)), ('execution_timeout', timedelta(seconds=301)),
    ('workflow_type', 'foreign'), ('workflow_id', 'foreign'),
    ('namespace', ''), ('task_queue', 'queue/foreign'), ('run_id', ''),
    ('first_execution_run_id', 'foreign'), ('original_execution_run_id', 'foreign'),
    ('continued_run_id', 'prior'), ('cron_schedule', '* * * * *'),
    ('parent', SimpleNamespace(workflow_id='parent')),
]
# Mutation -> exact classification (receipt hash defects are never repaired).
RESULT_MUTATIONS = [
    (('receipt_report', 'breaker_state'), 'CLOSED', 'UNRESOLVED'),
    (('receipt_report', 'breaker_state'), 'OPEN', 'UNRESOLVED'),
    (('receipt_report', 'breaker_state'), 'HALF_OPEN', 'UNRESOLVED'),
    (('receipt_report', 'input_hash'), '0' * 64, 'UNRESOLVED'),
    (('receipt_report', 'output_hash'), '0' * 64, 'UNRESOLVED'),
    (('receipt_report', 'output_hash'), None, 'UNRESOLVED'),
    (('input_payload_sha256',), '0' * 64, 'UNRESOLVED'),
    (('workflow_run_id',), 'foreign', 'UNRESOLVED'),
    (('activity_id',), 'dag2-inspect-normal-' + EFFECT_A[7:], 'UNRESOLVED'),
    (('namespace',), 'foreign', 'UNRESOLVED'),
    (('effect_id',), 'sha256:' + '0' * 64, 'UNRESOLVED'),
    (('seed_ref', 'sha256'), '0' * 64, 'UNRESOLVED'),
    (('parent_result_ref',), FROZEN['vectors']['A']['original_result_ref'], 'UNRESOLVED'),
    (('receipt_report', 'attempts'), True, 'UNRESOLVED'),
    (('receipt_report', 'semantic_valid'), 1, 'UNRESOLVED'),
    (('receipt_report', 'execution_observation', 'input_sha256'), '0' * 64, 'UNRESOLVED'),
    (('receipt_report', 'execution_observation', 'registration_sha256'), '0' * 64, 'UNRESOLVED'),
    (('receipt_report', 'execution_observation', 'worker_pid'), True, 'UNRESOLVED'),
    (('receipt_report', 'execution_observation', 'execution_id'), 'forged', 'UNRESOLVED'),
    (('receipt_report', 'execution_observation', 'execution_kind'), 'external', 'UNRESOLVED'),
    (('receipt_report', 'execution_observation', 'read_only_declared'), False, 'UNRESOLVED'),
    (('receipt_report', 'execution_observation'), None, 'UNRESOLVED'),
    (('receipt_report', 'execution_liveness'), {'termination_observed': True}, 'UNRESOLVED'),
    (('receipt_report', 'execution_liveness'), {'timed_out': False}, 'UNRESOLVED'),
    (('receipt_report', 'execution_liveness'), {'unknown': False}, 'UNRESOLVED'),
    (('receipt_report', 'error_type'), 'TimeoutError', 'UNRESOLVED'),
    (('scientific_validity',), True, 'UNRESOLVED'),
    (('device_control_authority',), True, 'UNRESOLVED'),
    (('owner_integration',), 'PASSED', 'UNRESOLVED'),
]
# Frozen lifecycle/uncertainty outcomes used by public Workflow tests below.
WORKFLOW_ORACLES = {
    'normal': ('COMPLETED', 9, (2, 2, 0, 4)),
    'reconcile_execution_unknown': ('COMPLETED', 10, (2, 1, 1, 4)),
    'reconcile_inspection_unknown': ('COMPLETED', 11, (2, 2, 1, 5)),
    'two_reconciliations': ('COMPLETED', 13, (2, 2, 2, 6)),
    'unknown_deadline': ('STOPPED_WITH_UNKNOWN', 5, (1, 0, 0, 1)),
    'inspection_deadline': ('STOPPED_WITH_UNKNOWN', 6, (1, 1, 0, 2)),
    'reconcile_unresolved': ('STOPPED_WITH_UNKNOWN', 6, (1, 0, 1, 2)),
    'cancel_before': ('STOPPED_WITH_UNKNOWN', 2, (0, 0, 0, 0)),
    'cancel_execution_return': ('STOPPED_WITH_UNKNOWN', 4, (1, 0, 0, 1)),
    'cancel_inspection_return': ('STOPPED_WITH_UNKNOWN', 5, (1, 1, 0, 2)),
    'cancel_reconciliation_return': ('STOPPED_WITH_UNKNOWN', 6, (1, 0, 1, 2)),
}

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def wire(ref):
    return {**asdict(ref), 'source_refs': list(ref.source_refs), 'integrity_verified': False}


def artifact(row):
    return ArtifactRef(**{**row, 'source_refs': tuple(row['source_refs'])})


def effect(node, parent=None):
    return 'sha256:' + digest({'schema_version': 'opendot.effect.v1',
        'namespace': NAMESPACE, 'workflow_id': WF_ID, 'plan_sha256': PLAN,
        'node_id': node, 'parent_result_sha256': None if parent is None else parent['sha256']})


def start_request():
    return {'schema_version': 'opendot.temporal.dag-start.v1', 'mission_id': MISSION,
            'plan_sha256': PLAN, 'seed_ref': copy.deepcopy(SEED)}


def step_request(node='A', parent=None):
    return {'schema_version': 'opendot.temporal.dag-step.v1', 'mission_id': MISSION,
        'plan_sha256': PLAN, 'node_id': node, 'effect_id': effect(node, parent),
        'seed_ref': copy.deepcopy(SEED), 'parent_result_ref': copy.deepcopy(parent)}


def inspect_request(node='A', parent=None, candidate=None, mode='normal', revision=4,
                    origin=None):
    row = step_request(node, parent)
    row.update(schema_version='opendot.temporal.dag-inspect.v1',
               candidate_result_ref=copy.deepcopy(candidate or FROZEN['vectors'][node]['original_result_ref']),
               mode=mode, expected_revision=revision,
               original_evidence_sha256=digest(origin) if origin is not None else None,
               original_result_sha256=origin['original_result_ref']['sha256'] if origin is not None else None)
    return row


def update_request(state, node='A', candidate=None, origin=None):
    candidate = candidate or FROZEN['vectors'][node]['original_result_ref']
    origin = origin or FROZEN['vectors'][node]['original_origin_record']
    return {'schema_version': 'opendot.temporal.dag-reconcile.v1', 'node_id': node,
        'effect_id': state['nodes'][node]['effect_id'], 'expected_revision': state['revision'],
        'candidate_result_ref': copy.deepcopy(candidate), 'original_evidence_sha256': digest(origin),
        'original_result_sha256': origin['original_result_ref']['sha256']}


def origin_record(node, ref, parent=None):
    return {'schema_version': 'opendot.temporal.dag-origin.v1',
        'origin_kind': 'trusted-single-operator-synthetic-put-observer',
        'capture_phase': 'original_put_return_before_response', 'mission_id': MISSION,
        'plan_sha256': PLAN, 'node_id': node, 'effect_id': effect(node, parent),
        'namespace': NAMESPACE, 'workflow_id': WF_ID, 'workflow_run_id': RUN_ID,
        'execution_activity_id': 'dag2-execute-' + effect(node, parent)[7:],
        'original_result_ref': copy.deepcopy(ref)}


def inspection_response(request, status='CONSISTENT_COMPLETED', reason=None):
    if reason is None:
        reason = {'CONSISTENT_COMPLETED': 'RESULT_VERIFIED',
                  'CONSISTENT_REJECTED': 'OUTPUT_REJECTED', 'UNRESOLVED': 'RESULT_INVALID'}[status]
    return {'schema_version': 'opendot.temporal.dag-inspection.v1',
        'effect_id': request['effect_id'], 'mode': request['mode'],
        'expected_revision': request['expected_revision'], 'status': status, 'reason_code': reason,
        'result_ref': copy.deepcopy(request['candidate_result_ref']),
        'input_payload_sha256': FROZEN['vectors'][request['node_id']]['input_sha256'],
        'output': {'A': 5, 'B': 6}[request['node_id']] if status == 'CONSISTENT_COMPLETED' else None,
        'original_evidence_sha256': request['original_evidence_sha256']}


def replace_path(row, path, value):
    for part in path[:-1]:
        row = row[part]
    row[path[-1]] = copy.deepcopy(value)


@pytest.fixture
def rig(tmp_path, monkeypatch):
    def build(*, handler=None, grants=frozenset({'synthetic:read'}), origins=None,
              runtime_options=None, fail_delivery=False):
        counts = {'get': [], 'put': [], 'execute': [], 'handler': []}
        observed = {}
        runtime = ToolRuntime(**(runtime_options or {}))
        def counted(payload):
            counts['handler'].append(copy.deepcopy(payload))
            return (handler or activity_module.bounded_sum)(payload)
        runtime.register(activity_module.SYNTHETIC_SPEC, counted)
        store = ArtifactStore(tmp_path / ('cas-' + str(len(list(tmp_path.iterdir())))))
        seed = store.put_bytes(FROZEN['vectors']['A']['input_bytes'].encode(),
                               mime_type='application/json',
                               producer='opendot.temporal.dag-seed.v1', task_id='seed')
        assert wire(seed) == SEED
        original_get, original_put, original_execute = store.get_bytes, store.put_json, runtime.execute
        def get(ref, *, max_bytes=None):
            counts['get'].append((wire(ref), max_bytes))
            assert max_bytes == (256 if ref.producer == 'opendot.temporal.dag-seed.v1' else 16384)
            return original_get(ref, max_bytes=max_bytes)
        def put(value, **kwargs):
            counts['put'].append((copy.deepcopy(value), copy.deepcopy(kwargs)))
            result = original_put(value, **kwargs)
            # Independent observer lives outside adapter state. Capture AFTER the
            # original canonical return and BEFORE one injected delivery failure.
            node = value['node_id']
            original_ref = wire(result)
            assert hashlib.sha256(original_get(result, max_bytes=16384)).hexdigest() == original_ref['sha256']
            observed[node] = origin_record(node, original_ref, value['parent_result_ref'])
            if fail_delivery and node == 'A':
                raise RuntimeError('one bounded post-publication delivery failure')
            return result
        def execute(*args, **kwargs):
            counts['execute'].append((copy.deepcopy(args), copy.deepcopy(kwargs)))
            return original_execute(*args, **kwargs)
        monkeypatch.setattr(store, 'get_bytes', get)
        monkeypatch.setattr(store, 'put_json', put)
        monkeypatch.setattr(runtime, 'execute', execute)
        config = dict(runtime=runtime, store=store, expected_registration_sha256=REGISTRATION,
            expected_handler_source_sha256=SOURCE_PIN, expected_plan_sha256=PLAN,
            expected_seed_sha256=SEED_PIN, granted_permissions=grants,
            expected_namespace=NAMESPACE, expected_task_queue=QUEUE,
            expected_workflow_id=WF_ID, expected_workflow_run_id=RUN_ID,
            original_A=(origins or {}).get('A'), original_B=(origins or {}).get('B'))
        adapter = activity_module.DependentSumActivity(**config)
        def env(request, inspect=False):
            value = ActivityEnvironment()
            value.info = replace(ActivityEnvironment.default_info(),
                activity_type='opendot.synthetic.dependent-inspect.v1' if inspect else 'opendot.synthetic.dependent-step.v1',
                activity_id=('dag2-inspect-' + request['mode'] + '-' if inspect else 'dag2-execute-') + request['effect_id'][7:],
                namespace=NAMESPACE, task_queue=QUEUE, workflow_id=WF_ID, workflow_run_id=RUN_ID,
                retry_policy=RetryPolicy(maximum_attempts=1), start_to_close_timeout=timedelta(seconds=10),
                schedule_to_close_timeout=timedelta(seconds=60))
            return value
        def invoke(request, *, inspector=False, owner=None, info_changes=None):
            context = env(request, inspect=inspector)
            if info_changes:
                context.info = replace(context.info, **info_changes)
            method = (owner or adapter).inspect_result if inspector else (owner or adapter).execute_step
            return context.run(method, request)
        def store_fixture(body):
            # Keep outer candidate metadata valid independently of deliberately
            # mutated body effect/parent fields, so acquired-body tests actually
            # reach the read-only validator rather than request admission.
            node = body['node_id']
            parent = None if node == 'A' else FROZEN['vectors']['A']['original_result_ref']
            return wire(original_put(body, producer='opendot.temporal.dag-result.v1',
                task_id=effect(node, parent)[7:], source_refs=tuple(
                    [SEED['artifact_id']] + ([] if parent is None else [parent['artifact_id']]))))
        return SimpleNamespace(**locals())
    return build


def assert_admission_error(call, category='TemporalDagAdmissionRejected'):
    with pytest.raises(ApplicationError) as caught:
        call()
    assert caught.value.type == category and caught.value.non_retryable is True
    assert set(caught.value.details[0]) == {'phase', 'code'}
    assert 'private' not in str(caught.value)


def test_literal_design_vectors_and_source_pin():
    assert digest(FROZEN['plan']) == PLAN
    assert FROZEN['plan_canonical_bytes'].encode() == canonical(FROZEN['plan'])
    assert workflow_module.DAG_PLAN_SHA256 == PLAN
    assert workflow_module.DAG_HANDLER_SOURCE_SHA256 == SOURCE_PIN
    assert workflow_module.DAG_SEED_SHA256 == SEED_PIN
    assert workflow_module.DAG_INPUT_SHA256 == {node: FROZEN['vectors'][node]['input_sha256'] for node in ('A', 'B')}
    assert workflow_module.DAG_OUTPUT_SHA256 == {node: FROZEN['vectors'][node]['output_sha256'] for node in ('A', 'B')}
    text = Path(activity_module.__file__).read_text()
    nodes = {n.name: n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef)}
    fragment = '\n\n'.join(ast.get_source_segment(text, nodes[name]) for name in
                           ('_validate_payload', 'bounded_sum', 'bounded_sum_valid')) + '\n'
    assert len(fragment.encode()) == 792
    assert hashlib.sha256(fragment.encode()).hexdigest() == SOURCE_PIN
    assert activity_module.REGISTRATION_SHA256 == REGISTRATION
    assert workflow_module.dag_workflow_id(MISSION) == WF_ID
    for node in ('A', 'B'):
        vector = FROZEN['vectors'][node]
        parent = None if node == 'A' else FROZEN['vectors']['A']['original_result_ref']
        assert workflow_module.dag_effect_id(namespace=NAMESPACE, workflow_id=WF_ID,
            node_id=node, parent_result_sha256=None if parent is None else parent['sha256']) == vector['effect_id']
        assert effect(node, parent) == vector['effect_id']
        assert hashlib.sha256(vector['input_bytes'].encode()).hexdigest() == vector['input_sha256']
        assert hashlib.sha256(vector['output_bytes'].encode()).hexdigest() == vector['output_sha256']
        assert digest(vector['original_result_body']) == vector['original_result_ref']['sha256']
        assert len(canonical(vector['original_result_body'])) == vector['original_result_ref']['size_bytes']
        assert digest(vector['original_origin_record']) == vector['origin_evidence_sha256']


@pytest.mark.parametrize('inspector', [False, True])
@pytest.mark.parametrize('field,value', ACTIVITY_INFO_MUTATIONS)
def test_activity_actual_info_refuses_before_io(rig, inspector, field, value):
    r = rig(); request = inspect_request() if inspector else step_request()
    assert_admission_error(lambda: r.invoke(request, inspector=inspector, info_changes={field: value}))
    assert all(not value for value in r.counts.values())


@pytest.mark.parametrize('inspector', [False, True])
@pytest.mark.parametrize('field,value', REF_MUTATIONS)
def test_activity_seed_wire_refuses_before_io(rig, inspector, field, value):
    r = rig(); request = inspect_request() if inspector else step_request()
    request['seed_ref'][field] = value
    assert_admission_error(lambda: r.invoke(request, inspector=inspector))
    assert all(not value for value in r.counts.values())


@pytest.mark.parametrize('inspector', [False, True])
@pytest.mark.parametrize('field,value', [
    ('schema_version', 'wrong'), ('mission_id', '../private'), ('mission_id', StrSubclass(MISSION)),
    ('plan_sha256', '0' * 64), ('node_id', 'C'), ('node_id', True),
    ('effect_id', 'sha256:' + '0' * 64), ('parent_result_ref', SEED),
    ('approval_token', 'private-token'), ('granted_permissions', ['synthetic:read']),
    ('retry_policy', {'maximum_attempts': 1}), ('workflow_run_id', RUN_ID), ('output', 5),
])
def test_activity_shapes_authority_and_bindings_refuse_before_io(rig, inspector, field, value):
    r = rig(); request = inspect_request() if inspector else step_request()
    request[field] = value
    # Build valid SDK context independently from malformed request's effect/node.
    context = r.env(inspect_request() if inspector else step_request(), inspect=inspector)
    method = r.adapter.inspect_result if inspector else r.adapter.execute_step
    assert_admission_error(lambda: context.run(method, request))
    assert all(not value for value in r.counts.values())


@pytest.mark.parametrize('inspector', [False, True])
@pytest.mark.parametrize('missing', ['schema_version', 'mission_id', 'plan_sha256', 'node_id', 'effect_id', 'seed_ref', 'parent_result_ref'])
def test_activity_missing_fields_before_io(rig, inspector, missing):
    r = rig(); original = inspect_request() if inspector else step_request(); request = copy.deepcopy(original)
    request.pop(missing)
    context = r.env(original, inspect=inspector)
    assert_admission_error(lambda: context.run(r.adapter.inspect_result if inspector else r.adapter.execute_step, request))
    assert all(not value for value in r.counts.values())


@pytest.mark.parametrize('field,value', [('mode', 'automatic'), ('expected_revision', True),
    ('expected_revision', 1.0), ('expected_revision', 0), ('expected_revision', 65),
    ('original_evidence_sha256', 'a' * 64), ('original_result_sha256', 'a' * 64)])
def test_inspect_shape_before_read(rig, field, value):
    r = rig(); request = inspect_request(); request[field] = value
    context = r.env(inspect_request(), inspect=True)
    assert_admission_error(lambda: context.run(r.adapter.inspect_result, request))
    assert all(not value for value in r.counts.values())


@pytest.mark.parametrize('path,value,status', RESULT_MUTATIONS)
def test_inspector_does_not_repair_receipt_or_domain(rig, path, value, status):
    r = rig(); body = copy.deepcopy(FROZEN['vectors']['A']['original_result_body'])
    replace_path(body, path, value)
    candidate = r.store_fixture(body)
    request = inspect_request(candidate=candidate)
    response = r.invoke(request, inspector=True)
    assert set(response) == INSPECTION_FIELDS
    assert response['status'] == status and response['output'] is None
    assert response['result_ref'] == candidate
    assert response['input_payload_sha256'] == SEED_PIN
    assert len(r.counts['get']) == 1
    assert not r.counts['put'] and not r.counts['execute'] and not r.counts['handler']


@pytest.mark.parametrize('mode', ['normal', 'reconcile'])
@pytest.mark.parametrize('node', ['A', 'B'])
def test_frozen_original_inspection_is_read_only(rig, mode, node):
    r = rig(origins={n: copy.deepcopy(FROZEN['vectors'][n]['original_origin_record']) for n in ('A', 'B')})
    for n in ('A', 'B'):
        assert r.store_fixture(FROZEN['vectors'][n]['original_result_body']) == FROZEN['vectors'][n]['original_result_ref']
    parent = FROZEN['vectors']['A']['original_result_ref'] if node == 'B' else None
    request = inspect_request(node, parent, mode=mode,
        origin=FROZEN['vectors'][node]['original_origin_record'] if mode == 'reconcile' else None)
    response = r.invoke(request, inspector=True)
    assert response == inspection_response(request)
    assert len(r.counts['get']) == 1  # Inspector reads only its exact candidate; B execute rereads A.
    assert not r.counts['put'] and not r.counts['execute'] and not r.counts['handler']


@pytest.mark.parametrize('kind', ['null', 'wrong', 'blocked', 'failed'])
def test_consistent_nonpositive_result_is_rejected(rig, kind):
    r = rig(); body = copy.deepcopy(FROZEN['vectors']['A']['original_result_body'])
    receipt = body['receipt_report']
    if kind in ('null', 'wrong'):
        body['output'] = None if kind == 'null' else 7
        receipt['output_hash'] = digest(body['output'])
    else:
        body['output'] = None
        receipt.update(status=kind.upper(), output_hash=None, semantic_valid=False,
                       execution_observation=None, error_type='PermissionDenied' if kind == 'blocked' else 'ValueError')
    request = inspect_request(candidate=r.store_fixture(body))
    response = r.invoke(request, inspector=True)
    assert response['status'] == 'CONSISTENT_REJECTED'
    assert response['reason_code'] == ('OUTPUT_REJECTED' if kind in ('null', 'wrong') else 'TOOL_REJECTED')
    assert response['output'] is None
    assert not r.counts['execute'] and not r.counts['put']


@pytest.mark.parametrize('fault', ['missing', 'corrupt', 'oversized', 'duplicate-json', 'noncanonical'])
def test_result_acquisition_failure_is_unresolved_without_repeat(rig, monkeypatch, fault):
    r = rig(); candidate = copy.deepcopy(FROZEN['vectors']['A']['original_result_ref'])
    if fault == 'missing':
        pass
    elif fault == 'corrupt':
        def read(ref, *, max_bytes):
            r.counts['get'].append((wire(ref), max_bytes)); return b'corrupt'
        monkeypatch.setattr(r.store, 'get_bytes', read)
    elif fault == 'oversized':
        def read(ref, *, max_bytes):
            r.counts['get'].append((wire(ref), max_bytes)); return b'x' * 16385
        monkeypatch.setattr(r.store, 'get_bytes', read)
    else:
        raw = canonical(FROZEN['vectors']['A']['original_result_body'])
        raw = raw[:-1] + b',"output":5}' if fault == 'duplicate-json' else b' ' + raw
        candidate = wire(r.store.put_bytes(raw, mime_type='application/json',
            producer='opendot.temporal.dag-result.v1', task_id=EFFECT_A[7:], source_refs=(SEED['artifact_id'],)))
    response = r.invoke(inspect_request(candidate=candidate), inspector=True)
    assert response['status'] == 'UNRESOLVED'
    assert len(r.counts['get']) == 1
    assert not r.counts['execute'] and not r.counts['put']


@pytest.mark.parametrize('kind', ['absent', 'copied-update-pin', 'alternate-body', 'wrong-output'])
def test_candidate_cannot_supply_its_own_origin(rig, kind):
    original = copy.deepcopy(FROZEN['vectors']['A']['original_origin_record'])
    r = rig(origins={} if kind == 'absent' else {'A': original})
    body = copy.deepcopy(FROZEN['vectors']['A']['original_result_body'])
    if kind in ('alternate-body', 'copied-update-pin'):
        body['receipt_report']['call_id'] = 'f' * 24
    if kind == 'wrong-output':
        body['output'] = 7; body['receipt_report']['output_hash'] = digest(7)
    candidate = r.store_fixture(body)
    candidate_origin = origin_record('A', candidate)
    request = inspect_request(candidate=candidate, mode='reconcile',
                              origin=candidate_origin if kind != 'absent' else original)
    response = r.invoke(request, inspector=True)
    assert response['status'] == 'UNRESOLVED' and response['output'] is None
    assert not r.counts['execute'] and not r.counts['put']


def test_origin_configuration_is_detached_before_update(rig):
    original = copy.deepcopy(FROZEN['vectors']['A']['original_origin_record'])
    r = rig(origins={'A': original})
    r.store_fixture(FROZEN['vectors']['A']['original_result_body'])
    original['original_result_ref']['sha256'] = '0' * 64
    request = inspect_request(mode='reconcile', origin=FROZEN['vectors']['A']['original_origin_record'])
    assert r.invoke(request, inspector=True) == inspection_response(request)


def test_execute_has_one_original_put_and_one_exact_runtime_call(rig):
    r = rig(); response = r.invoke(step_request())
    assert set(response) == {'schema_version', 'effect_id', 'result_ref'}
    assert response['schema_version'] == 'opendot.temporal.dag-step-response.v1'
    assert response['effect_id'] == EFFECT_A
    body = json.loads(r.original_get(artifact(response['result_ref']), max_bytes=16384))
    assert set(body) == set(FROZEN['vectors']['A']['original_result_body'])
    assert body['input_payload_sha256'] == body['receipt_report']['input_hash'] == SEED_PIN
    assert body['output'] == 5 and body['receipt_report']['output_hash'] == FROZEN['vectors']['A']['output_sha256']
    assert body['seed_ref']['integrity_verified'] is response['result_ref']['integrity_verified'] is False
    assert len(r.counts['get']) == len(r.counts['execute']) == len(r.counts['handler']) == len(r.counts['put']) == 1
    assert r.counts['execute'][0] == (('synthetic.bounded_sum', {'left': 2, 'return_null': False, 'right': 3}),
        {'granted_permissions': frozenset({'synthetic:read'}), 'approval_token': None,
         'backoff_base_s': 0.0, 'attempt_limit': 1})
    assert r.observed['A']['original_result_ref'] == response['result_ref']


@pytest.mark.parametrize('kind', ['grant', 'registration', 'guard'])
def test_b_requires_fresh_authority_after_accepted_a(rig, monkeypatch, kind):
    r = rig(runtime_options={'guarded_embedding': True, 'current_context_resolver': lambda: None,
                             'control_error': ControlDenied} if kind == 'guard' else None)
    a = r.invoke(step_request())['result_ref']
    config = {**r.config, 'granted_permissions': frozenset()} if kind == 'grant' else r.config
    if kind == 'guard':
        # Replace trusted guard source through a fresh canonical runtime, never edit its internals.
        guarded = ToolRuntime(guarded_embedding=True, current_context_resolver=lambda: False,
                              control_error=ControlDenied)
        guarded.register(activity_module.SYNTHETIC_SPEC, lambda _: pytest.fail('denied B handler ran'))
        config = {**r.config, 'runtime': guarded}
    owner = activity_module.DependentSumActivity(**config)
    before = {k: len(v) for k, v in r.counts.items()}
    if kind == 'registration':
        monkeypatch.setattr(r.runtime, 'registration_signature', lambda _: '0' * 64)
        assert_admission_error(lambda: r.invoke(step_request('B', a), owner=owner))
        assert {k: len(v) for k, v in r.counts.items()} == before
    elif kind == 'guard':
        with pytest.raises(ControlDenied): r.invoke(step_request('B', a), owner=owner)
        assert len(r.counts['put']) == before['put']
    else:
        b = r.invoke(step_request('B', a), owner=owner)
        inspection = r.invoke(inspect_request('B', a, b['result_ref']), inspector=True)
        assert inspection['status'] == 'CONSISTENT_REJECTED'
        assert len(r.counts['handler']) == 1


def test_original_control_escape_is_not_retried_or_wrapped(rig, monkeypatch):
    r = rig(); marker = ControlDenied('private control detail')
    def denied(*args, **kwargs):
        r.counts['execute'].append((args, kwargs)); raise marker
    monkeypatch.setattr(r.runtime, 'execute', denied)
    with pytest.raises(ControlDenied) as caught: r.invoke(step_request())
    assert caught.value is marker
    assert len(r.counts['execute']) == 1 and not r.counts['put'] and not r.counts['handler']


@pytest.mark.parametrize('kind', ['put', 'response'])
def test_publication_uncertainty_retains_exact_original_once(rig, monkeypatch, kind):
    r = rig(fail_delivery=kind == 'put')
    if kind == 'response':
        original_put = r.store.put_json
        monkeypatch.setattr(r.store, 'put_json', lambda *a, **kw: replace(original_put(*a, **kw), size_bytes=True))
    assert_admission_error(lambda: r.invoke(step_request()),
        'TemporalDagResultStoreFailed' if kind == 'put' else 'TemporalDagResultEncodingFailed')
    assert len(r.counts['execute']) == len(r.counts['handler']) == len(r.counts['put']) == 1
    assert 'A' in r.observed
    retained = r.observed['A']['original_result_ref']
    assert hashlib.sha256(r.original_get(artifact(retained), max_bytes=16384)).hexdigest() == retained['sha256']

# SDK cache-eviction/internal cancellation oracle: preserve ambiguity and reservations,
# re-raise the same CancelledError, and never invent recorded user cancellation.
INTERNAL_CANCEL_ORACLE = {'revision': 3, 'cancel_requested': False,
                         'execute_used': 1, 'activity_commands_used': 1,
                         'commands': 1, 'replacement_commands': 0}


def workflow_info():
    # Construct the exact pinned SDK dataclass only in this finite test double.
    values = {f.name: None for f in fields(workflow.Info)}
    started = datetime.fromtimestamp(1_700_000_000, timezone.utc)
    values.update(attempt=1, continued_run_id=None, cron_schedule=None,
        execution_timeout=timedelta(seconds=300), first_execution_run_id=RUN_ID,
        headers={}, namespace=NAMESPACE, original_execution_run_id=RUN_ID,
        parent=None, root=None, priority=Priority.default, raw_memo={},
        retry_policy=RetryPolicy(maximum_attempts=1), run_id=RUN_ID,
        run_timeout=timedelta(seconds=300), search_attributes={},
        start_time=started, task_queue=QUEUE, task_timeout=timedelta(seconds=10),
        typed_search_attributes=TypedSearchAttributes.empty,
        workflow_id=WF_ID, workflow_start_time=started,
        workflow_type='opendot.synthetic.dependent-sum.v1')
    return workflow.Info(**values)


class WorkflowHarness:
    """No worker/event service: public SDK calls receive completed local Futures.

    A one-shot await hook exposes a deterministic delivery boundary. It never
    creates a pending task, thread, timer, service or polling loop.
    """
    def __init__(self, monkeypatch, *, response=None, info_changes=None):
        self.info = replace(workflow_info(), **(info_changes or {}))
        self.clock = 1_700_000_000.0
        self.cancel_reason = None
        self.handlers_finished = True
        self.owner = workflow_module.DependentSumWorkflow()
        self.commands = []
        self.handles = []
        self.waits = []
        self.paused = []
        self.on_wait = None
        self.on_pause = None
        self.response = response or self.default_response
        monkeypatch.setattr(workflow_module.workflow, 'info', lambda: self.info)
        monkeypatch.setattr(workflow_module.workflow, 'time', lambda: self.clock)
        monkeypatch.setattr(workflow_module.workflow, 'now', lambda: datetime.fromtimestamp(self.clock, timezone.utc))
        monkeypatch.setattr(workflow_module.workflow, 'cancellation_reason', lambda: self.cancel_reason)
        monkeypatch.setattr(workflow_module.workflow, 'all_handlers_finished', lambda: self.handlers_finished)
        monkeypatch.setattr(workflow_module.workflow, 'start_activity', self.start)
        monkeypatch.setattr(workflow_module.workflow, 'wait_condition', self.wait)
        monkeypatch.setattr(workflow_module.workflow, 'execute_activity', self.forbidden)
        monkeypatch.setattr(workflow_module.workflow, 'execute_local_activity', self.forbidden)

    @staticmethod
    def forbidden(*args, **kwargs):
        raise AssertionError('DAG called an unapproved scheduling surface')

    @staticmethod
    def default_response(name, request, options):
        if name == 'opendot.synthetic.dependent-step.v1':
            return {'schema_version': 'opendot.temporal.dag-step-response.v1',
                    'effect_id': request['effect_id'],
                    'result_ref': copy.deepcopy(FROZEN['vectors'][request['node_id']]['original_result_ref'])}
        assert name == 'opendot.synthetic.dependent-inspect.v1'
        return inspection_response(request)

    def start(self, name, request, **options):
        state = self.owner.dag_state()
        assert len(canonical(state)) <= 16384
        self.commands.append((name, copy.deepcopy(request), copy.deepcopy(options), state))
        assert len(self.commands) <= 6
        assert state['resources']['activity_commands_used'] == len(self.commands)
        assert options == {'task_queue': QUEUE,
            'activity_id': ('dag2-execute-' if name.endswith('dependent-step.v1') else 'dag2-inspect-' + request['mode'] + '-') + request['effect_id'][7:],
            'retry_policy': RetryPolicy(maximum_attempts=1),
            'start_to_close_timeout': timedelta(seconds=10),
            'schedule_to_close_timeout': timedelta(seconds=60),
            'cancellation_type': workflow.ActivityCancellationType.TRY_CANCEL}
        result = asyncio.get_running_loop().create_future()
        self.handles.append(result)
        try:
            value = self.response(name, copy.deepcopy(request), options)
            if isinstance(value, BaseException):
                result.set_exception(value)
            else:
                result.set_result(value)
        except BaseException as error:
            result.set_exception(error)
        assert result.done()
        return result

    async def wait(self, predicate, *, timeout=None, **kwargs):
        assert not kwargs or set(kwargs) <= {'timeout_summary'}
        seconds = timeout.total_seconds() if isinstance(timeout, timedelta) else timeout
        assert seconds is not None and 0 <= seconds <= max(0, 1_700_000_300 - self.clock)
        self.waits.append((seconds, self.owner.dag_state()))
        if self.on_wait is not None:
            callback, self.on_wait = self.on_wait, None
            await callback(self)
        if predicate():
            return
        state = self.owner.dag_state()
        if state['mission_status'] == 'PAUSED_UNKNOWN':
            self.paused.append(state)
        if self.on_pause is not None:
            await self.on_pause(self)
            if predicate():
                return
        if self.cancel_reason is not None:
            raise asyncio.CancelledError('controlled recorded cancellation delivery')
        self.clock += seconds
        raise TimeoutError('controlled deterministic deadline')

    def run(self, request=None):
        return asyncio.run(self.owner.run(start_request() if request is None else request))


def assert_state(state, expected):
    mission, revision, usage = WORKFLOW_ORACLES[expected]
    assert set(state) == STATE_FIELDS
    assert state['schema_version'] == 'opendot.temporal.dag-state.v1'
    assert state['profile'] == 'synthetic.dependent_sum.v1'
    assert state['mission_status'] == mission and state['revision'] == revision
    assert state['mission_id'] == MISSION and state['plan_sha256'] == PLAN
    assert state['seed_ref'] == SEED
    assert state['namespace'] == NAMESPACE and state['workflow_id'] == WF_ID and state['run_id'] == RUN_ID
    assert state['deadline_unix_ms'] == 1_700_000_300_000
    resources = state['resources']
    assert set(resources) == set(RESOURCE_LIMITS) | {'execute_used', 'normal_inspect_used', 'reconcile_inspect_used', 'activity_commands_used'}
    assert {key: resources[key] for key in RESOURCE_LIMITS} == RESOURCE_LIMITS
    assert tuple(resources[key] for key in ('execute_used', 'normal_inspect_used', 'reconcile_inspect_used', 'activity_commands_used')) == usage
    assert all(type(value) is int for value in resources.values())
    assert state['termination_status'] == 'NOT_ESTABLISHED'
    assert state['external_effect_authenticity'] == 'NOT_PROVED'
    assert state['scientific_validity'] is state['device_control_authority'] is False
    assert state['independent_review'] == state['owner_integration'] == 'NOT_EVALUATED'
    for node in ('A', 'B'):
        row = state['nodes'][node]
        assert set(row) == NODE_FIELDS
        assert type(row['execute_reserved']) is type(row['normal_inspect_reserved']) is type(row['reconcile_inspect_reserved']) is bool
        assert type(row['inspect_reserved']) is int
        assert row['inspect_reserved'] == row['normal_inspect_reserved'] + row['reconcile_inspect_reserved'] <= 2
    assert len(canonical(state)) <= 16384


def unknown_a(name, request, options):
    if name.endswith('dependent-step.v1') and request['node_id'] == 'A':
        return RuntimeError('synthetic uncertain delivery')
    return WorkflowHarness.default_response(name, request, options)


@pytest.mark.parametrize('field,value', WORKFLOW_INFO_MUTATIONS)
def test_start_checks_actual_workflow_info_before_commands(monkeypatch, field, value):
    h = WorkflowHarness(monkeypatch, info_changes={field: value})
    with pytest.raises(ApplicationError) as caught: h.run()
    assert caught.value.type == 'TemporalDagStartRejected' and caught.value.non_retryable
    assert h.commands == []


@pytest.mark.parametrize('field,value', [
    ('schema_version', 'wrong'), ('mission_id', '../private'), ('mission_id', 'A'),
    ('mission_id', 'a' * 33), ('mission_id', StrSubclass(MISSION)),
    ('plan_sha256', '0' * 64), ('plan', {}), ('approval_token', 'private'),
    ('task_queue', 'foreign'), ('nodes', ['A', 'B']), ('granted_permissions', ['synthetic:read']),
])
def test_start_shape_refuses_before_commands(monkeypatch, field, value):
    h = WorkflowHarness(monkeypatch); request = start_request(); request[field] = value
    with pytest.raises(ApplicationError) as caught: h.run(request)
    assert caught.value.type == 'TemporalDagStartRejected' and caught.value.non_retryable
    assert h.commands == []


@pytest.mark.parametrize('field,value', REF_MUTATIONS)
def test_start_seed_ref_refuses_before_commands(monkeypatch, field, value):
    h = WorkflowHarness(monkeypatch); request = start_request(); request['seed_ref'][field] = value
    with pytest.raises(ApplicationError) as caught: h.run(request)
    assert caught.value.type == 'TemporalDagStartRejected'
    assert h.commands == []


def test_normal_workflow_literal_trace_and_detached_query(monkeypatch):
    h = WorkflowHarness(monkeypatch); state = h.run()
    assert_state(state, 'normal')
    assert [row[0] for row in h.commands] == ['opendot.synthetic.dependent-step.v1',
        'opendot.synthetic.dependent-inspect.v1', 'opendot.synthetic.dependent-step.v1',
        'opendot.synthetic.dependent-inspect.v1']
    assert [row[3]['revision'] for row in h.commands] == [3, 4, 7, 8]
    assert [row[3]['resources']['execute_used'] for row in h.commands] == [1, 1, 2, 2]
    assert [row[3]['resources']['normal_inspect_used'] for row in h.commands] == [0, 1, 1, 2]
    assert state['nodes']['A']['accepted_result_ref'] == FROZEN['vectors']['A']['original_result_ref']
    assert state['nodes']['B']['accepted_result_ref'] == FROZEN['vectors']['B']['original_result_ref']
    assert h.commands[2][1]['parent_result_ref'] == state['nodes']['A']['accepted_result_ref']
    assert state['admission_closed'] is True
    before = h.owner.dag_state()
    detached = h.owner.dag_state(); detached['nodes']['A']['accepted_result_ref']['sha256'] = '0' * 64
    detached['resources']['execute_used'] = 0
    assert h.owner.dag_state() == before


def test_normal_workflow_real_local_counts(rig, monkeypatch):
    r = rig()
    def response(name, request, options):
        return r.invoke(request, inspector=name.endswith('dependent-inspect.v1'))
    h = WorkflowHarness(monkeypatch, response=response); state = h.run()
    assert_state(state, 'normal')
    assert len(r.counts['execute']) == len(r.counts['handler']) == len(r.counts['put']) == 2
    assert r.counts['handler'] == [{'left': 2, 'return_null': False, 'right': 3},
                                    {'left': 5, 'return_null': False, 'right': 1}]
    assert [row[1] for row in r.counts['get']] == [256, 16384, 256, 16384, 16384]
    assert [body['output'] for body, _ in r.counts['put']] == [5, 6]


@pytest.mark.parametrize('status', ['CONSISTENT_REJECTED', 'UNRESOLVED'])
def test_negative_inspection_blocks_b_without_another_execution(monkeypatch, status):
    def response(name, request, options):
        if name.endswith('dependent-inspect.v1'):
            return inspection_response(request, status)
        return WorkflowHarness.default_response(name, request, options)
    h = WorkflowHarness(monkeypatch, response=response); state = h.run()
    assert len(h.commands) == 2 and state['nodes']['B']['execute_reserved'] is False
    assert state['nodes']['A']['accepted_result_ref'] is None
    if status == 'UNRESOLVED':
        assert_state(state, 'inspection_deadline')
    else:
        assert state['mission_status'] == 'REJECTED' and state['revision'] == 5
        assert state['nodes']['B']['reason_code'] == 'DEPENDENCY_REJECTED'
        assert state['resources']['execute_used'] == 1


@pytest.mark.parametrize('kind', ['ordinary', 'encoding', 'store', 'timeout', 'malformed-response'])
def test_execution_uncertainty_never_redispatches(monkeypatch, kind):
    from temporalio.exceptions import TimeoutError as TemporalTimeoutError, TimeoutType
    outcomes = {'ordinary': RuntimeError('private exception'),
        'encoding': ApplicationError('fixed', type='TemporalDagResultEncodingFailed', non_retryable=True),
        'store': ApplicationError('fixed', type='TemporalDagResultStoreFailed', non_retryable=True),
        'timeout': TemporalTimeoutError('fixed', type=TimeoutType.START_TO_CLOSE, last_heartbeat_details=[]),
        'malformed-response': {'schema_version': 'wrong', 'result_ref': {}}}
    h = WorkflowHarness(monkeypatch, response=lambda *args: outcomes[kind]); state = h.run()
    assert_state(state, 'unknown_deadline')
    assert len(h.commands) == 1 and state['nodes']['A']['execute_reserved'] is True
    assert state['nodes']['B']['status'] == 'CANCELLED_BEFORE_ADMISSION'
    assert state['nodes']['B']['reason_code'] == 'OBSERVATION_DEADLINE'
    assert 'private' not in canonical(state).decode()


@pytest.mark.parametrize('failure', ['TemporalDagAdmissionRejected', 'TemporalDagInputRejected'])
def test_known_preruntime_rejection_closes_without_b(monkeypatch, failure):
    detail = ({'phase': 'admission', 'code': 'ADMISSION_REFUSED'}
              if failure == 'TemporalDagAdmissionRejected'
              else {'phase': 'input', 'code': 'INPUT_REFUSED'})
    h = WorkflowHarness(monkeypatch, response=lambda *args: ApplicationError(
        failure, detail, type=failure, non_retryable=True))
    state = h.run()
    assert state['mission_status'] == 'REJECTED' and state['revision'] == 4
    assert state['nodes']['B']['reason_code'] == 'DEPENDENCY_REJECTED'
    assert len(h.commands) == state['resources']['execute_used'] == 1


@pytest.mark.parametrize('field,value', [
    ('schema_version', 'wrong'), ('effect_id', 'sha256:' + '0' * 64), ('mode', 'reconcile'),
    ('expected_revision', True), ('expected_revision', 64), ('status', 'ACCEPTED'),
    ('reason_code', 'TOOL_REJECTED'), ('output', True), ('output', 6),
    ('input_payload_sha256', '0' * 64), ('original_evidence_sha256', 'a' * 64),
    ('result_ref', FROZEN['vectors']['B']['original_result_ref']), ('approval_token', 'private'),
])
def test_whole_inspector_envelope_is_verified_before_acceptance(monkeypatch, field, value):
    def response(name, request, options):
        answer = WorkflowHarness.default_response(name, request, options)
        if name.endswith('dependent-inspect.v1'): answer[field] = value
        return answer
    h = WorkflowHarness(monkeypatch, response=response); state = h.run()
    assert_state(state, 'inspection_deadline')
    assert len(h.commands) == 2 and state['nodes']['A']['accepted_result_ref'] is None


@pytest.mark.parametrize('unknown_stage', ['execute', 'normal_inspect'])
def test_positive_update_literal_trace_no_execute_refund(monkeypatch, unknown_stage):
    updates = []
    def response(name, request, options):
        if request['node_id'] == 'A':
            if unknown_stage == 'execute' and name.endswith('dependent-step.v1'):
                return RuntimeError('uncertain original delivery')
            if unknown_stage == 'normal_inspect' and request.get('mode') == 'normal':
                return RuntimeError('uncertain original inspection')
        return WorkflowHarness.default_response(name, request, options)
    h = WorkflowHarness(monkeypatch, response=response)
    async def update(h):
        snapshot = h.owner.dag_state()
        assert snapshot['revision'] == (4 if unknown_stage == 'execute' else 5)
        before = h.owner.dag_state(); request = update_request(before)
        h.owner.validate_reconcile_result(request)
        assert h.owner.dag_state() == before
        updates.append(await h.owner.reconcile_result(request))
        h.on_pause = None
    h.on_pause = update
    state = h.run()
    assert_state(state, 'reconcile_execution_unknown' if unknown_stage == 'execute' else 'reconcile_inspection_unknown')
    assert len(updates) == 1 and set(updates[0]) == UPDATE_FIELDS
    assert updates[0]['status'] == 'ACCEPTED' and updates[0]['accepted_result_ref'] == FROZEN['vectors']['A']['original_result_ref']
    assert [row[3]['revision'] for row in h.commands] == ([3, 5, 8, 9] if unknown_stage == 'execute' else [3, 4, 6, 9, 10])
    assert sum(name.endswith('dependent-step.v1') and request['node_id'] == 'A' for name, request, _, _ in h.commands) == 1


def test_original_put_observed_before_update_recovers_without_a_redispatch(rig, monkeypatch):
    r = rig(fail_delivery=True)
    inspectors = []
    update_calls = []
    sequence = []
    def response(name, request, options):
        if request.get('mode') == 'reconcile':
            assert inspectors and sequence == ['original-observed', 'inspector-configured', 'update-submitted']
            return r.invoke(request, inspector=True, owner=inspectors[0])
        return r.invoke(request, inspector=name.endswith('dependent-inspect.v1'))
    h = WorkflowHarness(monkeypatch, response=response)
    async def update(h):
        assert h.owner.dag_state()['nodes']['A']['status'] == 'UNKNOWN'
        assert len(r.counts['execute']) == len(r.counts['handler']) == len(r.counts['put']) == 1
        retained = copy.deepcopy(r.observed['A']); sequence.append('original-observed')
        inspectors.append(activity_module.DependentSumActivity(**{**r.config, 'original_A': retained}))
        sequence.append('inspector-configured')
        # Only now is the candidate Update assembled. Its evidence expectation
        # came from the original put observer, not from itself or current CAS.
        request = update_request(h.owner.dag_state(), candidate=retained['original_result_ref'], origin=retained)
        assert retained['original_result_ref']['sha256'] == hashlib.sha256(
            r.original_get(artifact(retained['original_result_ref']), max_bytes=16384)).hexdigest()
        sequence.append('update-submitted')
        update_calls.append(await h.owner.reconcile_result(request))
        h.on_pause = None
    h.on_pause = update
    state = h.run()
    assert_state(state, 'reconcile_execution_unknown')
    assert update_calls[0]['status'] == 'ACCEPTED'
    assert len(r.counts['execute']) == len(r.counts['handler']) == len(r.counts['put']) == 2
    assert [row['left'] for row in r.counts['handler']] == [2, 5]
    assert len(h.commands) == 4


def test_two_normal_failures_use_exact_six_command_ceiling(monkeypatch):
    updates = []
    def response(name, request, options):
        if request.get('mode') == 'normal': return RuntimeError('one uncertain normal inspection')
        return WorkflowHarness.default_response(name, request, options)
    h = WorkflowHarness(monkeypatch, response=response)
    async def update(h):
        state = h.owner.dag_state()
        node = 'A' if state['nodes']['A']['status'] == 'UNKNOWN' else 'B'
        result = await h.owner.reconcile_result(update_request(state, node))
        updates.append(result)
    h.on_pause = update
    state = h.run()
    assert_state(state, 'two_reconciliations')
    assert len(h.commands) == 6
    assert [row[3]['revision'] for row in h.commands] == [3, 4, 6, 9, 10, 12]
    before = h.owner.dag_state()
    refusal = asyncio.run(h.owner.reconcile_result(update_request(before, 'B')))
    assert refusal['status'] == 'REFUSED' and refusal['reason_code'] == 'TERMINAL_CLOSED'
    assert h.owner.dag_state() == before and len(h.commands) == 6


@pytest.mark.parametrize('failure', ['unresolved', 'exception', 'malformed'])
def test_reconciliation_failure_is_sticky_and_allowance_spent(monkeypatch, failure):
    def response(name, request, options):
        if request.get('mode') == 'reconcile':
            if failure == 'unresolved': return inspection_response(request, 'UNRESOLVED')
            if failure == 'exception': return RuntimeError('private detail')
            return {'status': 'CONSISTENT_COMPLETED'}
        return unknown_a(name, request, options)
    h = WorkflowHarness(monkeypatch, response=response); returns = []
    async def update(h):
        request = update_request(h.owner.dag_state())
        returns.append(await h.owner.reconcile_result(request))
        before = h.owner.dag_state()
        repeat = await h.owner.reconcile_result(request)
        assert repeat['status'] == 'REFUSED' and repeat['reason_code'] == 'TERMINAL_CLOSED'
        assert h.owner.dag_state() == before
    h.on_pause = update
    state = h.run()
    assert_state(state, 'reconcile_unresolved')
    assert returns[0]['status'] == 'UNRESOLVED'
    assert state['nodes']['A']['reconcile_inspect_reserved'] is True
    assert len(h.commands) == 2


@pytest.mark.parametrize('field,value', [('schema_version', 'wrong'), ('node_id', 'C'),
    ('node_id', True), ('expected_revision', True), ('expected_revision', 4.0),
    ('expected_revision', 0), ('expected_revision', 65), ('approval_token', 'private'),
    ('granted_permissions', ['synthetic:read']), ('workflow_run_id', RUN_ID),
    ('original_evidence_sha256', None), ('original_result_sha256', None)])
def test_update_validator_shape_is_read_only_and_no_command(monkeypatch, field, value):
    h = WorkflowHarness(monkeypatch, response=unknown_a)
    async def check(h):
        before = h.owner.dag_state(); count = len(h.commands)
        request = update_request(before); request[field] = value
        with pytest.raises(ApplicationError) as caught: h.owner.validate_reconcile_result(request)
        assert caught.value.type == 'TemporalDagUpdateRejected' and caught.value.non_retryable
        assert 'private' not in str(caught.value)
        assert h.owner.dag_state() == before and len(h.commands) == count
        h.on_pause = None
    h.on_pause = check
    assert_state(h.run(), 'unknown_deadline')


@pytest.mark.parametrize('kind,reason', [('stale', 'STALE_REVISION'), ('effect', 'EFFECT_MISMATCH'),
                                       ('state', 'STATE_NOT_UNKNOWN'), ('conflict', 'CONFLICTING_CANDIDATE')])
def test_update_refusals_preserve_exact_state_and_counters(monkeypatch, kind, reason):
    def response(name, request, options):
        if kind == 'conflict' and request.get('mode') == 'normal':
            return RuntimeError('normal inspection unknown with retained candidate')
        return unknown_a(name, request, options) if kind != 'conflict' else WorkflowHarness.default_response(name, request, options)
    h = WorkflowHarness(monkeypatch, response=response)
    async def check(h):
        before = h.owner.dag_state(); count = len(h.commands)
        request = update_request(before)
        if kind == 'stale': request['expected_revision'] -= 1
        elif kind == 'effect': request['effect_id'] = 'sha256:' + '0' * 64
        elif kind == 'state':
            # B has no admitted effect. A stale/effect defect would precede
            # state refusal, so probe A after its accepted transition instead.
            accepted = await h.owner.reconcile_result(request)
            assert accepted['status'] == 'ACCEPTED'
            before = h.owner.dag_state(); count = len(h.commands)
            request = update_request(before)
        else:
            replacement = copy.deepcopy(request['candidate_result_ref']); replacement['sha256'] = '0' * 64
            replacement['artifact_id'] = 'sha256:' + '0' * 64
            replacement['uri'] = 'artifact://sha256/' + '0' * 64
            request['candidate_result_ref'] = replacement
            request['original_result_sha256'] = replacement['sha256']
        result = await h.owner.reconcile_result(request)
        assert result['status'] == 'REFUSED' and result['reason_code'] == reason
        assert h.owner.dag_state() == before and len(h.commands) == count
        h.on_pause = None
    h.on_pause = check
    state = h.run()
    assert_state(state, 'reconcile_execution_unknown' if kind == 'state' else
                 'inspection_deadline' if kind == 'conflict' else 'unknown_deadline')


@pytest.mark.parametrize('stage', ['normal', 'reconcile'])
def test_competing_update_is_busy_without_a_second_reservation(monkeypatch, stage):
    h = WorkflowHarness(monkeypatch, response=unknown_a if stage == 'reconcile' else None)
    checked = []
    async def competing(h):
        before = h.owner.dag_state()
        if before['nodes']['A']['status'] != 'VERIFYING':
            h.on_wait = competing
            return
        request = update_request(before)
        # Even a stale revision must lose to INSPECTION_BUSY.
        request['expected_revision'] = max(1, before['revision'] - 1)
        commands = len(h.commands)
        result = await h.owner.reconcile_result(request)
        assert result['status'] == 'REFUSED' and result['reason_code'] == 'INSPECTION_BUSY'
        assert h.owner.dag_state() == before and len(h.commands) == commands
        checked.append(result)
    if stage == 'normal':
        h.on_wait = competing
    else:
        async def update(h):
            request = update_request(h.owner.dag_state())
            h.on_wait = competing
            assert (await h.owner.reconcile_result(request))['status'] == 'ACCEPTED'
            h.on_pause = None
        h.on_pause = update
    state = h.run()
    assert len(checked) == 1
    assert_state(state, 'normal' if stage == 'normal' else 'reconcile_execution_unknown')


@pytest.mark.parametrize('reason', ['', 'operator stop'])
def test_recorded_cancellation_before_admission_has_zero_commands(monkeypatch, reason):
    h = WorkflowHarness(monkeypatch); h.cancel_reason = reason
    state = h.run()
    assert_state(state, 'cancel_before')
    assert state['cancel_requested'] is state['admission_closed'] is True
    assert all(state['nodes'][node]['status'] == 'CANCELLED_BEFORE_ADMISSION' for node in ('A', 'B'))
    assert h.commands == []
    before = h.owner.dag_state()
    result = asyncio.run(h.owner.reconcile_result(update_request(before)))
    assert result['reason_code'] == 'CANCELLED' and result['status'] == 'REFUSED'
    assert h.owner.dag_state() == before


@pytest.mark.parametrize('stage,target,oracle', [
    ('execution', 1, 'cancel_execution_return'), ('normal', 2, 'cancel_inspection_return'),
    ('reconciliation', 2, 'cancel_reconciliation_return')])
def test_empty_recorded_cancel_fences_completed_activity_before_acceptance(monkeypatch, stage, target, oracle):
    h = WorkflowHarness(monkeypatch, response=unknown_a if stage == 'reconciliation' else None)
    results = []
    async def cancel(h):
        if len(h.commands) < target:
            h.on_wait = cancel; return
        assert h.owner.dag_state()['cancel_requested'] is False
        h.cancel_reason = ''
    if stage != 'reconciliation':
        h.on_wait = cancel
    else:
        async def update(h):
            request = update_request(h.owner.dag_state())
            h.on_wait = cancel
            results.append(await h.owner.reconcile_result(request))
            h.on_pause = None
        h.on_pause = update
    state = h.run()
    assert_state(state, oracle)
    assert state['cancel_requested'] is state['admission_closed'] is True
    assert state['nodes']['A']['accepted_result_ref'] is None
    assert state['nodes']['B']['execute_reserved'] is False
    assert len(h.commands) == target
    if results:
        assert results[0]['accepted_result_ref'] is None
        assert results[0]['status'] != 'ACCEPTED'


def test_validator_empty_cancel_is_read_only_handler_closes_synchronously(monkeypatch):
    h = WorkflowHarness(monkeypatch, response=unknown_a)
    async def check(h):
        before = h.owner.dag_state(); request = update_request(before)
        assert before['revision'] == 4 and before['cancel_requested'] is False
        h.cancel_reason = ''
        with pytest.raises(ApplicationError) as caught: h.owner.validate_reconcile_result(request)
        assert caught.value.type == 'TemporalDagUpdateRejected'
        assert h.owner.dag_state() == before
        result = await h.owner.reconcile_result(request)
        assert result['status'] == 'REFUSED' and result['reason_code'] == 'CANCELLED'
        after = h.owner.dag_state()
        assert after['revision'] == 5 and after['cancel_requested'] is True
        assert after['mission_status'] == 'STOPPED_WITH_UNKNOWN'
        assert len(h.commands) == 1
        assert (await h.owner.reconcile_result(request))['reason_code'] == 'CANCELLED'
        assert h.owner.dag_state() == after
        h.on_pause = None
    h.on_pause = check
    state = h.run()
    assert state['revision'] == 5 and len(h.commands) == 1


@pytest.mark.parametrize('stage', ['normal', 'reconcile'])
def test_deadline_fences_late_valid_inspector_response(monkeypatch, stage):
    h = WorkflowHarness(monkeypatch, response=unknown_a if stage == 'reconcile' else None)
    results = []
    async def deadline(h):
        if len(h.commands) < 2:
            h.on_wait = deadline; return
        h.clock = 1_700_000_300
    if stage == 'normal':
        h.on_wait = deadline
    else:
        async def update(h):
            h.on_wait = deadline
            results.append(await h.owner.reconcile_result(update_request(h.owner.dag_state())))
            h.on_pause = None
        h.on_pause = update
    state = h.run()
    assert state['mission_status'] == 'STOPPED_WITH_UNKNOWN'
    assert state['nodes']['A']['accepted_result_ref'] is None
    assert state['nodes']['B']['execute_reserved'] is False
    assert state['revision'] == (5 if stage == 'normal' else 6)
    assert len(h.commands) == 2 and state['resources']['execute_used'] == 1
    assert all(result['accepted_result_ref'] is None for result in results)


@pytest.mark.parametrize('remaining', [0, 0.25, 1, 10])
def test_unfinished_handler_drain_fails_within_remaining_deadline(monkeypatch, remaining):
    h = WorkflowHarness(monkeypatch, response=unknown_a)
    async def close(h):
        h.clock = 1_700_000_300 - remaining
        h.handlers_finished = False
        h.cancel_reason = ''
        h.on_pause = None
    h.on_pause = close
    with pytest.raises(ApplicationError) as caught: h.run()
    assert caught.value.type == 'DAG_HANDLERS_UNFINISHED' and caught.value.non_retryable is True
    assert any(isinstance(detail, dict) and detail.get('mission_status') == 'STOPPED_WITH_UNKNOWN'
               for detail in caught.value.details)
    assert h.owner.dag_state()['mission_status'] == 'STOPPED_WITH_UNKNOWN'
    assert h.clock <= 1_700_000_300
    # A drain can never extend 300s to 301s. The paused wait is distinct.
    drain = [seconds for seconds, state in h.waits if state['mission_status'] == 'STOPPED_WITH_UNKNOWN']
    assert all(seconds <= min(1, remaining) for seconds in drain)
    assert not drain if remaining == 0 else len(drain) == 1
    assert len(h.commands) == 1


def test_terminal_drain_observes_finished_update_without_new_effect(monkeypatch):
    h = WorkflowHarness(monkeypatch); h.handlers_finished = False
    async def finish(h):
        if h.owner.dag_state()['mission_status'] != 'COMPLETED':
            h.on_wait = finish; return
        h.handlers_finished = True
    h.on_wait = finish
    state = h.run()
    assert_state(state, 'normal')
    assert len(h.commands) == 4 and h.handlers_finished
    assert h.waits[-1][0] <= 1


def test_internal_cancel_propagates_unchanged_without_false_terminal_or_redispatch(monkeypatch):
    marker = asyncio.CancelledError('internal reconstruction, not recorded user cancellation')
    h = WorkflowHarness(monkeypatch, response=lambda *args: marker)
    with pytest.raises(asyncio.CancelledError) as caught: h.run()
    assert caught.value is marker
    state = h.owner.dag_state()
    assert state['revision'] == INTERNAL_CANCEL_ORACLE['revision']
    assert state['cancel_requested'] is INTERNAL_CANCEL_ORACLE['cancel_requested']
    assert state['resources']['execute_used'] == INTERNAL_CANCEL_ORACLE['execute_used']
    assert state['resources']['activity_commands_used'] == INTERNAL_CANCEL_ORACLE['activity_commands_used']
    assert len(h.commands) == INTERNAL_CANCEL_ORACLE['commands']


def test_finite_decision_reconstruction_preserves_commands_refs_and_reservations(monkeypatch):
    # Two independently initialized deterministic decisions consume identical
    # recorded choices. No runtime/CAS is available in this finite oracle.
    first = WorkflowHarness(monkeypatch); result = first.run()
    recorded = [(name, request, options, state) for name, request, options, state in first.commands]
    second = WorkflowHarness(monkeypatch); reconstructed = second.run()
    assert reconstructed == result
    assert second.commands == recorded
    assert second.commands[0][2]['activity_id'] == 'dag2-execute-' + EFFECT_A[7:]
    assert sum(request['node_id'] == 'A' and name.endswith('dependent-step.v1')
               for name, request, _, _ in second.commands) == 1


def test_default_converter_preserves_all_fixed_envelopes(rig, monkeypatch):
    r = rig(); request = step_request(); response = r.invoke(request)
    inspection = inspect_request(candidate=response['result_ref'])
    inspected = r.invoke(inspection, inspector=True)
    h = WorkflowHarness(monkeypatch); state = h.run()
    update = update_request(state)
    values = [start_request(), request, response, inspection, inspected, update, state]
    async def convert():
        payloads = await DataConverter.default.encode(values)
        return await DataConverter.default.decode(payloads, [dict[str, Any]] * len(values))
    assert asyncio.run(convert()) == values
    for cls, method in ((activity_module.DependentSumActivity, 'execute_step'),
                        (activity_module.DependentSumActivity, 'inspect_result'),
                        (workflow_module.DependentSumWorkflow, 'run'),
                        (workflow_module.DependentSumWorkflow, 'reconcile_result')):
        annotations = get_type_hints(getattr(cls, method))
        assert annotations['request'] == dict[str, Any] and annotations['return'] == dict[str, Any]


@pytest.mark.parametrize('uppercase', ['CLOSED', 'OPEN', 'HALF_OPEN'])
def test_uppercase_breaker_members_have_no_compatibility_fallback(rig, uppercase):
    r = rig(); body = copy.deepcopy(FROZEN['vectors']['A']['original_result_body'])
    body['receipt_report']['breaker_state'] = uppercase
    response = r.invoke(inspect_request(candidate=r.store_fixture(body)), inspector=True)
    assert response['status'] == 'UNRESOLVED' and response['reason_code'] == 'RESULT_INVALID'
    assert response['output'] is None and len(r.counts['get']) == 1
    assert not r.counts['execute'] and not r.counts['handler'] and not r.counts['put']


def test_internal_cancellation_during_terminal_drain_is_not_abandonment_failure(monkeypatch):
    marker = asyncio.CancelledError('internal drain cancellation without recorded user cancel')
    h = WorkflowHarness(monkeypatch); h.handlers_finished = False
    before = []
    async def cancel_drain(h):
        state = h.owner.dag_state()
        if state['mission_status'] != 'COMPLETED':
            h.on_wait = cancel_drain
            return
        assert h.cancel_reason is None and state['cancel_requested'] is False
        assert h.clock < state['deadline_unix_ms'] / 1000
        before.append(state)
        raise marker
    h.on_wait = cancel_drain
    with pytest.raises(asyncio.CancelledError) as caught: h.run()
    assert caught.value is marker
    assert len(before) == 1 and h.owner.dag_state() == before[0]
    assert_state(h.owner.dag_state(), 'normal')
    assert len(h.commands) == 4


@pytest.mark.parametrize('failure', ['TemporalDagAdmissionRejected', 'TemporalDagInputRejected'])
@pytest.mark.parametrize('defect', ['type-only', 'wrong-detail', 'retryable'])
def test_preruntime_type_label_alone_never_establishes_known_rejection(monkeypatch, failure, defect):
    detail = ({'phase': 'admission', 'code': 'ADMISSION_REFUSED'}
              if failure == 'TemporalDagAdmissionRejected'
              else {'phase': 'input', 'code': 'INPUT_REFUSED'})
    if defect == 'type-only':
        error = ApplicationError(failure, type=failure, non_retryable=True)
    elif defect == 'wrong-detail':
        error = ApplicationError(failure, {'phase': 'other', 'code': 'OTHER'},
                                 type=failure, non_retryable=True)
    else:
        error = ApplicationError(failure, detail, type=failure, non_retryable=False)
    h = WorkflowHarness(monkeypatch, response=lambda *args: error)
    state = h.run()
    assert_state(state, 'unknown_deadline')
    assert len(h.commands) == 1 and state['nodes']['A']['accepted_result_ref'] is None
    assert state['nodes']['B']['execute_reserved'] is False


@pytest.mark.parametrize('closure', ['cancel', 'deadline'])
def test_successful_terminal_drain_return_is_fenced_before_reporting(monkeypatch, closure):
    h = WorkflowHarness(monkeypatch); h.handlers_finished = False
    before = []
    async def finish_and_close(h):
        state = h.owner.dag_state()
        if state['mission_status'] != 'COMPLETED':
            if closure == 'deadline' and state['nodes']['B']['status'] == 'VERIFYING':
                # B can be accepted with 0.25s still inside the original budget.
                h.clock = 1_700_000_299.75
            h.on_wait = finish_and_close
            return
        assert state['revision'] == 9 and state['cancel_requested'] is False
        before.append(state)
        h.handlers_finished = True
        if closure == 'cancel':
            h.cancel_reason = ''
        else:
            assert h.cancel_reason is None
            h.clock = 1_700_000_300
    h.on_wait = finish_and_close
    state = h.run()
    assert len(before) == 1
    assert state['mission_status'] == 'STOPPED_WITH_UNKNOWN' and state['revision'] == 10
    assert state['cancel_requested'] is (closure == 'cancel')
    assert state['admission_closed'] is True
    assert state['nodes'] == before[0]['nodes']
    assert all(state['nodes'][node]['status'] == 'ACCEPTED' for node in ('A', 'B'))
    assert state['resources'] == {**RESOURCE_LIMITS, 'execute_used': 2,
        'normal_inspect_used': 2, 'reconcile_inspect_used': 0, 'activity_commands_used': 4}
    assert state['termination_status'] == 'NOT_ESTABLISHED'
    assert len(h.commands) == 4
    # Reobserving the same public closure through the handler is idempotent.
    request = update_request(state)
    for _ in range(2):
        refusal = asyncio.run(h.owner.reconcile_result(request))
        assert refusal['status'] == 'REFUSED'
        assert refusal['reason_code'] == ('CANCELLED' if closure == 'cancel' else 'OBSERVATION_DEADLINE')
        assert h.owner.dag_state() == state and len(h.commands) == 4


def test_default_sdk_sandbox_prepares_fixed_workflow_without_service():
    """Pinned Worker preparation path only; no activation, Worker or service.

    This qualifies default sandbox import/definition preparation separately
    from ActivityEnvironment and command-fake behavior. It is not history
    replay, Worker delivery, persistence, deployment or server evidence.
    """
    from importlib.metadata import version
    from temporalio.worker.workflow_sandbox import SandboxRestrictions, SandboxedWorkflowRunner

    assert version('temporalio') == '1.34.0'
    # The public runner accepts the SDK definition object. Its pinned private
    # retrieval is test-only; production adapters never use SDK private APIs.
    definition = workflow._Definition.must_from_class(workflow_module.DependentSumWorkflow)
    assert definition.name == 'opendot.synthetic.dependent-sum.v1'
    assert definition.sandboxed is True
    assert definition.cls is workflow_module.DependentSumWorkflow
    assert definition.run_fn is workflow_module.DependentSumWorkflow.run
    assert set(definition.queries) == {'dag_state'}
    assert set(definition.updates) == {'reconcile_result'}
    assert not definition.signals
    runner = SandboxedWorkflowRunner()
    assert runner.restrictions is SandboxRestrictions.default

    async def prepare():
        # SDK 1.34.0's in-sandbox instance preparation needs a running loop,
        # but performs no activation or Activity scheduling in this call.
        assert runner.prepare_workflow(definition) is None

    asyncio.run(prepare())
