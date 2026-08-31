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
    0xE2U, 0x38U, 0xEBU, 0x54U, 0xA3U, 0x88U, 0x45U, 0xC5U,
    0x74U, 0x66U, 0x9CU, 0x9DU, 0x9CU, 0x76U, 0x84U, 0x23U
};
static const uint8_t s_generation_profile_hash[PROJECT_LOG_DECODER_HASH_SIZE] =
{
    0x59U, 0x0FU, 0xD5U, 0x5DU, 0xBBU, 0x9AU, 0x44U, 0x11U,
    0xDAU, 0xF4U, 0x96U, 0x2EU, 0x5EU, 0xADU, 0x05U, 0xB1U
};

void ProjectLogDecoderProfile_Get(ProjectLogDecoderProfile *profile)
{
    SILVERSTAR_ASSERT_OBJECT(profile, ProjectLogDecoderProfile,
        SILVERSTAR_ASSERT_MODULE_GENERATED);
    (void)memset(profile, 0, sizeof(*profile));
    profile->package_schema_major = 1U;
    profile->package_schema_minor = 1U;
    profile->container_format_major = 0U;
    profile->container_format_minor = 0U;
    (void)memcpy(profile->record_catalog_hash_128,
        s_record_catalog_hash, sizeof(profile->record_catalog_hash_128));
    (void)memcpy(profile->project_semantics_hash_128,
        s_project_semantics_hash, sizeof(profile->project_semantics_hash_128));
    (void)memcpy(profile->generation_profile_hash_128,
        s_generation_profile_hash, sizeof(profile->generation_profile_hash_128));
}
