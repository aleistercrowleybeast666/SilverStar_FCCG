/* App orchestration fixture: production work type/helpers are inserted above. */
static uint64_t TestApp_Hash(uint64_t hash, const void *data, size_t size)
{
    const unsigned char *bytes = data;
    size_t i;
    for (i = 0U; i < size; i++) { hash = (hash ^ bytes[i]) * UINT64_C(1099511628211); }
    return hash;
}

int main(void)
{
    unsigned int step, axis;
    uint64_t hash = UINT64_C(14695981039346656037);
    static NavigationReplayStorage storage;
    NavigationKf_Init(&s_estimator.kf);
    NavigationKf_Reset(&s_estimator.kf);
    NavigationReplay_Reset(&s_replay, &storage, &s_estimator.kf, 1000000ULL, 7U);
    for (step = 1U; step <= 450U; step++)
    {
        const float delta[3] = {0.0001f, 0.0002f, 0.0003f};
        uint64_t timestamp = 1000000ULL + (uint64_t)step * 5000ULL;
        if (NavigationReplay_Predict(&s_replay, &s_estimator.kf, timestamp, delta, 0.005f) != NAV_REPLAY_OK)
        { return 2; }
        if ((step % 8U == 0U) && ((step < 120U) || (step > 208U)))
        {
            EstimatorGnssUpdateWork work;
            (void)memset(&work, 0, sizeof(work));
            work.sample.receive_timestamp_us = timestamp;
            work.sample.sample_timestamp_us = timestamp;
            work.sample.sequence = step;
            work.epoch.valid_group_mask = 15U;
            work.velocity_dimension = 3U;
            for (axis = 0U; axis < 3U; axis++)
            {
                work.position_enu_m[axis] = 0.2f * sinf((float)step * 0.03f);
                work.sample.velocity_enu_mps[axis] = 0.05f * cosf((float)step * 0.03f);
                work.position_variance[axis] = 2.25f;
                work.velocity_variance[axis] = 0.04f;
                work.epoch.position_enu_m[axis] = work.position_enu_m[axis];
                work.epoch.velocity_enu_mps[axis] = work.sample.velocity_enu_mps[axis];
                work.epoch.position_std_m[axis] = 1.5f;
                work.epoch.velocity_std_mps[axis] = 0.2f;
            }
            Estimator_GnssReplay(timestamp, &work);
            hash = TestApp_Hash(hash, &work.replay_outcome, sizeof(work.replay_outcome));
            hash = TestApp_Hash(hash, &s_snapshot, sizeof(s_snapshot));
        }
        hash = TestApp_Hash(hash, &s_estimator.kf, sizeof(s_estimator.kf));
        hash = TestApp_Hash(hash, (const unsigned char *)&s_replay + offsetof(NavigationReplayContext, events),
                            sizeof(s_replay) - offsetof(NavigationReplayContext, events));
        hash = TestApp_Hash(hash, &storage, sizeof(storage));
        (void)printf("%016llx\n", (unsigned long long)hash);
    }
    return 0;
}
