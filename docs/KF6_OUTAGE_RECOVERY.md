# KF6 GNSS outage recovery and vertical measurement noise

Platform 0.0.10, project 12, parameter schema 1.0 and decoder/project semantics 1.2 remain unchanged.
The record catalog, AIR/GSP and SSLOG layouts are unchanged. Exact acceptance results belong in
[VALIDATION.md](../VALIDATION.md).

## Availability and return

Each of position EN, position U, velocity EN and velocity U owns an availability timestamp,
outage eligibility, a loss latch, reject/consistency/accepted streaks and bounded inflation attempts.
A quality-valid sample refreshes its own group's clock even when its NIS is rejected. An invalid
velocity never expires a valid position group. Position consistency may require the corresponding
velocity; that is a consistency condition, not a position-availability condition.

A gap **strictly greater than** `gnss_reacquire_outage_ms` permits return confirmation. The default
is 300 ms (a conservative configuration choice, not a measured flight optimum); the accepted
range is 100–10000 ms. At 25 Hz, candidates 160/200/250/300/500 ms represent 4/5/6.25/7.5/12.5
nominal sample periods. A 100 ms scheduling gap remains below every candidate. The firmware does
not need synthetic unavailable samples: the next observed GNSS epoch closes any absent interval.
Present invalid groups advance loss detection, and a long all-source absence is recognized on return.
The existing freshness, source, frozen-origin and START gates run before this tracker.

The returning measurement first takes the normal NIS update. A fused result before activation
clears outage eligibility without inflation. Otherwise, activation requires the true outage,
five consecutive hard rejects and three consistent source intervals. Continuous high-dynamic
rejection with fresh GNSS never authorizes inflation. Duplicate/rollback timestamps clear recovery
streaks and eligibility; timestamp zero disables that epoch's result gate. Finite/positive sigma
validation is group-specific. A new loss clears prior attempt/accept/reject state even during recovery.

Inflation remains `P' = D P D'`, group-selective, with target D=2, at least five rejected epochs
between attempts, at most eight attempts, position variance cap 1e6 and velocity variance cap 1e4.
Three consecutive fused returns end active recovery. Origins, observations, NIS thresholds and Q
are never changed by recovery. Multiple attempts remain useful for substantial prediction drift.

## Vertical fusion

The state remains `[pE,pN,pU,vE,vN,vU]`. Barometer observes pU; vU is corrected through P(vU,pU).
GNSS pU remains a separate 1D observation, as does GNSS vU. No bias state, ZUPT, INS/attitude change
or fixed timing compensation is introduced. Defaults remain GNSS pU sigma floor 2.5 m, barometer
sigma floor 5 m, velocity sigma floor 0.15 m/s. Ground-oriented candidates are not flight defaults.

`gnss_velocity_std` retains the shared receiver sigma floor for compatibility.
`gnss_velocity_vertical_scale` (dimensionless actual value, default 1, range 1–10) scales only the
vertical **measurement standard deviation** after the receiver uncertainty/floor maximum:

```
sigma_EN = max(receiver_sigma_EN * accuracy_scale, gnss_velocity_std)
sigma_U  = max(receiver_sigma_U  * accuracy_scale, gnss_velocity_std) * gnss_velocity_vertical_scale
R_axis   = sigma_axis * sigma_axis
```

Receiver uncertainty remains dynamic. P0 initialization is unchanged. The new values are declared
by the KF6 manifest, rendered into generated constants and exported in decoder 1.2 actual values.
Old FCCG projects reconcile only missing fields to defaults. FLP recognizes the exact prior
parameter identity and supplies explicit compatibility defaults for these two additions only;
missing previously required parameters remain errors. Old GNSS logs replayed with the new recovery
policy are marked approximate, never advertised as an exact old-firmware reproduction.

## Offline evidence

FLP owns independent per-log weight and velocity-latency experiments. These keep initial state,
P0, Q, attitude and position/barometer timing fixed. Velocity delay scans resample velocity and its
receiver variance on the original GNSS epoch grid over a common interior window, without crossing
source gaps or extrapolating. This is an explicitly approximate analysis, not a firmware timing fix.
Without qualified real logs, retain conservative defaults and report missing evidence rather than
selecting a purported flight optimum. See the FLP repository's field-analysis guide for its CLI.
