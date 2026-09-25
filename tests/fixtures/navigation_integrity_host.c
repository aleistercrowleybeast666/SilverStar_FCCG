#include <stdint.h>
#include <stdio.h>

#include "navigation_integrity.h"

static NavigationIntegrityContext s_context;
static NavigationIntegrityInput s_input;
static NavigationIntegrityDecision s_decision;

static NavigationIntegrityConfig Integrity_ConfigGet(void)
{
    NavigationIntegrityConfig config = {0};
    config.enabled = 1U;
    config.window_us = 5000000U;
    config.max_gap_us = 120000U;
    config.max_evidence_age_us = 550000U;
    config.reference_max_age_us = 30000000U;
    config.suspect_duration_us = 2000000U;
    config.untrusted_duration_us = 5000000U;
    config.recovery_duration_us = 1000000U;
    config.recovery_min_samples = 25U;
    config.rolling_threshold_m = 7.0f;
    config.anchored_threshold_m = 15.0f;
    config.recovery_rolling_m = 5.0f;
    config.recovery_anchored_m = 7.0f;
    config.hacc_max_m = 10.0f;
    config.sacc_max_mps = 5.0f;
    config.velocity_bias_bound_mps = 0.15f;
    config.reference_renewal_max_m = 2.0f;
    config.position_r_scale = 4.0f;
    config.reanchor_min_distance_m = 3.0f;
    config.reanchor_covariance_floor_m2 = 16.0f;
    return config;
}

static uint8_t Integrity_Feed(uint64_t receive_us, float hacc)
{
    s_input.receive_us = receive_us;
    s_input.position_us = receive_us;
    s_input.velocity_us = receive_us - 270000U;
    s_input.sequence++;
    s_input.valid_group_mask = 5U;
    s_input.position_en[0] = (float)(receive_us - 1000000U) * 1e-6f;
    s_input.velocity_en[0] = 1.0f;
    s_input.hacc_m = hacc;
    s_input.sacc_mps = 0.2f;
    return (uint8_t)(NavigationIntegrity_Receive(
        &s_context, &s_input, &s_decision) == NAV_INTEGRITY_PROCESS_OK);
}


static uint8_t Integrity_AccelerationCheck(void)
{
    NavigationIntegrityConfig config = Integrity_ConfigGet();
    uint64_t receive_us = 1000000U;
    uint32_t index;
    if (NavigationIntegrity_Reset(&s_context, &config) != NAV_INTEGRITY_PROCESS_OK)
    { return 0U; }
    s_input = (NavigationIntegrityInput){0};
    for (index = 0U; index < 180U; index++)
    {
        float position_s = (float)receive_us * 1e-6f;
        float velocity_s = (float)(receive_us - 270000U) * 1e-6f;
        s_input.receive_us = receive_us;
        s_input.position_us = receive_us;
        s_input.velocity_us = receive_us - 270000U;
        s_input.epoch = 1U;
        s_input.sequence = index + 1U;
        s_input.valid_group_mask = 5U;
        s_input.position_en[0] = 4.0f * position_s * position_s;
        s_input.velocity_en[0] = 8.0f * velocity_s;
        s_input.hacc_m = 0.5f;
        s_input.sacc_mps = 0.2f;
        if (NavigationIntegrity_Receive(&s_context, &s_input, &s_decision) !=
            NAV_INTEGRITY_PROCESS_OK) { return 0U; }
        receive_us += 40000U;
    }
    return (uint8_t)((s_decision.evidence_valid != 0U) &&
                     (s_decision.state == NAV_INTEGRITY_TRUSTED) &&
                     (s_decision.rolling_m < 0.1f));
}

int main(void)
{
    NavigationIntegrityConfig config = Integrity_ConfigGet();
    uint64_t receive_us = 1000000U;
    uint32_t index;
    uint32_t generation;
    if (NavigationIntegrity_Reset(&s_context, &config) != NAV_INTEGRITY_PROCESS_OK)
    { return 1; }
    for (index = 0U; index < 160U; index++)
    {
        if (Integrity_Feed(receive_us, 0.5f) == 0U) { return 2; }
        receive_us += 40000U;
    }
    if ((s_decision.evidence_valid == 0U) ||
        (s_decision.state != NAV_INTEGRITY_TRUSTED) ||
        (s_decision.rolling_m > 0.01f)) { return 3; }
    generation = s_context.reference_generation;
    if (Integrity_Feed(receive_us, 99.0f) == 0U) { return 4; }
    if ((s_decision.evidence_valid != 0U) ||
        (s_context.reference_generation != generation) ||
        (s_decision.state != NAV_INTEGRITY_TRUSTED)) { return 5; }
    receive_us += 500000U;
    if (Integrity_Feed(receive_us, 0.5f) == 0U) { return 6; }
    if ((s_context.reference_trusted != 0U) ||
        (s_decision.state != NAV_INTEGRITY_SUSPECT) ||
        (s_context.healthy_count != 0U) ||
        (s_context.recovery_us != 0U)) { return 7; }
    for (index = 0U; index < 170U; index++)
    {
        receive_us += 40000U;
        if (Integrity_Feed(receive_us, 0.5f) == 0U) { return 8; }
    }
    if ((s_decision.state != NAV_INTEGRITY_RECOVERING) ||
        (s_decision.reanchor_requested != 0U) ||
        ((s_decision.admitted_group_mask & 1U) == 0U)) { return 9; }
    s_context.pending_reanchor = 1U;
    receive_us += 40000U;
    if (Integrity_Feed(receive_us, 99.0f) == 0U) { return 10; }
    if ((s_decision.reanchor_requested != 0U) ||
        (s_decision.evidence_valid != 0U) ||
        (s_context.pending_reanchor == 0U)) { return 11; }
    for (index = 0U; index < 5U; index++)
    { NavigationIntegrity_ReanchorAcknowledge(&s_context, 0U); }
    if ((s_context.pending_reanchor != 0U) ||
        (s_context.reanchor_withdrawn == 0U)) { return 12; }
    if (Integrity_AccelerationCheck() == 0U) { return 13; }
    (void)puts("navigation_integrity_host: 13 checks, 0 failures");
    return 0;
}
