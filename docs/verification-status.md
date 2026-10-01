# Verification status

This historical record covers the bounded standalone `0.1.0a0` adapter source cut, not a complete
engineering MVP. The following local checks were performed on 2026-09-30 using
CPython 3.12.14 on Linux, with pytest 9.1.1. Historical full-suite and native
results are not carried forward as results for this cut.

## Executed checks

| Check | Result | Boundary |
| --- | --- | --- |
| Source path and attribution review | PASS | Exactly 45 selected source paths; complete LICENSE retained byte-for-byte; copyright retained |
| Static Python parsing | PASS | Retained Python files parse; adapter algorithms unchanged |
| Reviewed portable test selection | 350 passed, 0 failed, 0 skipped | 92 explicitly selected function nodes across eight retained files; not the full suite |
| Fresh wheel build | PASS | `opendot-engineering` 0.1.0a0; no runtime dependency or console-script registration |
| Clean virtual-environment import smoke | PASS | Only this distribution installed; isolated imports resolve to the wheel and load only standard-library/package modules |
| Installed source-audit fixture | PASS | Fixed published synthetic manifest pin; `audit_accepted=true`, `scientific_accepted=false` |
| Installed qualification fixture | PASS | Fixed published synthetic manifest pin; oracle contract passed; scientific/device-control/real-device flags remain false |

Portable case counts by file:

| File | Executed cases |
| --- | ---: |
| `tests/test_source_audit.py` | 86 |
| `tests/test_lab_qualification.py` | 94 |
| `tests/test_ci_summary.py` | 2 |
| `tests/test_geometry.py` | 25 |
| `tests/test_gmsh_mesh.py` | 44 |
| `tests/test_thermal_conduction.py` | 25 |
| `tests/test_thermal_source.py` | 46 |
| `tests/test_structural_beam.py` | 28 |

## Deliberately not run

- Native build123d/CadQuery geometry, Gmsh mesh generation, and CalculiX solves
- Native/preserved-pack integration fixtures and their dependent mutation tests
- Actual process-lifetime tests in structural and thermal modules
- Gmsh's existing-output test, whose implementation can inspect enclosing Git provenance
- Model/agent execution, physical-device control, scientific qualification, multi-host execution, or runtime recovery
- Hosted CI, registry publication, or native/backend installation

Excluded cases were never selected, so they do not appear as pytest skips. The
five isolated-Python import/CLI smoke tests and synthetic fake-Gmsh tests were
included; they did not invoke native CAD or solvers. Test-generated artifacts
and receipts are kept outside the source release.

The configured GitHub workflow is an unrun workflow definition. Its default suite
selection is broader than this explicitly reviewed local selection, and its
future results must be reported independently. A portable pass is not native
acceptance, independent review, process-lifetime certification, or physical
validation.

## Reproduce the reviewed portable selection

