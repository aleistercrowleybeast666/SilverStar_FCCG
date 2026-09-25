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
R is its square. Horizontal E/N share a position floor; velocity U additionally uses the declared vertical sigma scale.
Barometer R is the square of the configured sigma. JY901B recommendation (1.5 m)
is advisory; there is no device sigma floor and no fabricated native variance.
NIS values are dimensionless; hard must exceed soft even after float32 rounding.
The existing NIS maximum R inflation cap is itself an actual dimensionless parameter.

FLP's old default-multiplier vocabulary must not enter the project: P0 scale maps to the six
actual diagonal floors, GNSS R scales to the real firmware sigma-floor parameters, and baro R
scale to actual sigma. There is no invented fixed GNSS R; the declared vertical velocity scale multiplies sigma after its dynamic floor. This does
not emulate arbitrary offline R multipliers: reported receiver uncertainty still participates.
FLP process sigma, gravity and NIS values already have actual semantics. FLP is read-only in
this change; its later consumer must adopt this explicit contract independently.
State dimension, coning/sculling coefficients, matrix safeguards and source selection remain unchanged.
Measurement timing is extended by the [fixed-lag replay contract](KF6_FIXED_LAG_REPLAY.md). GNSS outage recovery and its two compatible parameter additions are defined in [the recovery contract](KF6_OUTAGE_RECOVERY.md).

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
| `gnss_velocity_vertical_scale` | 1.75 | 1 | value |
| `gnss_reacquire_outage_ms` | 300 | ms | value |
| `baro_std_m` | 2.5 | m | sigma |
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

## Fixed-lag parameters and migration

KF6 declares advanced integer `gnss_position_measurement_delay_ms` (0),
`gnss_velocity_measurement_delay_ms` (270), and `baro_measurement_delay_ms` (0).
Values 0–550 ms are supported by the static 600 ms history with 50 ms scheduling
headroom. A measurement outside the actual available history is explicitly rejected,
including startup and reset boundaries. 270 ms is an experimental candidate, not a
NEO-M9N hardware property. All values are emitted into generated constants and decoder
actual-parameter metadata.

`legacy_default` is optional declarative parameter metadata. Reconciliation uses it
only for a missing field in an existing algorithm owner. Previously stored explicit
values always win; new selections and Restore Defaults use `default`. Old KF6 owners
missing new delay fields receive zero delays; missing legacy baro/vertical-scale
fields receive 5.0/1.0. New projects use 2.5/1.75 and velocity delay 270 ms.
Recommendations never participate in shared-parameter contract equality.


## GNSS position self-check candidate contract

The KF6 plugin is the authority for the following values. FCCG format-12 projects
store per-owner actual values, generated constants use the same values, and
`.ssdecoder` project-semantics 1.2 declares `navigation_replay.gnss_integrity_revision = 1`
for newly generated projects. FLP mirrors the exact types, units, ranges and
representation. A newly selected KF6 defaults to enabled; an existing KF6
owner missing the new fields reconciles with `legacy_default` and stays disabled.
Revision-0 logs must remain disabled for faithful replay. A revision-1 KF6
parameter set must contain all 20 values. These defaults are candidates, not
flight-qualified thresholds.

| KF6 parameter | Type | New default | Legacy default | Unit | Allowed range |
| --- | --- | ---: | ---: | --- | --- |
| `gnss_integrity_enable` | integer | 1 | 0 | 1 | 0–1 |
| `gnss_integrity_window_s` | integer | 5 | 5 | s | 1–10 |
| `gnss_integrity_max_gap_ms` | integer | 120 | 120 | ms | 40–1200 |
| `gnss_integrity_max_evidence_age_ms` | integer | 550 | 550 | ms | 0–550 |
| `gnss_integrity_reference_max_age_s` | integer | 30 | 30 | s | 11–300 |
| `gnss_integrity_suspect_duration_ms` | integer | 2000 | 2000 | ms | 100–30000 |
| `gnss_integrity_untrusted_duration_ms` | integer | 5000 | 5000 | ms | 100–30000 |
| `gnss_integrity_recovery_duration_ms` | integer | 8000 | 8000 | ms | 100–30000 |
| `gnss_integrity_recovery_min_samples` | integer | 25 | 25 | samples | 1–1000 |
| `gnss_integrity_rolling_threshold_m` | float | 7.0 | 7.0 | m | 0.1–100.0 |
| `gnss_integrity_anchored_threshold_m` | float | 15.0 | 15.0 | m | 0.1–200.0 |
| `gnss_integrity_recovery_rolling_m` | float | 2.0 | 2.0 | m | 0.1–50.0 |
| `gnss_integrity_recovery_anchored_m` | float | 8.0 | 8.0 | m | 0.1–100.0 |
| `gnss_integrity_hacc_max_m` | float | 6.0 | 6.0 | m | 0.1–100.0 |
| `gnss_integrity_sacc_max_mps` | float | 1.2 | 1.2 | m/s | 0.01–20.0 |
| `gnss_integrity_velocity_bias_bound_mps` | float | 0.15 | 0.15 | m/s | 0.0–5.0 |
| `gnss_integrity_reference_renewal_max_m` | float | 2.0 | 2.0 | m | 0.1–50.0 |
| `gnss_integrity_position_r_scale` | float | 4.0 | 4.0 | 1 | 1.0–100.0 |
| `gnss_integrity_reanchor_min_distance_m` | float | 8.0 | 8.0 | m | 0.1–100.0 |
| `gnss_integrity_reanchor_covariance_floor_m2` | float | 25.0 | 25.0 | m^2 | 0.01–10000.0 |

The receive-side C state machine compares position displacement and velocity
integral over a causal aligned history window using the existing resolved
position/velocity times. It admits only horizontal position (E/N) through
normal R, a conservative R multiplier, or pause; other GNSS groups retain their
own native validity. An anchored residual uses the bounded reference age and
`anchored_threshold_m + velocity_bias_bound_mps * age_s`. Reference renewal is
permitted only while trusted and within both rolling and anchored renewal
bounds. A true velocity/sequence discontinuity clears duration counters and
pending reanchor. Reanchor operates on the historical position state and
covariance, followed by normal fixed-lag replay.

The candidate has unresolved resource and replay/logging validation failures;
its exact gate results and limits are recorded in [VALIDATION](../VALIDATION.md).
