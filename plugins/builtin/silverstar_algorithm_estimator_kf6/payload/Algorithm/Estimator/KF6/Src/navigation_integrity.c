#include "navigation_integrity.h"

#include <math.h>
#include <stddef.h>
#include <string.h>

#include "silverstar_assert.h"

_Static_assert(NAV_INTEGRITY_CAPACITY >= 272U, "25 Hz / 10 s evidence");
_Static_assert(NAV_INTEGRITY_CAPACITY < UINT16_MAX, "bounded index");
#define NAV_INTEGRITY_REANCHOR_MAX_ATTEMPTS 5U

typedef struct
{
    float position[2];
    float integral[2];
    uint32_t segment;
    uint8_t valid;
} NavigationIntegrityPoint;

static uint8_t NavigationIntegrity_Positive(float value)
{ return (uint8_t)(isfinite(value) && (value > 0.0f)); }

NavigationIntegrityProcessResult NavigationIntegrity_ConfigValidate(
    const NavigationIntegrityConfig *config)
{
    if (config == NULL) { return NAV_INTEGRITY_PROCESS_INVALID; }
    SILVERSTAR_ASSERT_OBJECT(config, NavigationIntegrityConfig,
                             SILVERSTAR_ASSERT_MODULE_ALGORITHM);
    if ((config->enabled > 1U) ||
        (config->window_us < 1000000U) ||
        (config->window_us > NAV_INTEGRITY_MAX_WINDOW_US) ||
        (config->max_gap_us < 40000U) || (config->max_gap_us > 1200000U) ||
        (config->max_evidence_age_us > 550000U) ||
        (config->reference_max_age_us <= config->window_us) ||
        (config->recovery_min_samples == 0U) ||
        (config->suspect_duration_us == 0U) ||
        (config->untrusted_duration_us == 0U) ||
        (config->recovery_duration_us == 0U))
    { return NAV_INTEGRITY_PROCESS_INVALID; }
    if ((NavigationIntegrity_Positive(config->rolling_threshold_m) == 0U) ||
        (NavigationIntegrity_Positive(config->anchored_threshold_m) == 0U) ||
        (NavigationIntegrity_Positive(config->recovery_rolling_m) == 0U) ||
        (NavigationIntegrity_Positive(config->recovery_anchored_m) == 0U) ||
        (NavigationIntegrity_Positive(config->hacc_max_m) == 0U) ||
        (NavigationIntegrity_Positive(config->sacc_max_mps) == 0U) ||
        (NavigationIntegrity_Positive(config->reference_renewal_max_m) == 0U) ||
        (NavigationIntegrity_Positive(config->reanchor_covariance_floor_m2) == 0U) ||
        !isfinite(config->velocity_bias_bound_mps) ||
        (config->velocity_bias_bound_mps < 0.0f) ||
        !isfinite(config->position_r_scale) ||
        (config->position_r_scale < 1.0f))
    { return NAV_INTEGRITY_PROCESS_INVALID; }
    SILVERSTAR_ASSERT(config->window_us <= NAV_INTEGRITY_MAX_WINDOW_US,
        SILVERSTAR_ASSERT_MODULE_ALGORITHM, SILVERSTAR_ASSERT_REASON_POSTCONDITION);
    return NAV_INTEGRITY_PROCESS_OK;
}

NavigationIntegrityProcessResult NavigationIntegrity_Reset(
    NavigationIntegrityContext *context, const NavigationIntegrityConfig *config)
{
    if ((context == NULL) ||
        (NavigationIntegrity_ConfigValidate(config) != NAV_INTEGRITY_PROCESS_OK))
    { return NAV_INTEGRITY_PROCESS_INVALID; }
    SILVERSTAR_ASSERT_OBJECT(context, NavigationIntegrityContext,
                             SILVERSTAR_ASSERT_MODULE_ALGORITHM);
    (void)memset(context, 0, sizeof(*context));
    context->config = *config;
    context->state = NAV_INTEGRITY_TRUSTED;
    context->velocity_segment = 1U;
    return NAV_INTEGRITY_PROCESS_OK;
}

