#include "navigation_kf_replay.h"
#include "system_user_config.h"

#include <math.h>
#include <stddef.h>
#include <string.h>

static NavigationReplayResult NavigationReplay_Reject(
    NavigationReplayContext *history, NavigationReplayResult result)
{
    if (history != NULL)
    {
        history->diagnostics.last_result = result;
        history->diagnostics.rejection_count++;
        if (result == NAV_REPLAY_HISTORY_MISS)
        { history->diagnostics.history_miss_count++; }
        if (result == NAV_REPLAY_OVERFLOW)
        { history->diagnostics.overflow_count++; }
    }
    return result;
}

void NavigationReplay_Reset(NavigationReplayContext *history,
                            NavigationReplayStorage *storage,
                            const NavigationKfContext *state,
                            uint64_t timestamp_us, uint32_t epoch)
{
    if ((history == NULL) || (storage == NULL) || (state == NULL)) { return; }
    (void)memset(history, 0, sizeof(*history));
    (void)memset(storage, 0, sizeof(*storage));
    history->storage = storage;
    history->epoch = epoch;
    history->present_us = timestamp_us;
    history->epoch_start_us = timestamp_us;
    history->storage->checkpoints[0].timestamp_us = timestamp_us;
    history->storage->checkpoints[0].state = *state;
    history->checkpoint_count = 1U;
    history->receive_tracker = *state;
}

static uint64_t NavigationReplay_EventTimeGet(
    const NavigationReplayContext *history, uint16_t index)
{
    uint16_t slot = history->event_order[index];
    return (slot < NAV_REPLAY_GNSS_CAPACITY) ?
        history->events[slot].measurement_timestamp_us :
        history->barometer[slot - NAV_REPLAY_GNSS_CAPACITY].measurement_timestamp_us;
}

static const NavigationReplayEvent *NavigationReplay_EventGet(
    NavigationReplayContext *history, uint16_t index)
{
    uint16_t slot = history->event_order[index];
    const NavigationReplayBarometerEvent *barometer;
    if (slot < NAV_REPLAY_GNSS_CAPACITY) { return &history->events[slot]; }
    barometer = &history->barometer[slot - NAV_REPLAY_GNSS_CAPACITY];
    (void)memset(&history->event_work, 0, sizeof(history->event_work));
    history->event_work.measurement_timestamp_us = barometer->measurement_timestamp_us;
    history->event_work.receive_timestamp_us = barometer->receive_timestamp_us;
    history->event_work.epoch = barometer->epoch;
    history->event_work.sequence = barometer->sequence;
    history->event_work.source = barometer->source;
    history->event_work.kind = NAV_REPLAY_BAROMETER;
    history->event_work.altitude = barometer->altitude;
    history->event_work.altitude_variance = barometer->altitude_variance;
    return &history->event_work;
}

static uint16_t NavigationReplay_EventStore(
    NavigationReplayContext *history, const NavigationReplayEvent *event)
{
    uint16_t slot;
    if (event->kind == NAV_REPLAY_BAROMETER)
    {
        for (slot = 0U; slot < NAV_REPLAY_BARO_CAPACITY; slot++)
        {
            NavigationReplayBarometerEvent *barometer = &history->barometer[slot];
            if (barometer->occupied != 0U) { continue; }
            barometer->measurement_timestamp_us = event->measurement_timestamp_us;
            barometer->receive_timestamp_us = event->receive_timestamp_us;
            barometer->epoch = event->epoch;
            barometer->sequence = event->sequence;
            barometer->source = event->source;
            barometer->altitude = event->altitude;
            barometer->altitude_variance = event->altitude_variance;
            barometer->occupied = 1U;
            return (uint16_t)(NAV_REPLAY_GNSS_CAPACITY + slot);
        }
    }
    else
    {
        for (slot = 0U; slot < NAV_REPLAY_GNSS_CAPACITY; slot++)
        {
            if (history->events[slot].kind != 0U) { continue; }
            history->events[slot] = *event;
            return slot;
        }
    }
    return UINT16_MAX;
}

