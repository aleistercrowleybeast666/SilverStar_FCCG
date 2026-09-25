#ifndef __NAVIGATION_INTEGRITY_H
#define __NAVIGATION_INTEGRITY_H

#include <stdint.h>

/* 10 s at 25 Hz with 550 ms delay and scheduling margin. */
#define NAV_INTEGRITY_CAPACITY 272U
#define NAV_INTEGRITY_MAX_WINDOW_US 10000000ULL

typedef enum
{
    NAV_INTEGRITY_TRUSTED = 0,
    NAV_INTEGRITY_SUSPECT,
    NAV_INTEGRITY_UNTRUSTED,
    NAV_INTEGRITY_RECOVERING
} NavigationIntegrityState;

typedef enum
{
    NAV_INTEGRITY_REASON_HEALTHY = 0,
    NAV_INTEGRITY_REASON_WARMUP,
    NAV_INTEGRITY_REASON_POSITION_INVALID,
    NAV_INTEGRITY_REASON_VELOCITY_INVALID,
    NAV_INTEGRITY_REASON_TIME_GAP,
    NAV_INTEGRITY_REASON_SEQUENCE_JUMP,
    NAV_INTEGRITY_REASON_QUALITY,
    NAV_INTEGRITY_REASON_EVIDENCE_AGE,
    NAV_INTEGRITY_REASON_REFERENCE_EXPIRED,
    NAV_INTEGRITY_REASON_CLOSURE_ABNORMAL
} NavigationIntegrityReason;

typedef enum
{
    NAV_INTEGRITY_PROCESS_OK = 0,
    NAV_INTEGRITY_PROCESS_INVALID,
    NAV_INTEGRITY_PROCESS_DUPLICATE,
    NAV_INTEGRITY_PROCESS_CAPACITY
} NavigationIntegrityProcessResult;

typedef struct
{
    uint8_t enabled;
    uint32_t window_us;
    uint32_t max_gap_us;
    uint32_t max_evidence_age_us;
    uint32_t reference_max_age_us;
    uint32_t suspect_duration_us;
    uint32_t untrusted_duration_us;
    uint32_t recovery_duration_us;
    uint16_t recovery_min_samples;
    float rolling_threshold_m;
    float anchored_threshold_m;
    float recovery_rolling_m;
    float recovery_anchored_m;
    float hacc_max_m;
    float sacc_max_mps;
    float velocity_bias_bound_mps;
    float reference_renewal_max_m;
    float position_r_scale;
    float reanchor_min_distance_m;
    float reanchor_covariance_floor_m2;
} NavigationIntegrityConfig;

typedef struct
{
    uint64_t receive_us;
    uint64_t position_us;
    uint64_t velocity_us;
    uint32_t epoch;
    uint32_t sequence;
    uint8_t valid_group_mask;
    float position_en[2];
    float velocity_en[2];
    float hacc_m;
    float sacc_mps;
} NavigationIntegrityInput;

typedef struct
{
    uint64_t decision_us;
    uint64_t evidence_cutoff_us;
    uint32_t reference_generation;
    uint8_t admitted_group_mask;
    uint8_t evidence_valid;
    uint8_t reanchor_requested;
    NavigationIntegrityState state;
    NavigationIntegrityReason reason;
    float position_r_scale;
    float rolling_m;
    float anchored_m;
} NavigationIntegrityDecision;

typedef struct
{
    uint32_t position_us_lo;
    uint32_t velocity_us_lo;
    uint32_t velocity_segment;
    float position_en[2];
    float velocity_en[2];
    float velocity_integral[2];
    uint8_t valid_group_mask;
} NavigationIntegritySample;

typedef struct
{
    NavigationIntegritySample samples[NAV_INTEGRITY_CAPACITY];
    NavigationIntegrityConfig config;
    NavigationIntegrityInput previous_input;
    uint16_t count;
    uint16_t healthy_count;
    uint32_t velocity_segment;
    uint32_t reference_generation;
    uint32_t abnormal_us;
    uint32_t healthy_us;
    uint32_t recovery_us;
    uint64_t reference_us;
    float reference_position[2];
    float reference_integral[2];
    uint32_t reference_velocity_segment;
    uint8_t reference_trusted;
    uint8_t pending_reanchor;
    uint8_t reanchor_attempts;
    uint8_t reanchor_withdrawn;
    NavigationIntegrityState state;
} NavigationIntegrityContext;

NavigationIntegrityProcessResult NavigationIntegrity_ConfigValidate(
    const NavigationIntegrityConfig *config);
NavigationIntegrityProcessResult NavigationIntegrity_Reset(
    NavigationIntegrityContext *context, const NavigationIntegrityConfig *config);
NavigationIntegrityProcessResult NavigationIntegrity_Receive(
    NavigationIntegrityContext *context, const NavigationIntegrityInput *input,
    NavigationIntegrityDecision *decision);
void NavigationIntegrity_ReanchorAcknowledge(NavigationIntegrityContext *context,
                                             uint8_t succeeded);

#endif /* __NAVIGATION_INTEGRITY_H */