Install the test-only tooling from `ci/requirements.txt` into a separate test
environment. From the source root, select only these reviewed nodes:

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python -m pytest -q -ra -p no:cacheprovider \
    tests/test_source_audit.py::test_synthetic_read_only_receipt_is_not_science_acceptance \
    tests/test_source_audit.py::test_import_has_no_optional_dependency_or_network \
    tests/test_source_audit.py::test_no_network_or_process_execution \
    tests/test_source_audit.py::test_missing_inputs_and_independent_manifest_pin \
    tests/test_source_audit.py::test_invalid_revision_pin \
    tests/test_source_audit.py::test_revision_disagreement \
    tests/test_source_audit.py::test_path_escape_or_nonlocal_input \
    tests/test_source_audit.py::test_symlink_routes_fail_closed \
    tests/test_source_audit.py::test_named_pipe_is_not_read_as_source \
    tests/test_source_audit.py::test_source_sha_and_git_blob_are_both_required \
    tests/test_source_audit.py::test_unrecognized_access_categories \
    tests/test_source_audit.py::test_private_inputs_need_private_audience \
    tests/test_source_audit.py::test_unknowns_non_numeric_values_and_uncertainty \
    tests/test_source_audit.py::test_censored_is_not_zero_or_known \
    tests/test_source_audit.py::test_synthetic_cannot_be_promoted \
    tests/test_source_audit.py::test_reported_nonmeasurement_cannot_be_promoted \
    tests/test_source_audit.py::test_locators_fail_closed \
    tests/test_source_audit.py::test_claim_semantics_must_match_bound_source \
    tests/test_source_audit.py::test_duplicate_ids_missing_source_and_unrequested_fields \
    tests/test_source_audit.py::test_malformed_json_is_bounded_and_rejected \
    tests/test_source_audit.py::test_bounded_sizes \
    tests/test_source_audit.py::test_cli_success_and_rejection_do_not_echo_input_paths \
    tests/test_lab_qualification.py::test_example_correct_refusals_pass_software_benchmark \
    tests/test_lab_qualification.py::test_semantic_refusals \
    tests/test_lab_qualification.py::test_unknown_is_retained_and_refused \
    tests/test_lab_qualification.py::test_stale_and_gap_signals \
    tests/test_lab_qualification.py::test_early_ack_and_transient_overshoot_are_not_hidden \
    tests/test_lab_qualification.py::test_explicit_consistent_percent_conversion \
    tests/test_lab_qualification.py::test_invalid_or_unknown_numeric_cannot_be_coerced \
    tests/test_lab_qualification.py::test_structural_invalidity_is_not_a_qualification_outcome \
    tests/test_lab_qualification.py::test_false_promotion_fields_and_missing_evidence \
    tests/test_lab_qualification.py::test_incorrect_oracle_is_software_failure_even_with_valid_bytes \
    tests/test_lab_qualification.py::test_hashes_bind_every_input_component \
    tests/test_lab_qualification.py::test_missing_and_changed_input_fail_closed \
    tests/test_lab_qualification.py::test_source_path_escape_refused \
    tests/test_lab_qualification.py::test_symlink_and_wrong_blob_refused \
    tests/test_lab_qualification.py::test_manifest_contract \
    tests/test_lab_qualification.py::test_no_network_process_or_device_imports \
    tests/test_lab_qualification.py::test_bounded_fixture_and_source_identity \
    tests/test_lab_qualification.py::test_cli_pass_oracle_failure_and_invalid_input \
    tests/test_ci_summary.py::test_counts_actual_cases_without_double_counting_nested_suites \
    tests/test_ci_summary.py::test_missing_receipt_is_not_success \
    tests/test_geometry.py::test_import_does_not_load_optional_cad_backends \
    tests/test_geometry.py::test_si_contract_and_analytical_volume \
    tests/test_geometry.py::test_rejects_unbounded_or_non_numeric_parameters \
    tests/test_geometry.py::test_bounds_are_explicit_and_inclusive \
    tests/test_geometry.py::test_output_refuses_existing_empty_nonempty_and_symlink \
    tests/test_geometry.py::test_missing_optional_dependency_is_actionable \
    tests/test_geometry.py::test_measurements_reject_scale_topology_nonfinite_and_translation \
    tests/test_geometry.py::test_step_unit_header_fails_closed \
    tests/test_gmsh_mesh.py::test_invalid_divisions \
    tests/test_gmsh_mesh.py::test_invalid_timeout \
    tests/test_gmsh_mesh.py::test_import_is_lightweight \
    tests/test_gmsh_mesh.py::test_mesh_readback \
    tests/test_gmsh_mesh.py::test_bad_saved_mesh_rejected \
    tests/test_gmsh_mesh.py::test_tampered_input_refused \
    tests/test_gmsh_mesh.py::test_failed_process_never_publishes \
    tests/test_gmsh_mesh.py::test_missing_process_output_never_passes \
    tests/test_gmsh_mesh.py::test_new_receipt_binds_native_identity \
    tests/test_gmsh_mesh.py::test_resealed_native_identity_disagreement_rejected \
    tests/test_gmsh_mesh.py::test_resealed_matching_wrong_native_version_rejected \
    tests/test_gmsh_mesh.py::test_legacy_is_read_only_not_native_verified \
    tests/test_gmsh_mesh.py::test_legacy_cannot_silently_upgrade_native_claim \
    tests/test_gmsh_mesh.py::test_worker_checks_native_version_before_file_identity \
    tests/test_gmsh_mesh.py::test_worker_mismatch_never_touches_geometry \
    tests/test_gmsh_mesh.py::test_worker_requires_linux_for_native_identity \
    tests/test_gmsh_mesh.py::test_native_mapping_uses_symbol_address_and_inode \
    tests/test_gmsh_mesh.py::test_file_identity_detects_mutation_during_hash \
    tests/test_thermal_conduction.py::test_timeout_contract \
    tests/test_thermal_conduction.py::test_optional_missing_solver \
    tests/test_thermal_conduction.py::test_parser_fixture \
    tests/test_thermal_conduction.py::test_parser_rejects_incomplete_nonfinite_duplicate \
    tests/test_thermal_conduction.py::test_empty_manifest_rejected \
    tests/test_thermal_conduction.py::test_shared_elapsed_evidence_contract \
    tests/test_thermal_conduction.py::test_shared_elapsed_exact_bound_accepted \
    tests/test_thermal_source.py::test_exact_nodes_still_have_nonzero_field_error_and_rates \
    tests/test_thermal_source.py::test_physics_mutations_rejected \
    tests/test_thermal_source.py::test_zero_error_from_exact_nodes_cannot_certify_field \
    tests/test_thermal_source.py::test_two_point_temperature_quadrature_is_not_continuous_rms \
    tests/test_thermal_source.py::test_false_refinement_rejected \
    tests/test_thermal_source.py::test_source_deck_leaves_linear_default_unchanged \
    tests/test_thermal_source.py::test_same_end_reaction_cancellation_is_rejected \
    tests/test_thermal_source.py::test_nodal_areas_accept_all_positive_axis_permutations \
    tests/test_thermal_source.py::test_ambiguous_boundary_area_fails_closed \
    tests/test_thermal_source.py::test_legacy_source_creation_is_refused \
    tests/test_structural_beam.py::test_timeout_contract \
    tests/test_structural_beam.py::test_unsupported_element_and_missing_solver \
    tests/test_structural_beam.py::test_shared_job_name_rejected_before_spawn \
    tests/test_structural_beam.py::test_consistent_face_load_weights \
    tests/test_structural_beam.py::test_parser_fixture \
    tests/test_structural_beam.py::test_parser_rejects_bad_output \
    tests/test_structural_beam.py::test_empty_manifest_rejected
```

For wheel smoke checks, build in a separate staging directory, install the wheel
without dependencies into a fresh virtual environment, and run the two pinned
module commands in the README against separately copied synthetic fixtures.
Use `python -I -B` and clear source-tree `PYTHONPATH` to verify installation
independently. For reproduction of this historical artifact, package metadata reports version
`0.1.0a0`, no required runtime requirements, and no entry points. The current
`0.1.0a1` candidate and its optional extras are recorded [separately](combined-candidate-verification.md). Native execution remains a separate gate.