static void NavigationReplay_Prune(NavigationReplayContext *history)
{
    uint64_t oldest;
    uint16_t remove = 0U;
    /* Keep the nearest checkpoint at or before the time-window boundary.
     * Do not silently shorten the promised window at a higher input rate. */
    while ((history->checkpoint_count > 1U) &&
           (history->present_us >= NAV_REPLAY_WINDOW_US) &&
           (history->storage->checkpoints[1].timestamp_us <=
            history->present_us - NAV_REPLAY_WINDOW_US))
    {
        history->checkpoint_count--;
        (void)memmove(history->storage->checkpoints, &history->storage->checkpoints[1],
                      history->checkpoint_count * sizeof(history->storage->checkpoints[0]));
    }
    oldest = history->storage->checkpoints[0].timestamp_us;
    while ((history->imu_count != 0U) &&
           (history->storage->imu[history->imu_head].end_us <= oldest))
    {
        history->imu_head = (uint16_t)((history->imu_head + 1U) %
                                       NAV_REPLAY_IMU_CAPACITY);
        history->imu_count--;
    }
    while ((remove < history->event_count) &&
           (NavigationReplay_EventTimeGet(history, remove) < oldest))
    {
        uint16_t slot = history->event_order[remove];
        if (slot < NAV_REPLAY_GNSS_CAPACITY) { history->events[slot].kind = 0U; }
        else { history->barometer[slot - NAV_REPLAY_GNSS_CAPACITY].occupied = 0U; }
        remove++;
    }
    if (remove != 0U)
    {
        history->event_count -= remove;
        (void)memmove(history->event_order, &history->event_order[remove],
                      history->event_count * sizeof(history->event_order[0]));
    }
}

static uint8_t NavigationReplay_ModelMatches(
    const NavigationReplayContext *history, const NavigationKfContext *state)
{
    const NavigationKfContext *initial = &history->storage->checkpoints[0].state;
    return (uint8_t)(
        (memcmp(initial->process_accel_std_mps2, state->process_accel_std_mps2,
                sizeof(state->process_accel_std_mps2)) == 0) &&
        (initial->baro_std_m == state->baro_std_m) &&
        (memcmp(initial->nis_soft_threshold, state->nis_soft_threshold,
                sizeof(state->nis_soft_threshold)) == 0) &&
        (memcmp(initial->nis_hard_threshold, state->nis_hard_threshold,
                sizeof(state->nis_hard_threshold)) == 0) &&
        (initial->nis_max_r_scale == state->nis_max_r_scale));
}

static uint8_t NavigationReplay_EventValid(const NavigationReplayEvent *event)
{
    uint8_t axis;
    if ((event->kind == 0U) || (event->kind > NAV_REPLAY_BAROMETER) ||
        (event->vertical_valid > 1U) || (event->receive_timestamp_us == 0U))
    { return 0U; }
    for (axis = 0U; axis < 3U; axis++)
    {
        if (((event->kind & NAV_REPLAY_POSITION) != 0U) &&
            ((event->valid_group_mask & 3U) != 0U) &&
            ((!isfinite(event->position[axis])) || (!isfinite(event->position_variance[axis])) ||
             (event->position_variance[axis] <= 0.0f)))
        { return 0U; }
        if (((event->kind & NAV_REPLAY_VELOCITY) != 0U) &&
            ((event->valid_group_mask & 4U) != 0U) &&
            ((axis < 2U) || (event->vertical_valid != 0U)) &&
            ((!isfinite(event->velocity[axis])) || (!isfinite(event->velocity_variance[axis])) ||
             (event->velocity_variance[axis] <= 0.0f)))
        { return 0U; }
    }
    if (((event->kind & NAV_REPLAY_BAROMETER) != 0U) &&
        ((!isfinite(event->altitude)) || (!isfinite(event->altitude_variance)) ||
         (event->altitude_variance <= 0.0f)))
    { return 0U; }
    return 1U;
}