static uint8_t NavigationIntegrity_InputValid(const NavigationIntegrityInput *input)
{
    uint8_t axis;
    if ((input == NULL) || (input->valid_group_mask > 15U) ||
        (input->receive_us == 0ULL) ||
        (input->position_us > input->receive_us) ||
        (input->velocity_us > input->receive_us))
    { return 0U; }
    for (axis = 0U; axis < 2U; axis++)
    {
        if (((input->valid_group_mask & 1U) != 0U) &&
            !isfinite(input->position_en[axis])) { return 0U; }
        if (((input->valid_group_mask & 4U) != 0U) &&
            !isfinite(input->velocity_en[axis])) { return 0U; }
    }
    return 1U;
}

static void NavigationIntegrity_SampleQualityApply(
    const NavigationIntegrityContext *context,
    const NavigationIntegrityInput *input, NavigationIntegritySample *sample)
{
    SILVERSTAR_ASSERT_OBJECT(context, NavigationIntegrityContext,
                             SILVERSTAR_ASSERT_MODULE_ALGORITHM);
    SILVERSTAR_ASSERT_OBJECT(input, NavigationIntegrityInput,
                             SILVERSTAR_ASSERT_MODULE_ALGORITHM);
    if ((NavigationIntegrity_Positive(input->hacc_m) == 0U) ||
        (input->hacc_m > context->config.hacc_max_m))
    { sample->valid_group_mask &= (uint8_t)~1U; }
    if ((NavigationIntegrity_Positive(input->sacc_mps) == 0U) ||
        (input->sacc_mps > context->config.sacc_max_mps))
    { sample->valid_group_mask &= (uint8_t)~4U; }
}

static NavigationIntegrityProcessResult NavigationIntegrity_Append(
    NavigationIntegrityContext *context, const NavigationIntegrityInput *input)
{
    NavigationIntegritySample *sample;
    uint16_t index;
    uint8_t axis;
    SILVERSTAR_ASSERT_OBJECT(context, NavigationIntegrityContext,
                             SILVERSTAR_ASSERT_MODULE_ALGORITHM);
    SILVERSTAR_ASSERT(context->count <= NAV_INTEGRITY_CAPACITY,
        SILVERSTAR_ASSERT_MODULE_ALGORITHM, SILVERSTAR_ASSERT_REASON_LENGTH_RANGE);
    if (context->count == NAV_INTEGRITY_CAPACITY)
    {
        uint32_t age_us = (uint32_t)((uint32_t)input->position_us -
                                     context->samples[0].position_us_lo);
        if (age_us < context->config.window_us + 550000U)
        { return NAV_INTEGRITY_PROCESS_CAPACITY; }
        for (index = 1U; index < NAV_INTEGRITY_CAPACITY; index++)
        { context->samples[index - 1U] = context->samples[index]; }
        context->count--;
    }
    index = context->count;
    SILVERSTAR_ASSERT(index < NAV_INTEGRITY_CAPACITY,
        SILVERSTAR_ASSERT_MODULE_ALGORITHM, SILVERSTAR_ASSERT_REASON_LENGTH_RANGE);
    sample = &context->samples[index];
    (void)memset(sample, 0, sizeof(*sample));
    sample->position_us_lo = (uint32_t)input->position_us;
    sample->velocity_us_lo = (uint32_t)input->velocity_us;
    sample->valid_group_mask = input->valid_group_mask;
    NavigationIntegrity_SampleQualityApply(context, input, sample);
    sample->velocity_segment = context->velocity_segment;
    for (axis = 0U; axis < 2U; axis++)
    {
        sample->position_en[axis] = input->position_en[axis];
        sample->velocity_en[axis] = input->velocity_en[axis];
    }
    if (index > 0U)
    {
        const NavigationIntegritySample *previous = &context->samples[index - 1U];
        if (((input->valid_group_mask & 4U) != 0U) &&
            ((previous->valid_group_mask & 4U) != 0U) &&
            (previous->velocity_segment == sample->velocity_segment))
        {
            float dt_s = (float)(input->velocity_us -
                                 context->previous_input.velocity_us) * 1e-6f;
            for (axis = 0U; axis < 2U; axis++)
            {
                sample->velocity_integral[axis] = previous->velocity_integral[axis] +
                    0.5f * (input->velocity_en[axis] +
                            previous->velocity_en[axis]) * dt_s;
            }
        }
    }
    context->count++;
    SILVERSTAR_ASSERT(context->count <= NAV_INTEGRITY_CAPACITY,
        SILVERSTAR_ASSERT_MODULE_ALGORITHM, SILVERSTAR_ASSERT_REASON_POSTCONDITION);
    context->previous_input = *input;
    return NAV_INTEGRITY_PROCESS_OK;
}

