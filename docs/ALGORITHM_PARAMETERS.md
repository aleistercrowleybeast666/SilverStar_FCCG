# Algorithm actual parameters and decoder 1.2

Platform remains **0.0.10**. Project format is **12**; `.ssdecoder` package schema and
project semantics are **1.2**. Record Catalog and AIR M0 / Maintenance 0.0 / SSLOG 0.0
remain independent and unchanged. Decoder 1.1 is rejected; this is a package contract break.

The five pages are Devices → Flight Configuration → **Algorithm Parameters / 算法参数** →
Hardware Connection → Code Generation & Build. The new page shows only selected algorithms
that declare parameters, with actual values, units, localized descriptions, ranges, basic/advanced
disclosures and per-algorithm reset. Save, reopen and Save As preserve these values.

## Meaning and source inventory

Pure INS consumes gravity at `APP/Src/ins_task.c` → `InsMechanization_Init`.
KF6 consumes its gravity at the existing delta-velocity transform in `estimator_task.c`.
These independent navigation inputs leave platform gravity used by Calibration, Alignment,
IMU unit conversion and the legacy SSLOG header unchanged. Decoder parameter sets are the
authority for the two navigation gravity values; the legacy header gravity is not their override.

KF6 P0, process sigma, GNSS sigma floors, barometer sigma and NIS values come from
`System/User/system_user_config.h`, `System/Src/system_estimator_profile.c` and the existing
profile initialization calls in `estimator_task.c`. Their C calculation sites are in
`navigation_kf.c`. P0 entries are actual covariance diagonal **floors**, with E/N/U order;
the existing initial GNSS uncertainty rule may increase P0. They are not squared again.
Process acceleration sigma is per axis; existing prediction squares sigma and retains its
original dt gains. GNSS sigma remains `max(receiver_sigma * 1.25, configured_floor)` and
R is its square. Horizontal E/N share a position floor; velocity E/N/U share a velocity floor.
Barometer sigma is squared once by the existing update and retains its 1.5 m minimum.
NIS values are dimensionless; hard must exceed soft even after float32 rounding.
The existing NIS maximum R inflation cap is itself an actual dimensionless parameter.

FLP's old default-multiplier vocabulary must not enter the project: P0 scale maps to the six
actual diagonal floors, GNSS R scales to the real firmware sigma-floor parameters, and baro R
scale to actual sigma. There is no invented fixed GNSS R or new runtime multiplier. This does
not emulate arbitrary offline R multipliers: reported receiver uncertainty still participates.
FLP process sigma, gravity and NIS values already have actual semantics. FLP is read-only in
this change; its later consumer must adopt this explicit contract independently.
State dimension, coning/sculling coefficients, matrix safeguards, update order, source selection,
measurement timing and GNSS reacquisition policy are not exposed or changed.

## Coning2 + Sculling2 INS

`silverstar.algorithm.ins.coning2_sculling2`

| Parameter ID | Default actual | Unit | Representation |
|---|---:|---|---|
| `gravity_mps2` | 9.78 | m/s^2 | value |

## KF6 Navigation Estimator

`silverstar.algorithm.estimator.kf6`

| Parameter ID | Default actual | Unit | Representation |
|---|---:|---|---|
| `gravity_mps2` | 9.78 | m/s^2 | value |
| `p0_position_e` | 4 | m^2 | covariance_diagonal |
| `p0_position_n` | 4 | m^2 | covariance_diagonal |
| `p0_position_u` | 9 | m^2 | covariance_diagonal |
| `p0_velocity_e` | 0.25 | m^2/s^2 | covariance_diagonal |
| `p0_velocity_n` | 0.25 | m^2/s^2 | covariance_diagonal |
| `p0_velocity_u` | 0.25 | m^2/s^2 | covariance_diagonal |
| `process_accel_std_e` | 1.5 | m/s^2 | sigma |
| `process_accel_std_n` | 1.5 | m/s^2 | sigma |
| `process_accel_std_u` | 2 | m/s^2 | sigma |
| `gnss_position_std_horizontal` | 1.5 | m | sigma |
| `gnss_position_std_vertical` | 2.5 | m | sigma |
| `gnss_velocity_std` | 0.15 | m/s | sigma |
| `baro_std_m` | 5 | m | sigma |
| `nis_1d_soft` | 6.635 | 1 | value |
| `nis_1d_hard` | 10.828 | 1 | value |
| `nis_2d_soft` | 9.21 | 1 | value |
| `nis_2d_hard` | 13.816 | 1 | value |
| `nis_3d_soft` | 11.345 | 1 | value |
| `nis_3d_hard` | 16.266 | 1 | value |
| `nis_max_r_scale` | 10 | 1 | value |