NavigationReplayResult NavigationReplay_Predict(
    NavigationReplayContext *history, NavigationKfContext *state,
    uint64_t timestamp_us, const float delta_velocity[3], float dt_s)
{
    NavigationReplayImu *imu;
    uint64_t duration_us;
    uint8_t index;
    if ((history == NULL) || (state == NULL) || (delta_velocity == NULL) ||
        (history->faulted != 0U) || (history->checkpoint_count == 0U) ||
        (!isfinite(dt_s)) || (dt_s <= 0.0f) || (dt_s > SYSTEM_KF_PREDICTION_DT_MAX_S))
    { return NavigationReplay_Reject(history, NAV_REPLAY_INVALID); }
    for (index = 0U; index < 3U; index++)
    {
        if (!isfinite(delta_velocity[index]))
        { return NavigationReplay_Reject(history, NAV_REPLAY_INVALID); }
    }
    if (NavigationReplay_ModelMatches(history, state) == 0U)
    {
        history->faulted = 1U;
        return NavigationReplay_Reject(history, NAV_REPLAY_EPOCH_MISMATCH);
    }
    duration_us = (uint64_t)((double)dt_s * 1000000.0 + 0.5);
    if ((history->prediction_count == 0U) && (history->present_us == 0U) &&
        (timestamp_us >= duration_us))
    {
        history->present_us = timestamp_us - duration_us;
        history->epoch_start_us = history->present_us;
        history->storage->checkpoints[0].timestamp_us = history->present_us;
    }
    if ((timestamp_us <= history->present_us) ||
        (timestamp_us - history->present_us > duration_us + 1U) ||
        (timestamp_us - history->present_us + 1U < duration_us))
    {
        history->faulted = 1U;
        return NavigationReplay_Reject(history, NAV_REPLAY_DISCONTINUITY);
    }
    NavigationReplay_Prune(history);
    if ((history->imu_count >= NAV_REPLAY_IMU_CAPACITY) ||
        ((((history->prediction_count + 1U) % NAV_REPLAY_CHECKPOINT_STRIDE) == 0U) &&
         (history->checkpoint_count >= NAV_REPLAY_CHECKPOINT_CAPACITY)))
    {
        history->faulted = 1U;
        return NavigationReplay_Reject(history, NAV_REPLAY_OVERFLOW);
    }
    history->working = *state;
    if (NavigationKf_Predict(&history->working, delta_velocity, dt_s) == 0U)
    {
        history->faulted = 1U;
        return NavigationReplay_Reject(history, NAV_REPLAY_NUMERIC_ERROR);
    }
    imu = &history->storage->imu[(history->imu_head + history->imu_count) %
                        NAV_REPLAY_IMU_CAPACITY];
    imu->start_us = history->present_us;
    imu->end_us = timestamp_us;
    imu->dt_s = dt_s;
    (void)memcpy(imu->delta_velocity, delta_velocity, sizeof(imu->delta_velocity));
    history->imu_count++;
    history->prediction_count++;
    history->present_us = timestamp_us;
    *state = history->working;
    if ((history->prediction_count % NAV_REPLAY_CHECKPOINT_STRIDE) == 0U)
    {
        history->storage->checkpoints[history->checkpoint_count].timestamp_us = timestamp_us;
        history->storage->checkpoints[history->checkpoint_count].state = *state;
        history->checkpoint_count++;
        NavigationReplay_Prune(history);
    }
    history->diagnostics.last_result = NAV_REPLAY_OK;
    return NAV_REPLAY_OK;
}