static uint8_t NavigationIntegrity_PositionAt(const NavigationIntegrityContext *context,
    uint64_t target_us, float output[2])
{
    uint16_t index;
    uint16_t left = NAV_INTEGRITY_CAPACITY;
    uint32_t target = (uint32_t)target_us;
    SILVERSTAR_ASSERT_OBJECT(output, float, SILVERSTAR_ASSERT_MODULE_ALGORITHM);
    SILVERSTAR_ASSERT(context->count <= NAV_INTEGRITY_CAPACITY,
        SILVERSTAR_ASSERT_MODULE_ALGORITHM, SILVERSTAR_ASSERT_REASON_LENGTH_RANGE);
    for (index = 0U; index < NAV_INTEGRITY_CAPACITY; index++)
    {
        const NavigationIntegritySample *sample;
        uint32_t span;
        float fraction;
        uint8_t axis;
        if (index >= context->count) { break; }
        sample = &context->samples[index];
        if ((sample->valid_group_mask & 1U) == 0U) { continue; }
        if (sample->position_us_lo == target)
        {
            output[0] = sample->position_en[0];
            output[1] = sample->position_en[1];
            return 1U;
        }
        if ((uint32_t)(sample->position_us_lo - target) >= 0x80000000U)
        { left = index; continue; }
        if (left >= context->count) { return 0U; }
        span = sample->position_us_lo - context->samples[left].position_us_lo;
        if ((span == 0U) || (span > context->config.max_gap_us)) { return 0U; }
        fraction = (float)(target - context->samples[left].position_us_lo) /
                   (float)span;
        for (axis = 0U; axis < 2U; axis++)
        {
            float first = context->samples[left].position_en[axis];
            output[axis] = first + fraction * (sample->position_en[axis] - first);
        }
        return 1U;
    }
    return 0U;
}

static uint8_t NavigationIntegrity_VelocityAt(const NavigationIntegrityContext *context,
    uint64_t target_us, float output[2], uint32_t *segment)
{
    uint16_t index;
    uint32_t target = (uint32_t)target_us;
    SILVERSTAR_ASSERT_OBJECT(output, float, SILVERSTAR_ASSERT_MODULE_ALGORITHM);
    SILVERSTAR_ASSERT_OBJECT(segment, uint32_t, SILVERSTAR_ASSERT_MODULE_ALGORITHM);
    SILVERSTAR_ASSERT(context->count <= NAV_INTEGRITY_CAPACITY,
        SILVERSTAR_ASSERT_MODULE_ALGORITHM, SILVERSTAR_ASSERT_REASON_LENGTH_RANGE);
    for (index = 0U; index < NAV_INTEGRITY_CAPACITY; index++)
    {
        const NavigationIntegritySample *right;
        const NavigationIntegritySample *left;
        uint32_t span;
        float fraction;
        float dt_s;
        uint8_t axis;
        if (index >= context->count) { break; }
        right = &context->samples[index];
        if ((uint32_t)(right->velocity_us_lo - target) >= 0x80000000U) { continue; }
        if ((right->valid_group_mask & 4U) == 0U) { return 0U; }
        *segment = right->velocity_segment;
        if (right->velocity_us_lo == target)
        {
            output[0] = right->velocity_integral[0];
            output[1] = right->velocity_integral[1];
            return 1U;
        }
        if (index == 0U) { return 0U; }
        left = &context->samples[index - 1U];
        span = right->velocity_us_lo - left->velocity_us_lo;
        if (((left->valid_group_mask & 4U) == 0U) ||
            (left->velocity_segment != right->velocity_segment) ||
            (span == 0U) || (span > context->config.max_gap_us))
        { return 0U; }
        fraction = (float)(target - left->velocity_us_lo) / (float)span;
        dt_s = (float)(target - left->velocity_us_lo) * 1e-6f;
        for (axis = 0U; axis < 2U; axis++)
        {
            float value = left->velocity_en[axis] + fraction *
                (right->velocity_en[axis] - left->velocity_en[axis]);
            output[axis] = left->velocity_integral[axis] + 0.5f *
                (left->velocity_en[axis] + value) * dt_s;
        }
        return 1U;
    }
    return 0U;
}

static float NavigationIntegrity_Distance(const float a[2], const float b[2])
{ return hypotf(a[0] - b[0], a[1] - b[1]); }

