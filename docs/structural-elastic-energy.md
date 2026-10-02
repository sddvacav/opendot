# Optional structural elastic-energy consistency API

> Historical optional-only a5/a6 contract below. The current [default-v2 profile](structural-default-v2.md) requires the same unchanged kernel in its default profile; the optional API result remains compatible. See the [overview](../OVERVIEW.md) for current release status. Frozen a5/a6 source and evidence, including the version-specific statements below, are unchanged.

The historical unreleased `0.2.0a5` candidate introduced, and a6 retains,
`opendot_engineering.executors.structural_beam.verify_elastic_energy(directory)`.
It first requires the existing strict `verify_structural_artifacts(directory)`
to pass, then compares each element's raw printed E tensor strain with raw
whole-element ELSE. It reads an existing pack and never executes a solver or
writes artifacts. Existing verifier bodies, reports, receipts, tolerances, CLI
and default acceptance are unchanged. Calling the old verifier alone does not
perform this additional check.

A successful report has `status = CONDITIONAL_ELASTIC_ENERGY_CONSISTENCY_PASS`,
`scientific_accepted = false`, `physical_validation = NOT_PERFORMED`, and
`independent_review = NOT_EVALUATED`. Its result is conditional consistency
under the fixed material, output and arithmetic assumptions below. The report
explicitly records no-underflow as `ASSUMED_NOT_VERIFIED` and its arithmetic
error bound as `NOT_PROVED`. It is not
physical validation, automatic scientific acceptance, a constitutive solver,
a general material validator, or a proof about the native binary.

## Strict scope and results

The existing exact-deck gate limits the API to the synthetic SI C3D8I cantilever:
E = 210000000000 Pa, nu = 0.3, step 1 at time 1, small-strain linear static,
initially unstressed/unstrained, no thermal strain, history, material
nonlinearity, contact or material orientation. Incompatible modes contribute
to the native printed strains. They are not reconstructed from the eight
ordinary nodal displacements.

The API returns a new dictionary with fixed contract identity
`structural.elastic_energy.ccx223.e13_6.v1`, material and uncertainty profiles,
per-element energies, absolute residuals, printed-error bounds, arithmetic
allowances and all eight positive Jacobian determinants, plus sum diagnostics.
Every element must pass independently: signed errors cannot cancel across
elements. The global sum is supplementary. No report file is added to the pack.

Existing admission errors propagate. Unsupported precision/exponents, missing
or inconsistent element/IP identities, invalid Jacobians, nonfinite values,
negative ELSE and per-element mismatch raise `ValueError`. Mismatch errors
identify the element, absolute residual and allowed bound. The public API uses
the existing mesh validators, shared bounded reader and `parse_dat`; its small
additional raw-token extraction only establishes decimal precision against
already-parsed values and identities. Trusted cooperative, unmodified inputs
are required; these multiple reads are not a hostile-race snapshot.

## Source-frozen mechanics and quadrature

For tensor strain e = (xx, yy, zz, xy, xz, yz), with
mu = E/[2(1+nu)] and lambda = E*nu/[(1+nu)(1-2*nu)],

    W(e) = lambda/2 * (xx + yy + zz)^2
         + mu * (xx^2 + yy^2 + zz^2 + 2*xy^2 + 2*xz^2 + 2*yz^2)
    U_element = sum_IP detJ(IP) * W(e_IP)

The shear entries are tensor shear, not engineering shear. ELSE is integrated
whole-element internal energy; only in this restricted no-history elastic
case is it identified with the elastic energy of the printed state.

The eight Gauss weights are one. The exact 2.23 source literal
`0.577350269189626` is pinned, with x varying fastest, then y, then z:
`---, +--, -+-, ++-, --+, +-+, -++, +++`. Physical corner nodes instead follow
`---, +--, ++-, -+-, --+, +-+, +++, -++`. The existing physical corner-sign
constant is reused; its separate `1/sqrt(3)` thermal quadrature is not changed.

At every point the helper differentiates the eight physical HEX8 shape
functions, forms J from the preserved actual coordinates, and requires
positive finite detJ. Incompatible modes 9–11 affect strain, not geometric
mapping. No nominal cell volume, absolute determinant, or approximately affine
geometry shortcut substitutes for these weights. The earlier mesh admission
remains in force; helper-only warped-mapping tests do not expand that scope.

## Predeclared output uncertainty