NavigationReplayResult NavigationReplay_ReceiveTrack(
    NavigationReplayContext *history, const NavigationKfGnssEpoch *receive_epoch,
    NavigationReplayEvent *event)
{
    uint8_t group;
    const NavigationKfGnssReacquisitionContext *tracker;
    if ((history == NULL) || (receive_epoch == NULL) || (event == NULL) ||
        (receive_epoch->timestamp_us == 0U))
    { return NavigationReplay_Reject(history, NAV_REPLAY_INVALID); }
    if (receive_epoch->timestamp_us < history->epoch_start_us)
    { return NavigationReplay_Reject(history, NAV_REPLAY_HISTORY_MISS); }
    /* This is the existing availability/consistency implementation. The only
     * clock supplied to it is the actual packet receive clock. Never replay it. */
    NavigationKf_GnssEpochTrack(&history->receive_tracker, receive_epoch);
    tracker = &history->receive_tracker.gnss_reacquisition;
    event->receive_timestamp_us = receive_epoch->timestamp_us;
    event->epoch = history->epoch;
    event->valid_group_mask = receive_epoch->valid_group_mask;
    event->consistency_mask = tracker->consistency_mask;
    for (group = 0U; group < NAV_KF_GNSS_GROUP_COUNT; group++)
    {
        event->evidence[group].availability_timestamp_us =
            tracker->group[group].availability_timestamp_us;
        event->evidence[group].generation = tracker->group[group].generation;
        event->evidence[group].consistent_count = tracker->group[group].consistent_count;
        event->evidence[group].outage = tracker->group[group].outage;
        event->evidence[group].loss_latched = tracker->group[group].loss_latched;
        event->evidence[group].recovery_valid = (uint8_t)(
            (tracker->previous_epoch.valid_group_mask & NAV_KF_GNSS_GROUP_MASK(group)) != 0U);
    }
    return NAV_REPLAY_OK;
}

static void NavigationReplay_EvidenceApply(NavigationKfContext *state,
                                          const NavigationReplayEvent *event)
{
    uint8_t group;
    NavigationKfGnssReacquisitionContext *reacquisition = &state->gnss_reacquisition;
    for (group = 0U; group < NAV_KF_GNSS_GROUP_COUNT; group++)
    {
        uint8_t bit = NAV_KF_GNSS_GROUP_MASK(group);
        NavigationKfGnssReacquireGroupState *target = &reacquisition->group[group];
        const NavigationReplayGroupEvidence *source = &event->evidence[group];
        if (((group < 2U) && ((event->kind & NAV_REPLAY_POSITION) == 0U)) ||
            ((group >= 2U) && ((event->kind & NAV_REPLAY_VELOCITY) == 0U)))
        { continue; }
        if (target->generation != source->generation)
        {
            (void)memset(target, 0, sizeof(*target));
            target->generation = source->generation;
            target->outage = source->outage;
            reacquisition->active_mask &= (uint8_t)~bit;
        }
        target->availability_timestamp_us = source->availability_timestamp_us;
        target->loss_latched = source->loss_latched;
        target->consistent_count = source->consistent_count;
        if (source->recovery_valid == 0U)
        {
            target->reject_streak = 0U;
            target->accepted_streak = 0U;
        }
        reacquisition->previous_epoch.valid_group_mask = (uint8_t)(
            (reacquisition->previous_epoch.valid_group_mask & (uint8_t)~bit) |
            ((source->recovery_valid != 0U) ? bit : 0U));
        reacquisition->consistency_mask = (uint8_t)(
            (reacquisition->consistency_mask & (uint8_t)~bit) |
            (event->consistency_mask & bit));
    }
}

static void NavigationReplay_OutcomeReset(NavigationReplayOutcome *outcome)
{
    (void)memset(outcome, 0, sizeof(*outcome));
    outcome->position = NAV_KF_UPDATE_REJECTED_INVALID;
    outcome->velocity = NAV_KF_UPDATE_REJECTED_INVALID;
    outcome->barometer = NAV_KF_UPDATE_REJECTED_INVALID;
}