static void NavigationIntegrity_ReferenceStart(NavigationIntegrityContext *context,
    const NavigationIntegrityDecision *decision, const NavigationIntegrityPoint *end)
{
    if ((context->reference_us != 0ULL) ||
        (context->state != NAV_INTEGRITY_TRUSTED)) { return; }
    context->reference_us = decision->evidence_cutoff_us;
    context->reference_position[0] = end->position[0];
    context->reference_position[1] = end->position[1];
    context->reference_integral[0] = end->integral[0];
    context->reference_integral[1] = end->integral[1];
    context->reference_velocity_segment = end->segment;
    context->reference_generation++;
    context->reference_trusted = 1U;
}

static void NavigationIntegrity_ReferenceProcess(NavigationIntegrityContext *context,
    NavigationIntegrityDecision *decision, const NavigationIntegrityPoint *end)
{
    float displacement[2];
    float velocity_delta[2];
    float residual[2];
    uint8_t axis;
    uint64_t age_us;
    SILVERSTAR_ASSERT_OBJECT(context, NavigationIntegrityContext,
                             SILVERSTAR_ASSERT_MODULE_ALGORITHM);
    SILVERSTAR_ASSERT_OBJECT(decision, NavigationIntegrityDecision,
                             SILVERSTAR_ASSERT_MODULE_ALGORITHM);
    SILVERSTAR_ASSERT_OBJECT(end, NavigationIntegrityPoint,
                             SILVERSTAR_ASSERT_MODULE_ALGORITHM);
    if (context->reference_us == 0ULL)
    { NavigationIntegrity_ReferenceStart(context, decision, end); return; }
    if (context->reference_trusted == 0U) { return; }
    if (end->segment != context->reference_velocity_segment)
    { context->reference_trusted = 0U; return; }
    for (axis = 0U; axis < 2U; axis++)
    {
        displacement[axis] = end->position[axis] - context->reference_position[axis];
        velocity_delta[axis] = end->integral[axis] - context->reference_integral[axis];
        residual[axis] = displacement[axis] - velocity_delta[axis];
    }
    decision->anchored_m = hypotf(residual[0], residual[1]);
    age_us = decision->evidence_cutoff_us - context->reference_us;
    if (age_us > context->config.reference_max_age_us)
    {
        if ((context->state == NAV_INTEGRITY_TRUSTED) &&
            isfinite(decision->rolling_m) &&
            (decision->rolling_m <= context->config.recovery_rolling_m) &&
            (decision->anchored_m <= context->config.reference_renewal_max_m))
        {
            context->reference_us = decision->evidence_cutoff_us;
            context->reference_position[0] = end->position[0];
            context->reference_position[1] = end->position[1];
            context->reference_integral[0] = end->integral[0];
            context->reference_integral[1] = end->integral[1];
            context->reference_generation++;
            decision->anchored_m = 0.0f;
        }
        else
        {
            context->reference_trusted = 0U;
            if (context->state == NAV_INTEGRITY_TRUSTED)
            { context->state = NAV_INTEGRITY_SUSPECT; }
        }
    }
}

static void NavigationIntegrity_EvidenceProcess(NavigationIntegrityContext *context,
    NavigationIntegrityDecision *decision)
{
    NavigationIntegrityPoint end = {0};
    NavigationIntegrityPoint start = {0};
    uint64_t cutoff_us = decision->evidence_cutoff_us;
    uint64_t start_us;
    float position_delta[2];
    float velocity_delta[2];
    uint32_t segment;
    SILVERSTAR_ASSERT_OBJECT(context, NavigationIntegrityContext,
                             SILVERSTAR_ASSERT_MODULE_ALGORITHM);
    SILVERSTAR_ASSERT_OBJECT(decision, NavigationIntegrityDecision,
                             SILVERSTAR_ASSERT_MODULE_ALGORITHM);
    if (NavigationIntegrity_PositionAt(context, cutoff_us, end.position) == 0U)
    { decision->reason = NAV_INTEGRITY_REASON_POSITION_INVALID; return; }
    if (NavigationIntegrity_VelocityAt(context, cutoff_us,
                                      end.integral, &segment) == 0U)
    { decision->reason = NAV_INTEGRITY_REASON_VELOCITY_INVALID; return; }
    end.valid = 1U;
    end.segment = segment;
    NavigationIntegrity_ReferenceStart(context, decision, &end);
    if (cutoff_us < context->config.window_us)
    { decision->reason = NAV_INTEGRITY_REASON_WARMUP; return; }
    start_us = cutoff_us - context->config.window_us;
    if (NavigationIntegrity_PositionAt(context, start_us, start.position) == 0U)
    { decision->reason = NAV_INTEGRITY_REASON_WARMUP; return; }
    if (NavigationIntegrity_VelocityAt(context, start_us,
                                      start.integral, &segment) == 0U)
    { decision->reason = NAV_INTEGRITY_REASON_VELOCITY_INVALID; return; }
    start.segment = segment;
    if (start.segment != end.segment)
    { decision->reason = NAV_INTEGRITY_REASON_TIME_GAP; return; }
    position_delta[0] = end.position[0] - start.position[0];
    position_delta[1] = end.position[1] - start.position[1];
    velocity_delta[0] = end.integral[0] - start.integral[0];
    velocity_delta[1] = end.integral[1] - start.integral[1];
    decision->rolling_m = NavigationIntegrity_Distance(position_delta, velocity_delta);
    decision->evidence_valid = 1U;
    NavigationIntegrity_ReferenceProcess(context, decision, &end);
}

