# Final navigation review and owned fixes

The review inspected actual GNSS quality, health supervision, ESKF backend/replay,
APP preparation/START and navigation log producers against the taskbook. Original
hardware firmware/logs were not modified. The initial reproduction is preserved in
`review_reproduction.txt`, including production-source compiler command, input C
and output. That file records the pre-fix result, not a current acceptance claim.

## Reproduced defects

1. KF6 accepted an entirely zero float32 gain. Public ResetWithCovariance accepts
   diagonal P=1e-8; finite variance FLT_MAX yields exactly zero gain. Position and
   covariance remained unchanged, yet ACCEPTED and accept_count advanced.
2. The health supervisor returned overall HEALTHY for five successful groups with
   variance_scale=3 and SOFT_WEIGHTED state. The root agent owns this correction
   and its independent final validation; this child did not edit health code.
3. The root/FLP review identified KF6 health variance_scale omitted Pos EN window
   and actual robust factors. This child was explicitly assigned the producer fix.

## Completed owned changes

- `Algorithm/Estimator/KF6/Src/navigation_kf.c`: every active gain element must be
  finite and at least one must be nonzero before state/P mutation. Zero innovation
  remains valid when gain is positive. Invalid gain returns NUMERIC_ERROR (4),
  increments the existing numeric/measurement rejection counters and never an
  acceptance counter. State and covariance remain byte-identical on this path.
- Existing owned `Tests/Host/test_air_kf.c`: permanent all-four-GNSS plus Baro zero
  gain tests; small positive gain and zero-innovation controls; finite corrupt
  cross-P overflow fault injection proving unchanged state/P.
- `APP/Src/estimator_task.c`: health scale uses one actual profile snapshot and
  satellite variance factor x (Pos EN only) consistency factor x actual robust
  factor. No measurement, NIS threshold, estimator result or wire layout changed.
- Existing owned `Tests/Host/test_estimator_preparation.c`: the actual included APP
  translation unit is tested. Helper verifies 1.5 x 3 x 2 = 9, other groups omit
  window, nonsoft results omit robust, and the existing maximum remains bounded.
  Real ReplayEventApply -> HealthObserve tests exercise all four groups.

## Actual validation

| Check | Result | Evidence |
|---|---|---|
| Actual air_kf Host | 706 checks, zero failures | air_kf_compile.log / air_kf_run.log |
| Actual KF replay Host | 33,531 checks, zero failures | navigation_kf_replay_compile.log / navigation_kf_replay_run.log |
| Actual APP preparation/health producer Host | 288 checks, zero failures | estimator_preparation_compile_final.log / estimator_preparation_run_final.log |
| KF6 ARM Cortex-M4 Release O2 and Debug Og, complete first-party warnings | Both compile successfully | arm_release_compile.log / arm_debug_compile.log |
| Original Power of Ten on both changed production C files | 549 checks; 196 functions; pass | power10_final.log |

The first producer test tried NIS=2 x soft, which the real default hard thresholds
correctly reject (1D: 6.635/10.828; 2D: 9.21/13.816). The 12 failed assertions in
`estimator_preparation_run.log` are preserved. The final actual-producer test uses
the midpoint between those unchanged soft/hard thresholds; the helper retains the
exact factor-9 case. No gate was relaxed to obtain success.

One initial Host compile used an older generated navigation_quality.h and failed
because ConfigValidate was missing. The final compile uses the current owned
header and current production sources; both diagnostics are preserved.

Linked application RAM/FLASH, stack and complete six-configuration gates are owned
by the root/GSHC final matrix. This evidence does not substitute object compilation
for those application-level results. No hardware or physical output was exercised.