Both native fields use `1P E13.6`: seven significant decimal digits. The source
does not select an I/O rounding mode, so the API conservatively uses one
last-place quantum rather than claiming nearest rounding. For a normalized
nonzero token m * 10^p, delta = 10^(p-6). Only six fractional digits, uppercase
E and a signed two-digit exponent are supported. Optional leading signs are
accepted. Other precision, D notation, unnormalized mantissas, overflow and
three-digit exponents are refused.

Canonical `0.000000E+00` (including a leading sign) has delta = 0, conditional
on a normal finite binary64/no-subnormal-or-underflow output profile. This is
an explicitly declared assumption, not a fact that DAT can prove. The report
states `no_subnormal_or_underflow = ASSUMED_NOT_VERIFIED`. Users unable to
justify that profile must not treat the result as established consistency.
There is no generous fixed-point uncertainty or absolute floor for zero.

For each printed strain tuple, let t = xx+yy+zz, d = delta_xx+delta_yy+delta_zz
and c = (1,1,1,2,2,2):

    B_W = lambda/2 * (2*abs(t)*d + d^2)
        + mu * sum_i c_i * (2*abs(e_i)*delta_i + delta_i^2)
    B_print = sum_IP detJ(IP) * B_W(IP) + delta_ELSE
    B_arithmetic = 1e-10 * max(U_from_E, abs(ELSE))
    abs(U_from_E - ELSE) <= B_print + B_arithmetic  # separately per element

These formulas were fixed from source/analytic research before inspecting
native-pack residuals. The arithmetic allowance is a declared policy with zero
absolute floor, not a formally proved bound for arbitrary compilers, native
builds, distorted geometry or hidden underflow. It does not absorb a nominal
geometry approximation. All-zero strains with positive ELSE fail, including
small normal values. Coherently rewritten strains/energies, sign reversal and
other energy-preserving errors may still pass: this cross-check does not
establish authenticity or exhaustively validate a displacement/stress field.

## Primary-source basis

The reviewed [official CalculiX 2.23 source archive](https://dhondt.de/ccx_2.23.src.tar.bz2)
has SHA-256 `9c88385c10fb04f5dc6c4e98027a51bebdd8aee3920e05190d6c1dd08357d6e7`.
Relevant files under `CalculiX/ccx_2.23/src` are `calctotstrain.f:31–38,79–87`,
`resultsmech.f:318–324,695–741,917–945,1063–1091`,
`printoutint.f:436–459`, `printoutelem.f:324–331,411–428,519–521`,
`linel.f:38–64`, `gauss.f:99–108` and `shape8hu.f:120–127,144–202`.
The [2.23 manual](https://dhondt.de/ccx_2.23.pdf), sections 6.2.3 and 7.53,
distinguishes C3D8I, total strain and element energy. Intel's primary
[E-format](https://www.intel.com/content/www/us/en/docs/fortran-compiler/developer-guide-reference/2023-0/e-and-d-editing.html),
[P-scaling](https://www.intel.com/content/www/us/en/docs/fortran-compiler/developer-guide-reference/2023-1/scale-factor-editing-p.html)
and [I/O-rounding](https://www.intel.com/content/www/us/en/docs/fortran-compiler/developer-guide-reference/2025-0/rounding-specifier-round.html)
references support the conservative format interpretation; they do not identify
a particular native compiler/build.

## Verification boundary

`tests/test_structural_elastic_energy.py` contains independently analytic zero,
uniaxial-strain/stress, hydrostatic, pure-shear and mixed-field fixtures;
wrong-shear-factor, incomplete-IP, unsupported-precision, inverted-geometry,
warped/IP-varying geometry, signed-cancellation and resealed-pack negatives.
The complete synthetic-pack checks traverse the unchanged strict admission
path. No native solver, build, install or publication is performed by them.
The historical a5 explicit portable selection deliberately added 54 energy cases and 17
CPU-ceiling cases to the 1,033 inherited cases; selection counts are not pass
results. See the [a5 verification record](a5-candidate-verification.md) for the
separate historical source, build and installed-check scopes. The current
[a6 integration record](a6-candidate-verification.md) retains those cases and
requires new exact-candidate receipts. The earlier
source-only energy candidate's author run of 1,104 selected tests plus 49
subtests is historical evidence, not exact a5 artifact acceptance.

Any recheck of a previously generated native positive pack is a no-rerun,
output-only integration scope, separately recorded from synthetic tests. It
cannot qualify a new native execution or close the unchanged default
verifier's missing constitutive-energy cross-check or other numeric-field
consistency gaps. The inherited file-size-limit issue is also unchanged.
The historical a5 version identifies a separate unreleased candidate; neither
that version nor the current a6 integration implies
release approval or public distribution.