static NavigationIntegrityProcessResult NavigationIntegrity_Prepare(
    NavigationIntegrityContext *context, const NavigationIntegrityInput *input,
    uint32_t *delta_us)
{
    const NavigationIntegrityInput *previous;
    uint64_t span;
    uint8_t discontinuity;
    SILVERSTAR_ASSERT_OBJECT(context, NavigationIntegrityContext,
                             SILVERSTAR_ASSERT_MODULE_ALGORITHM);
    SILVERSTAR_ASSERT_OBJECT(input, NavigationIntegrityInput,
                             SILVERSTAR_ASSERT_MODULE_ALGORITHM);
    SILVERSTAR_ASSERT(delta_us != NULL, SILVERSTAR_ASSERT_MODULE_ALGORITHM,
                      SILVERSTAR_ASSERT_REASON_NULL_POINTER);
    if (context->count == 0U) { *delta_us = 0U; return NAV_INTEGRITY_PROCESS_OK; }
    previous = &context->previous_input;
    if ((context->count == NAV_INTEGRITY_CAPACITY) &&
        ((uint32_t)((uint32_t)input->position_us -
                    context->samples[0].position_us_lo) <
         context->config.window_us + 550000U))
    { return NAV_INTEGRITY_PROCESS_CAPACITY; }
    if ((input->receive_us <= previous->receive_us) ||
        (input->position_us <= previous->position_us) ||
        (input->velocity_us <= previous->velocity_us) ||
        ((input->epoch == previous->epoch) &&
         ((uint32_t)(input->sequence - previous->sequence) == 0U)))
    { return NAV_INTEGRITY_PROCESS_DUPLICATE; }
    span = input->receive_us - previous->receive_us;
    *delta_us = (span > UINT32_MAX) ? UINT32_MAX : (uint32_t)span;
    discontinuity = (uint8_t)(
        (input->epoch != previous->epoch) ||
        ((uint32_t)(input->sequence - previous->sequence) != 1U) ||
        (input->velocity_us - previous->velocity_us > context->config.max_gap_us) ||
        ((context->samples[context->count - 1U].valid_group_mask & 4U) == 0U));
    if (discontinuity != 0U)
    {
        context->velocity_segment++;
        context->reference_trusted = 0U;
        context->abnormal_us = 0U;
        context->healthy_us = 0U;
        context->recovery_us = 0U;
        context->healthy_count = 0U;
        context->pending_reanchor = 0U;
        context->reanchor_attempts = 0U;
        if (context->state == NAV_INTEGRITY_RECOVERING)
        { context->state = NAV_INTEGRITY_UNTRUSTED; }
        if (context->state == NAV_INTEGRITY_TRUSTED)
        { context->state = NAV_INTEGRITY_SUSPECT; }
    }
    return NAV_INTEGRITY_PROCESS_OK;
}

static uint32_t NavigationIntegrity_AddDuration(uint32_t elapsed, uint32_t delta_us)
{ return (elapsed > UINT32_MAX - delta_us) ? UINT32_MAX : elapsed + delta_us; }

static void NavigationIntegrity_RecoveryBegin(NavigationIntegrityContext *context)
{
    SILVERSTAR_ASSERT_OBJECT(context, NavigationIntegrityContext,
                             SILVERSTAR_ASSERT_MODULE_ALGORITHM);
    context->state = NAV_INTEGRITY_RECOVERING;
    context->healthy_count = 0U;
    context->recovery_us = 0U;
    context->pending_reanchor = context->reference_trusted;
    context->reanchor_attempts = 0U;
    context->reanchor_withdrawn = 0U;
}