static NavigationReplayResult NavigationReplay_EventApply(NavigationKfContext *state,
                                        const NavigationReplayEvent *event,
                                        NavigationReplayOutcome *outcome)
{
    uint8_t group;
    NavigationReplay_OutcomeReset(outcome);
    NavigationReplay_EvidenceApply(state, event);
    if (((event->kind & NAV_REPLAY_POSITION) != 0U) &&
        ((event->valid_group_mask & 3U) != 0U))
    {
        outcome->position = NavigationKf_UpdateGnssPositionSeparated(state,
            event->position, event->position_variance, &outcome->position_groups);
        (void)memcpy(outcome->position_innovation, state->last_position_innovation,
                      sizeof(outcome->position_innovation));
    }
    if (((event->kind & NAV_REPLAY_VELOCITY) != 0U) &&
        ((event->valid_group_mask & 4U) != 0U))
    {
        outcome->velocity = NavigationKf_UpdateGnssVelocitySeparated(state,
            event->velocity, event->velocity_variance, event->vertical_valid,
            &outcome->velocity_groups);
        (void)memcpy(outcome->velocity_innovation, state->last_velocity_innovation,
                      sizeof(outcome->velocity_innovation));
    }
    /* Keep the legacy same-epoch ordering: both updates, then all results. */
    for (group = 0U; group < NAV_KF_GNSS_GROUP_COUNT; group++)
    {
        const NavigationKfGnssSeparatedUpdateResult *result = (group < 2U) ?
            &outcome->position_groups : &outcome->velocity_groups;
        uint8_t vertical = (uint8_t)(group & 1U);
        if ((vertical != 0U) ? result->vertical_attempted : result->horizontal_attempted)
        {
            NavigationKf_GnssGroupResultProcess(state, (NavigationKfGnssGroup)group,
                (vertical != 0U) ? result->vertical_result : result->horizontal_result);
        }
        outcome->group_nis[group] = state->last_gnss_group_nis[group];
    }
    if ((event->kind & NAV_REPLAY_BAROMETER) != 0U)
    {
        outcome->baro_innovation = event->altitude - state->state[2];
        outcome->barometer = NavigationKf_UpdateBaroAltitude(state,
            event->altitude, event->altitude_variance);
        outcome->baro_nis = state->last_baro_nis;
    }
    return ((outcome->position == NAV_KF_UPDATE_NUMERIC_ERROR) ||
            (outcome->velocity == NAV_KF_UPDATE_NUMERIC_ERROR) ||
            (outcome->barometer == NAV_KF_UPDATE_NUMERIC_ERROR)) ?
        NAV_REPLAY_NUMERIC_ERROR : NAV_REPLAY_OK;
}

static uint8_t NavigationReplay_EventBefore(const NavigationReplayEvent *a,
                                           const NavigationReplayEvent *b)
{
    uint8_t a_rank = ((a->kind & NAV_REPLAY_POSITION) != 0U) ? 0U :
                     (((a->kind & NAV_REPLAY_VELOCITY) != 0U) ? 1U : 2U);
    uint8_t b_rank = ((b->kind & NAV_REPLAY_POSITION) != 0U) ? 0U :
                     (((b->kind & NAV_REPLAY_VELOCITY) != 0U) ? 1U : 2U);
    if (a->measurement_timestamp_us != b->measurement_timestamp_us)
    { return (uint8_t)(a->measurement_timestamp_us < b->measurement_timestamp_us); }
    if (a_rank != b_rank) { return (uint8_t)(a_rank < b_rank); }
    if (a->source != b->source) { return (uint8_t)(a->source < b->source); }
    return (uint8_t)(a->sequence < b->sequence);
}

static NavigationReplayResult NavigationReplay_SegmentPredict(
    NavigationReplayContext *history, const NavigationReplayImu *imu,
    uint64_t start_us, uint64_t end_us)
{
    float fraction;
    float delta[3];
    uint8_t axis;
    if (end_us == start_us) { return NAV_REPLAY_OK; }
    if (++history->diagnostics.last_steps > NAV_REPLAY_MAX_STEPS)
    { return NAV_REPLAY_WORK_LIMIT; }
    fraction = (float)(end_us - start_us) / (float)(imu->end_us - imu->start_us);
    for (axis = 0U; axis < 3U; axis++)
    { delta[axis] = imu->delta_velocity[axis] * fraction; }
    return (NavigationKf_Predict(&history->working, delta, imu->dt_s * fraction) != 0U) ?
        NAV_REPLAY_OK : NAV_REPLAY_NUMERIC_ERROR;
}