## Declarative schema and project state

An Algorithm manifest may declare `algorithm_parameters` with `schema_id` equal to
`silverstar.algorithm-parameters/1.0` and a `parameters` array. Each entry requires `id`, `type`,
`default`, `unit`, `representation`, `min`, `max`, `precision`, `step`, `group`, `order`,
`description`, `display_names` and `generated_symbol`. Descriptions/names contain `en_US` and
`zh_CN`; optional `greater_than` names another parameter in the same algorithm (NIS ordering).
Every object rejects unknown properties; the parser also checks unique IDs/symbols, finite
defaults, valid ranges and comparison references. Types are float (binary32) or integer (int32).
No executable plugin code or algorithm-name dispatch is involved.

Project format 12 requires `algorithm_parameters: {component_id: {parameter_id: actual_value}}`.
Selecting an algorithm initializes its declared defaults; deselection removes its parameter set.
Unknown IDs within a retained set stay invalid instead of being silently discarded. Type,
range, NaN/Inf and NIS-order errors block strict generation. Format 11 migration only adds an
empty map; reconciliation initializes selected defaults. Prior earlier migrations are retained.

## Generated configuration and ownership

`Generated/Inc/project_algorithm_parameters.h` is force-included through existing
`project_flight_config.h` by the common Make/Host graph. It emits static numeric macros;
float constants carry `f` and round-trip binary32 with no arithmetic reordered and no heap,
strings or JSON in the target. Prior explicit Host override fixtures keep their override
convention. Normal product generation uses only saved actual values; manual compiler overrides
or edited project-owned firmware require a new independently validated decoder contract.

Parameter changes participate in the existing normalized generation fingerprint. Make, EIDE,
readiness and decoder hashes consume the same state. Reference import preserves declarations,
modified system/task bindings and the numerical Host fixture. First-copy source ownership is
unchanged: normal Apply does not port old project-owned C files. Generate a fresh project or
deliberately port the listed bindings before using parameter configuration in an older output.

## Self-contained `.ssdecoder` 1.2

The same five archive members remain. `project_semantics.json` adds
`firmware_algorithm_parameters`, an array of `{component, schema_id, manifest_sha256, parameters}`.
Each parameter is `{id, value, unit, representation, storage_type, description}`. `value` is the
resolved binary32/int32 value used by emitted C constants, not an unrounded UI decimal and not
a hidden-base multiplier. The English description states per-axis/shared and conversion semantics.
The manifest hash identifies the exact declaring schema; ordinary package checksums and the
generation-profile hash cover the new semantics. The decoder validates ownership, duplicates,
representation and exact target representability without loading plugins or accessing a network.

`algorithms` remains firmware membership, not an offline whitelist. An algorithm absent onboard
has no firmware parameter set. **Recorded Configuration** describes this firmware build's
configured inputs, not changing runtime P/Q/R matrices. **Offline What-if** is a separate analysis
configuration and may use other algorithms; it must not overwrite or impersonate recorded inputs.

## Verification

The frozen pre-change C trajectory exercises two-subsample INS, KF6 prediction and GNSS/barometer
updates, comparing quaternion, position, velocity, state and full covariance output. New defaults
must match its exact binary32 trajectory; changed values must affect generated C results. Prior
Host Golden logs also remain generated by the real C codec. Exact hashes, toolchains, build sizes,
test counts and acceptance results belong only in [VALIDATION](../VALIDATION.md).

## Shared parameters and ordering

Selected owners are ordered by `selection.ui_order`, then component ID; owners without a
`selection` follow deterministically. The optional safe-token `shared_key` groups compatible
parameters without algorithm-name branches. Type, default, unit, representation, bounds,
precision and step must match exactly. The GUI renders each selected group once and synchronizes
all per-owner format-12 values; strict validation rejects conflicts, while reconciliation only
inherits an existing value for a newly selected owner.

Pure INS and KF6 declare `navigation.gravity_mps2`. Their separate generated macros and separate
`.ssdecoder` `firmware_algorithm_parameters` values resolve to the same float32. `shared_key` is
FCCG-only and is not serialized to `.ssdecoder`; FLP does not interpret it. This navigation group
does not include `SYSTEM_LOCAL_GRAVITY_MPS2`, Calibration, or Alignment. Package schema and project
semantics remain 1.2, required FLP minimum is 0.0.2, and algorithm formulas/timing are unchanged.