static void NavigationIntegrity_TransitionApply(NavigationIntegrityContext *context,
    uint8_t abnormal, uint8_t healthy)
{
    const NavigationIntegrityConfig *config = &context->config;
    SILVERSTAR_ASSERT_OBJECT(context, NavigationIntegrityContext,
                             SILVERSTAR_ASSERT_MODULE_ALGORITHM);
    SILVERSTAR_ASSERT(context->state <= NAV_INTEGRITY_RECOVERING,
        SILVERSTAR_ASSERT_MODULE_ALGORITHM, SILVERSTAR_ASSERT_REASON_ENUM_RANGE);
    if ((context->state == NAV_INTEGRITY_TRUSTED) &&
        (context->abnormal_us >= config->suspect_duration_us))
    { context->state = NAV_INTEGRITY_SUSPECT; }
    else if (context->state == NAV_INTEGRITY_SUSPECT)
    {
        if (context->abnormal_us >= config->suspect_duration_us +
                                     config->untrusted_duration_us)
        { context->state = NAV_INTEGRITY_UNTRUSTED; }
        else if ((context->reference_trusted != 0U) &&
                 (context->healthy_us >= config->suspect_duration_us))
        { context->state = NAV_INTEGRITY_TRUSTED; }
        else if ((context->reference_trusted == 0U) &&
                 (healthy != 0U) &&
                 (context->healthy_count >= config->recovery_min_samples) &&
                 (context->recovery_us >= config->recovery_duration_us))
        { NavigationIntegrity_RecoveryBegin(context); }
    }
    else if (context->state == NAV_INTEGRITY_UNTRUSTED)
    {
        if ((healthy != 0U) &&
            (context->healthy_count >= config->recovery_min_samples) &&
            (context->recovery_us >= config->recovery_duration_us))
        { NavigationIntegrity_RecoveryBegin(context); }
    }
    else if (context->state == NAV_INTEGRITY_RECOVERING)
    {
        if (abnormal != 0U)
        {
            context->state = NAV_INTEGRITY_UNTRUSTED;
            context->recovery_us = 0U;
            context->healthy_count = 0U;
            context->pending_reanchor = 0U;
        }
        else if ((healthy != 0U) &&
                 (context->healthy_count >= config->recovery_min_samples) &&
                 (context->recovery_us >= config->recovery_duration_us) &&
                 (context->pending_reanchor == 0U) &&
                 (context->reference_trusted != 0U) &&
                 (context->reanchor_withdrawn == 0U))
        { context->state = NAV_INTEGRITY_TRUSTED; }
    }
    SILVERSTAR_ASSERT(context->state <= NAV_INTEGRITY_RECOVERING,
        SILVERSTAR_ASSERT_MODULE_ALGORITHM, SILVERSTAR_ASSERT_REASON_POSTCONDITION);
}

static void NavigationIntegrity_StateAdvance(NavigationIntegrityContext *context,
    const NavigationIntegrityDecision *decision, uint32_t delta_us,
    uint8_t abnormal, uint8_t healthy)
{
    const NavigationIntegrityConfig *config = &context->config;
    uint8_t contiguous = (uint8_t)((delta_us > 0U) &&
                                    (delta_us <= config->max_gap_us));
    SILVERSTAR_ASSERT_OBJECT(context, NavigationIntegrityContext,
                             SILVERSTAR_ASSERT_MODULE_ALGORITHM);
    SILVERSTAR_ASSERT_OBJECT(decision, NavigationIntegrityDecision,
                             SILVERSTAR_ASSERT_MODULE_ALGORITHM);
    if ((decision->evidence_valid != 0U) && (contiguous != 0U))
    {
        if (abnormal != 0U)
        {
            context->abnormal_us =
                NavigationIntegrity_AddDuration(context->abnormal_us, delta_us);
            context->healthy_us = 0U;
        }
        else if (healthy != 0U)
        {
            context->healthy_us =
                NavigationIntegrity_AddDuration(context->healthy_us, delta_us);
            context->abnormal_us = 0U;
        }
        else { context->abnormal_us = 0U; context->healthy_us = 0U; }
    }
    else if (decision->evidence_valid != 0U)
    { context->abnormal_us = 0U; context->healthy_us = 0U; }
    if (healthy != 0U)
    {
        if (context->healthy_count < UINT16_MAX) { context->healthy_count++; }
        if (contiguous != 0U)
        {
            context->recovery_us =
                NavigationIntegrity_AddDuration(context->recovery_us, delta_us);
        }
    }
    else if (decision->evidence_valid != 0U)
    { context->healthy_count = 0U; context->recovery_us = 0U; }
    NavigationIntegrity_TransitionApply(context, abnormal, healthy);
}