static NavigationReplayResult NavigationReplay_Rebuild(
    NavigationReplayContext *history, uint8_t checkpoint, uint16_t inserted,
    NavigationReplayOutcome *outcome)
{
    uint16_t event_index = 0U;
    uint16_t imu_index;
    uint8_t next_checkpoint = (uint8_t)(checkpoint + 1U);
    uint64_t cursor = history->storage->checkpoints[checkpoint].timestamp_us;
    NavigationReplayOutcome ignored;
    history->working = history->storage->checkpoints[checkpoint].state;
    while ((event_index < history->event_count) &&
           (NavigationReplay_EventTimeGet(history, event_index) < cursor))
    { event_index++; }
    for (imu_index = 0U; imu_index <= history->imu_count; imu_index++)
    {
        const NavigationReplayImu *imu = (imu_index < history->imu_count) ?
            &history->storage->imu[(history->imu_head + imu_index) % NAV_REPLAY_IMU_CAPACITY] : NULL;
        uint64_t end = (imu != NULL) ? imu->end_us : history->present_us;
        if ((imu != NULL) && (end <= cursor)) { continue; }
        while ((event_index < history->event_count) &&
               (NavigationReplay_EventTimeGet(history, event_index) < end ||
                ((imu == NULL) && (NavigationReplay_EventTimeGet(history, event_index) == end))))
        {
            const NavigationReplayEvent *event = NavigationReplay_EventGet(history, event_index);
            NavigationReplayResult result;
            if (event->measurement_timestamp_us > cursor)
            {
                if (imu == NULL) { return NAV_REPLAY_DISCONTINUITY; }
                result = NavigationReplay_SegmentPredict(history, imu, cursor,
                    event->measurement_timestamp_us);
                if (result != NAV_REPLAY_OK) { return result; }
                cursor = event->measurement_timestamp_us;
            }
            if (++history->diagnostics.last_steps > NAV_REPLAY_MAX_STEPS)
            { return NAV_REPLAY_WORK_LIMIT; }
            result = NavigationReplay_EventApply(&history->working, event,
                (event_index == inserted) ? outcome : &ignored);
            if (result != NAV_REPLAY_OK) { return result; }
            event_index++;
        }
        if ((imu != NULL) && (end > cursor))
        {
            NavigationReplayResult result = NavigationReplay_SegmentPredict(history, imu, cursor, end);
            if (result != NAV_REPLAY_OK) { return result; }
            cursor = end;
            if ((next_checkpoint < history->checkpoint_count) &&
                (history->storage->checkpoints[next_checkpoint].timestamp_us == cursor))
            {
                history->storage->checkpoints[next_checkpoint].state = history->working;
                next_checkpoint++;
            }
        }
    }
    return NAV_REPLAY_OK;
}

