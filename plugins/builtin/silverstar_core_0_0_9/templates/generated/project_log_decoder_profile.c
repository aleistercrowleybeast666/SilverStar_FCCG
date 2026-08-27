#include "project_log_decoder_profile.h"

#include <string.h>

#include "silverstar_assert.h"

static const uint8_t s_record_catalog_hash[PROJECT_LOG_DECODER_HASH_SIZE] =
{
    0x96U, 0x2FU, 0x92U, 0x36U, 0x52U, 0x9DU, 0x2FU, 0xF4U,
    0x37U, 0x52U, 0x02U, 0xCCU, 0x20U, 0x85U, 0xEDU, 0x5DU
};
static const uint8_t s_project_semantics_hash[PROJECT_LOG_DECODER_HASH_SIZE] =
{
    0x78U, 0xE2U, 0xA3U, 0xA6U, 0xEEU, 0x9AU, 0xB3U, 0x39U,
    0xC8U, 0x09U, 0x0EU, 0x5BU, 0xF2U, 0xDCU, 0x27U, 0x0BU
};
static const uint8_t s_generation_profile_hash[PROJECT_LOG_DECODER_HASH_SIZE] =
{
    0x3EU, 0x53U, 0xC8U, 0x44U, 0x9EU, 0xBEU, 0xEAU, 0xD0U,
    0x10U, 0x2DU, 0x9BU, 0x11U, 0x06U, 0xE3U, 0xE7U, 0x5AU
};

void ProjectLogDecoderProfile_Get(ProjectLogDecoderProfile *profile)
{
    SILVERSTAR_ASSERT_OBJECT(profile, ProjectLogDecoderProfile,
        SILVERSTAR_ASSERT_MODULE_GENERATED);
    (void)memset(profile, 0, sizeof(*profile));
    profile->package_schema_major = 1U;
    profile->package_schema_minor = 0U;
    profile->container_format_major = 0U;
    profile->container_format_minor = 0U;
    (void)memcpy(profile->record_catalog_hash_128,
        s_record_catalog_hash, sizeof(profile->record_catalog_hash_128));
    (void)memcpy(profile->project_semantics_hash_128,
        s_project_semantics_hash, sizeof(profile->project_semantics_hash_128));
    (void)memcpy(profile->generation_profile_hash_128,
        s_generation_profile_hash, sizeof(profile->generation_profile_hash_128));
}