static void NavigationIntegrity_DecisionReset(const NavigationIntegrityInput *input,
    NavigationIntegrityDecision *decision)
{
    (void)memset(decision, 0, sizeof(*decision));
    decision->decision_us = input->receive_us;
    decision->evidence_cutoff_us = (input->position_us < input->velocity_us) ?
        input->position_us : input->velocity_us;
    decision->admitted_group_mask = input->valid_group_mask;
    decision->rolling_m = NAN;
    decision->anchored_m = NAN;
    decision->reason = NAV_INTEGRITY_REASON_WARMUP;
}

static uint8_t NavigationIntegrity_QualityReady(
    const NavigationIntegrityContext *context,
    const NavigationIntegrityInput *input,
    NavigationIntegrityDecision *decision)
{
    SILVERSTAR_ASSERT_OBJECT(context, NavigationIntegrityContext,
                             SILVERSTAR_ASSERT_MODULE_ALGORITHM);
    SILVERSTAR_ASSERT_OBJECT(input, NavigationIntegrityInput,
                             SILVERSTAR_ASSERT_MODULE_ALGORITHM);
    if (((input->valid_group_mask & 5U) == 5U) &&
        ((NavigationIntegrity_Positive(input->hacc_m) == 0U) ||
         (NavigationIntegrity_Positive(input->sacc_mps) == 0U) ||
         (input->hacc_m > context->config.hacc_max_m) ||
         (input->sacc_mps > context->config.sacc_max_mps)))
    { decision->reason = NAV_INTEGRITY_REASON_QUALITY; return 0U; }
    if ((input->receive_us < decision->evidence_cutoff_us) ||
        (input->receive_us - decision->evidence_cutoff_us >
         context->config.max_evidence_age_us))
    { decision->reason = NAV_INTEGRITY_REASON_EVIDENCE_AGE; return 0U; }
    return 1U;
}

static void NavigationIntegrity_QualityApply(const NavigationIntegrityContext *context,
    const NavigationIntegrityInput *input, NavigationIntegrityDecision *decision,
    uint8_t *abnormal, uint8_t *healthy)
{
    float limit;
    SILVERSTAR_ASSERT_OBJECT(context, NavigationIntegrityContext,
                             SILVERSTAR_ASSERT_MODULE_ALGORITHM);
    SILVERSTAR_ASSERT_OBJECT(input, NavigationIntegrityInput,
                             SILVERSTAR_ASSERT_MODULE_ALGORITHM);
    SILVERSTAR_ASSERT_OBJECT(decision, NavigationIntegrityDecision,
                             SILVERSTAR_ASSERT_MODULE_ALGORITHM);
    if (((input->valid_group_mask & 5U) != 5U) ||
        (NavigationIntegrity_Positive(input->hacc_m) == 0U) ||
        (NavigationIntegrity_Positive(input->sacc_mps) == 0U) ||
        (input->hacc_m > context->config.hacc_max_m) ||
        (input->sacc_mps > context->config.sacc_max_mps))
    { decision->evidence_valid = 0U; decision->reason = NAV_INTEGRITY_REASON_QUALITY; }
    else if ((input->receive_us < decision->evidence_cutoff_us) ||
        (input->receive_us - decision->evidence_cutoff_us >
         context->config.max_evidence_age_us))
    {
        decision->evidence_valid = 0U;
        decision->reason = NAV_INTEGRITY_REASON_EVIDENCE_AGE;
    }
    if (decision->evidence_valid == 0U) { return; }
    uint64_t age_us = decision->evidence_cutoff_us - context->reference_us;
    limit = context->config.anchored_threshold_m +
        context->config.velocity_bias_bound_mps * (float)age_us * 1e-6f;
    *abnormal = (uint8_t)(
        (decision->rolling_m > context->config.rolling_threshold_m) ||
        ((context->reference_trusted != 0U) && (decision->anchored_m > limit)));
    *healthy = (uint8_t)((decision->rolling_m <= context->config.recovery_rolling_m) &&
        ((context->reference_trusted == 0U) ||
         (decision->anchored_m <= context->config.recovery_anchored_m)));
    decision->reason = (context->reference_trusted == 0U) ?
        NAV_INTEGRITY_REASON_REFERENCE_EXPIRED :
        ((*abnormal != 0U) ? NAV_INTEGRITY_REASON_CLOSURE_ABNORMAL :
         NAV_INTEGRITY_REASON_HEALTHY);
}