NavigationReplayResult NavigationReplay_Insert(
    NavigationReplayContext *history, NavigationKfContext *state,
    const NavigationReplayEvent *event, NavigationReplayOutcome *outcome)
{
    uint16_t index = 0U;
    uint16_t slot;
    uint8_t checkpoint = 0U;
    uint64_t age;
    NavigationReplayResult result = NAV_REPLAY_OK;
    if (outcome != NULL) { NavigationReplay_OutcomeReset(outcome); }
    if ((history == NULL) || (state == NULL) || (event == NULL) || (outcome == NULL) ||
        (history->faulted != 0U) || (history->checkpoint_count == 0U) ||
        (NavigationReplay_EventValid(event) == 0U) ||
        (event->measurement_timestamp_us > history->present_us))
    { return NavigationReplay_Reject(history, NAV_REPLAY_INVALID); }
    history->diagnostics.last_steps = 0U;
    if ((event->epoch != history->epoch) || (NavigationReplay_ModelMatches(history, state) == 0U))
    { return NavigationReplay_Reject(history, NAV_REPLAY_EPOCH_MISMATCH); }
    age = history->present_us - event->measurement_timestamp_us;
    if ((age > NAV_REPLAY_WINDOW_US) ||
        (event->measurement_timestamp_us < history->epoch_start_us) ||
        (event->receive_timestamp_us < history->epoch_start_us) ||
        (event->measurement_timestamp_us < history->storage->checkpoints[0].timestamp_us))
    { return NavigationReplay_Reject(history, NAV_REPLAY_HISTORY_MISS); }
    if (history->event_count >= NAV_REPLAY_EVENT_CAPACITY)
    { return NavigationReplay_Reject(history, NAV_REPLAY_OVERFLOW); }
    while ((index < history->event_count) && NavigationReplay_EventBefore(NavigationReplay_EventGet(history, index), event))
    { index++; }
    if ((index < history->event_count) && !NavigationReplay_EventBefore(event, NavigationReplay_EventGet(history, index)))
    { return NavigationReplay_Reject(history, NAV_REPLAY_INVALID); }
    slot = NavigationReplay_EventStore(history, event);
    if (slot == UINT16_MAX)
    { return NavigationReplay_Reject(history, NAV_REPLAY_OVERFLOW); }
    (void)memmove(&history->event_order[index + 1U], &history->event_order[index],
                  (history->event_count - index) * sizeof(history->event_order[0]));
    history->event_order[index] = slot;
    history->event_count++;
    if (history->event_count > history->diagnostics.event_high_water)
    { history->diagnostics.event_high_water = history->event_count; }
    if ((age == 0U) && (index == history->event_count - 1U))
    {
        /* Original current-state fast path; still retain the event for future rewind. */
        history->working = *state;
        result = NavigationReplay_EventApply(&history->working, event, outcome);
        if (result != NAV_REPLAY_OK)
        {
            history->faulted = 1U;
            NavigationReplay_OutcomeReset(outcome);
            if (result == NAV_REPLAY_NUMERIC_ERROR)
            {
                outcome->position = NAV_KF_UPDATE_NUMERIC_ERROR;
                outcome->velocity = NAV_KF_UPDATE_NUMERIC_ERROR;
                outcome->barometer = NAV_KF_UPDATE_NUMERIC_ERROR;
            }
            return NavigationReplay_Reject(history, result);
        }
        *state = history->working;
    }
    else
    {
        while ((checkpoint + 1U < history->checkpoint_count) &&
               (history->storage->checkpoints[checkpoint + 1U].timestamp_us <= event->measurement_timestamp_us))
        { checkpoint++; }
        history->diagnostics.replay_count++;
        if (age > history->diagnostics.max_rewind_age_us)
        { history->diagnostics.max_rewind_age_us = (uint32_t)age; }
        result = NavigationReplay_Rebuild(history, checkpoint, index, outcome);
        if (result == NAV_REPLAY_OK) { *state = history->working; }
        else
        {
            /* Current x/P remains intact. History may have partial checkpoints;
             * fail closed until a new mission epoch, never current-update fallback. */
            history->faulted = 1U;
            NavigationReplay_OutcomeReset(outcome);
            if (result == NAV_REPLAY_NUMERIC_ERROR)
            {
                outcome->position = NAV_KF_UPDATE_NUMERIC_ERROR;
                outcome->velocity = NAV_KF_UPDATE_NUMERIC_ERROR;
                outcome->barometer = NAV_KF_UPDATE_NUMERIC_ERROR;
            }
            return NavigationReplay_Reject(history, result);
        }
    }
    if (history->diagnostics.last_steps > history->diagnostics.max_steps)
    { history->diagnostics.max_steps = history->diagnostics.last_steps; }
    history->diagnostics.last_result = result;
    return result;
}

void NavigationReplay_RuntimeRecord(NavigationReplayContext *history,
                                    uint64_t elapsed_us)
{
    if (history == NULL) { return; }
    history->diagnostics.last_runtime_us = (elapsed_us > UINT32_MAX) ? UINT32_MAX : (uint32_t)elapsed_us;
    if (history->diagnostics.last_runtime_us > history->diagnostics.max_runtime_us)
    { history->diagnostics.max_runtime_us = history->diagnostics.last_runtime_us; }
}