static void NavigationIntegrity_DecisionFinalize(const NavigationIntegrityContext *context,
    NavigationIntegrityDecision *decision)
{
    SILVERSTAR_ASSERT_OBJECT(context, NavigationIntegrityContext,
                             SILVERSTAR_ASSERT_MODULE_ALGORITHM);
    SILVERSTAR_ASSERT_OBJECT(decision, NavigationIntegrityDecision,
                             SILVERSTAR_ASSERT_MODULE_ALGORITHM);
    decision->state = context->state;
    decision->reference_generation = context->reference_generation;
    decision->position_r_scale = ((context->state == NAV_INTEGRITY_SUSPECT) ||
        (context->state == NAV_INTEGRITY_RECOVERING)) ?
        context->config.position_r_scale : 1.0f;
    if (context->state == NAV_INTEGRITY_UNTRUSTED)
    { decision->admitted_group_mask &= (uint8_t)~1U; }
    decision->reanchor_requested = (uint8_t)((context->pending_reanchor != 0U) &&
        (decision->evidence_valid != 0U) &&
        ((decision->admitted_group_mask & 1U) != 0U));
}

NavigationIntegrityProcessResult NavigationIntegrity_Receive(
    NavigationIntegrityContext *context, const NavigationIntegrityInput *input,
    NavigationIntegrityDecision *decision)
{
    NavigationIntegrityProcessResult result;
    uint32_t delta_us;
    uint8_t abnormal = 0U;
    uint8_t healthy = 0U;
    if ((context == NULL) || (decision == NULL) ||
        (NavigationIntegrity_InputValid(input) == 0U))
    { return NAV_INTEGRITY_PROCESS_INVALID; }
    SILVERSTAR_ASSERT_OBJECT(context, NavigationIntegrityContext,
                             SILVERSTAR_ASSERT_MODULE_ALGORITHM);
    SILVERSTAR_ASSERT_OBJECT(decision, NavigationIntegrityDecision,
                             SILVERSTAR_ASSERT_MODULE_ALGORITHM);
    NavigationIntegrity_DecisionReset(input, decision);
    if (context->config.enabled == 0U)
    {
        decision->state = NAV_INTEGRITY_TRUSTED;
        decision->position_r_scale = 1.0f;
        return NAV_INTEGRITY_PROCESS_OK;
    }
    result = NavigationIntegrity_Prepare(context, input, &delta_us);
    if (result != NAV_INTEGRITY_PROCESS_OK) { return result; }
    result = NavigationIntegrity_Append(context, input);
    if (result != NAV_INTEGRITY_PROCESS_OK) { return result; }
    if (NavigationIntegrity_QualityReady(context, input, decision) != 0U)
    {
        NavigationIntegrity_EvidenceProcess(context, decision);
        NavigationIntegrity_QualityApply(context, input, decision, &abnormal, &healthy);
    }
    NavigationIntegrity_StateAdvance(context, decision, delta_us, abnormal, healthy);
    NavigationIntegrity_DecisionFinalize(context, decision);
    return NAV_INTEGRITY_PROCESS_OK;
}

void NavigationIntegrity_ReanchorAcknowledge(NavigationIntegrityContext *context,
                                             uint8_t succeeded)
{
    if ((context == NULL) || (context->pending_reanchor == 0U)) { return; }
    if (succeeded != 0U)
    {
        context->pending_reanchor = 0U;
        context->reanchor_attempts = 0U;
        return;
    }
    if (context->reanchor_attempts < NAV_INTEGRITY_REANCHOR_MAX_ATTEMPTS)
    { context->reanchor_attempts++; }
    if (context->reanchor_attempts >= NAV_INTEGRITY_REANCHOR_MAX_ATTEMPTS)
    {
        context->pending_reanchor = 0U;
        context->reanchor_withdrawn = 1U;
    }
}
