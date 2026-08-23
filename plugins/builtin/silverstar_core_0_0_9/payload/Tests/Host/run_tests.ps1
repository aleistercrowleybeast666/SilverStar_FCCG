$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$outputDir = Join-Path $repoRoot 'build\Host\Tests'
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

$script:hostExecutableCount = 0
$script:hostCheckCount = 0
$script:hostFailureCount = 0
$script:compilePassCaseCount = 0
$script:expectedCompileFailureCount = 0
$silverstarAssertSource = "$repoRoot\Common\Src\silverstar_assert.c"

$includeArgs = @(
    "-I$repoRoot\Tests\Host",
    "-I$repoRoot\APP\Inc",
    "-I$repoRoot\Algorithm\Common\Inc",
    "-I$repoRoot\Algorithm\Calibration\Inc",
    "-I$repoRoot\Algorithm\Alignment\Common\Inc",
    "-I$repoRoot\Algorithm\Alignment\GravityKnownYaw\Inc",
    "-I$repoRoot\Algorithm\Alignment\GravityMagTriad\Inc",
    "-I$repoRoot\Algorithm\INS\Coning2Sculling2\Inc",
    "-I$repoRoot\Algorithm\Estimator\KF6\Inc",
    "-I$repoRoot\Common\Inc",
    "-I$repoRoot\Modules\Inc",
    "-I$repoRoot\Protocol\Inc",
    "-I$repoRoot\Protocol\SSLOG\Inc",
    "-I$repoRoot\Interfaces\Inc",
    "-I$repoRoot\System\Inc",
    "-I$repoRoot\System\Alignment\Inc",
    "-I$repoRoot\System\Calibration\Inc",
    "-I$repoRoot\System\Indicator\Inc",
    "-I$repoRoot\System\Inertial\Inc",
    "-I$repoRoot\System\User",
    "-I$repoRoot\Targets\SilverStar_F407\Inc",
    "-I$repoRoot\Board\SilverStar_0_5\Services\Inc",
    "-I$repoRoot\Generated\Inc",
    "-I$repoRoot\FlightLogic\Deployment\MultiTrigger\Inc",
    "-I$repoRoot\FlightLogic\Landing\BarometerImuWindow\Inc",
    "-I$repoRoot\Platform\Inc",
    "-I$repoRoot\Devices\IMU\JY901B\Inc",
    "-I$repoRoot\Devices\IMU\JY901B\Adapter\Inc",
    "-I$repoRoot\Devices\GNSS\NEO_M9N\Inc",
    "-I$repoRoot\Devices\Telemetry\SX1281\Inc",
    "-I$repoRoot\Middlewares\Third_Party\SX1280lib"
)

function Invoke-HostTest {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string[]]$Sources,
        [string[]]$ExtraCompilerArgs = @()
    )

    # A generated FCCG project contains only its selected component payloads.
    $fccgMissingSources = @($Sources | Where-Object {
        -not (Test-Path -LiteralPath $_)
    })
    if ($fccgMissingSources.Count -ne 0) {
        Write-Output ("Skipped host test {0}: unselected component sources {1}" -f $Name, ($fccgMissingSources -join ', '))
        return
    }

    $executable = Join-Path $outputDir ($Name + '.exe')
    $compilerArgs = @(
        '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic', '-O2'
    ) + $ExtraCompilerArgs + $includeArgs + $Sources + @(
        $silverstarAssertSource, '-lm', '-o', $executable)

    & gcc @compilerArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Host test compile failed: $Name"
    }
    $testOutput = @(& $executable)
    $testExit = $LASTEXITCODE
    $testOutput | Write-Output
    foreach ($line in $testOutput) {
        if ($line -match ':\s+(\d+) checks,\s+(\d+) failures$') {
            $script:hostCheckCount += [int]$Matches[1]
            $script:hostFailureCount += [int]$Matches[2]
        }
    }
    if ($testExit -ne 0) {
        throw "Host test failed: $Name"
    }
    $script:hostExecutableCount++
}

function Invoke-ExpectedCompileFailure {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Source,
        [string[]]$ExtraCompilerArgs = @()
    )

    $compilerArgs = @(
        '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic', '-fsyntax-only'
    ) + $ExtraCompilerArgs + $includeArgs + @($Source)
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    & gcc @compilerArgs 2>$null
    $compileExit = $LASTEXITCODE
    $ErrorActionPreference = $previousPreference
    if ($compileExit -eq 0) {
        throw "Expected host compile failure did not occur: $Name"
    }
    $script:expectedCompileFailureCount++
    Write-Output "Expected host compile failure passed: $Name"
}

function Invoke-ExpectedCompileSuccess {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Source,
        [string[]]$ExtraCompilerArgs = @()
    )

    $compilerArgs = @(
        '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic', '-fsyntax-only'
    ) + $ExtraCompilerArgs + $includeArgs + @($Source)
    & gcc @compilerArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Expected host compile success failed: $Name"
    }
    $script:compilePassCaseCount++
    Write-Output "Expected host compile success passed: $Name"
}

$hostPlatformMock = "$repoRoot\Tests\Host\host_platform_mock.c"
$sslogSources = @(
    "$repoRoot\Protocol\SSLOG\Src\sslog_protocol.c",
    "$repoRoot\Protocol\SSLOG\Src\sslog_records.c"
)

Invoke-HostTest -Name 'interfaces' -Sources @(
    "$repoRoot\Tests\Host\test_interfaces.c"
)

Invoke-HostTest -Name 'common_format' -Sources @(
    "$repoRoot\Tests\Host\test_common_format.c",
    "$repoRoot\Common\Src\common_format.c"
)

Invoke-HostTest -Name 'system_time' -Sources @(
    "$repoRoot\Tests\Host\test_system_time.c",
    "$repoRoot\System\Src\system_time.c"
)

$profileSources = @(
    "$repoRoot\Tests\Host\test_profiles.c",
    $hostPlatformMock,
    "$repoRoot\System\Src\system_navigation_profile.c",
    "$repoRoot\System\Src\system_estimator_profile.c",
    "$repoRoot\System\Src\system_log_policy.c",
    "$repoRoot\System\Src\system_profile.c",
    "$repoRoot\Protocol\SSLOG\Src\sslog_records.c",
    "$repoRoot\Generated\Src\project_log_config.c"
)
Invoke-HostTest -Name 'profiles_kf6' -Sources $profileSources

$estimatorNoiseOverrideArgs = @(
    '-DTEST_EXPECT_ESTIMATOR_NOISE_OVERRIDES=1',
    '-DSYSTEM_ESTIMATOR_PROCESS_ACCEL_E_STD_MPS2_OVERRIDE=0.8f',
    '-DSYSTEM_ESTIMATOR_PROCESS_ACCEL_N_STD_MPS2_OVERRIDE=0.9f',
    '-DSYSTEM_ESTIMATOR_PROCESS_ACCEL_U_STD_MPS2_OVERRIDE=1.1f',
    '-DSYSTEM_ESTIMATOR_GNSS_HORIZONTAL_STD_FLOOR_M_OVERRIDE=0.7f',
    '-DSYSTEM_ESTIMATOR_GNSS_VERTICAL_STD_FLOOR_M_OVERRIDE=1.2f',
    '-DSYSTEM_ESTIMATOR_GNSS_VELOCITY_STD_FLOOR_MPS_OVERRIDE=0.08f',
    '-DSYSTEM_ESTIMATOR_BAROMETER_ALTITUDE_STD_M_OVERRIDE=3.5f'
)
Invoke-HostTest -Name 'profiles_estimator_noise_overrides' `
    -ExtraCompilerArgs $estimatorNoiseOverrideArgs -Sources $profileSources

$pureInsConfigDir = Join-Path $outputDir 'config_pure_ins'
New-Item -ItemType Directory -Force -Path $pureInsConfigDir | Out-Null
$pureInsConfigPath = Join-Path $pureInsConfigDir 'system_user_config.h'
$configText = Get-Content -Raw -LiteralPath `
    (Join-Path $repoRoot 'System\User\system_user_config.h')
$configText = $configText.Replace(
    '#define SYSTEM_BUILD_FUSION_ALGORITHM SYSTEM_FUSION_KF6',
    '#define SYSTEM_BUILD_FUSION_ALGORITHM SYSTEM_FUSION_NONE')
Set-Content -LiteralPath $pureInsConfigPath -Value $configText -NoNewline
Invoke-HostTest -Name 'profiles_pure_ins' -ExtraCompilerArgs @(
    "-I$pureInsConfigDir"
) -Sources $profileSources

Invoke-HostTest -Name 'attitude_alignment' -Sources @(
    "$repoRoot\Tests\Host\test_attitude_alignment.c",
    "$repoRoot\Algorithm\Alignment\Common\Src\attitude_alignment.c",
    "$repoRoot\Algorithm\Alignment\Common\Src\attitude_preflight.c",
    "$repoRoot\Algorithm\Alignment\GravityKnownYaw\Src\alignment_gravity_known_yaw.c",
    "$repoRoot\Algorithm\Alignment\GravityMagTriad\Src\attitude_triad.c",
    "$repoRoot\Algorithm\Common\Src\attitude_frame.c"
)

$alignmentStrategyCommonSources = @(
    "$repoRoot\Tests\Host\test_alignment_strategy.c",
    "$repoRoot\Algorithm\Alignment\Common\Src\attitude_alignment.c",
    "$repoRoot\Algorithm\Common\Src\attitude_frame.c"
)
Invoke-HostTest -Name 'alignment_strategy_gravity_known_yaw' `
    -ExtraCompilerArgs @(
        '-DTEST_ALIGNMENT_GRAVITY_KNOWN_YAW=1',
        "-I$repoRoot\Algorithm\Alignment\GravityKnownYaw\Inc"
    ) -Sources ($alignmentStrategyCommonSources + @(
        "$repoRoot\Algorithm\Alignment\GravityKnownYaw\Src\alignment_gravity_known_yaw.c",
        "$repoRoot\Algorithm\Alignment\GravityKnownYaw\Src\alignment_strategy_binding.c"
    ))
Invoke-HostTest -Name 'alignment_strategy_gravity_mag_triad' `
    -ExtraCompilerArgs @(
        '-DTEST_ALIGNMENT_GRAVITY_MAG=1',
        "-I$repoRoot\Algorithm\Alignment\GravityMagTriad\Inc"
    ) -Sources ($alignmentStrategyCommonSources + @(
        "$repoRoot\Algorithm\Alignment\GravityMagTriad\Src\attitude_triad.c",
        "$repoRoot\Algorithm\Alignment\GravityMagTriad\Src\alignment_strategy_binding.c"
    ))
Invoke-HostTest -Name 'alignment_strategy_hardware_quat6_known_yaw' `
    -ExtraCompilerArgs @(
        '-DTEST_ALIGNMENT_HW_QUAT=1',
        "-I$repoRoot\Algorithm\Alignment\HardwareQuat6AxisKnownYaw\Inc"
    ) -Sources ($alignmentStrategyCommonSources + @(
        "$repoRoot\Algorithm\Alignment\HardwareQuat6AxisKnownYaw\Src\alignment_strategy_binding.c"
    ))
Invoke-HostTest -Name 'alignment_strategy_hardware_quat9' `
    -ExtraCompilerArgs @(
        '-DTEST_ALIGNMENT_HW_QUAT=1',
        "-I$repoRoot\Algorithm\Alignment\HardwareQuat9Axis\Inc"
    ) -Sources ($alignmentStrategyCommonSources + @(
        "$repoRoot\Algorithm\Alignment\HardwareQuat9Axis\Src\alignment_strategy_binding.c"
    ))

Invoke-HostTest -Name 'system_alignment' -Sources @(
    "$repoRoot\Tests\Host\test_system_alignment.c",
    $hostPlatformMock,
    "$repoRoot\Common\Src\common_format.c",
    "$repoRoot\System\Alignment\Src\system_alignment.c",
    "$repoRoot\System\Alignment\Src\system_alignment_source.c",
    "$repoRoot\System\Calibration\Src\system_calibration.c",
    "$repoRoot\Algorithm\Calibration\Src\imu_six_face_calibration.c"
)

Invoke-HostTest -Name 'system_inertial' -Sources @(
    "$repoRoot\Tests\Host\test_system_inertial.c",
    $hostPlatformMock,
    "$repoRoot\System\Inertial\Src\system_inertial.c",
    "$repoRoot\System\User\system_user_inertial_config.c"
)

Invoke-HostTest -Name 'system_indicator' -Sources @(
    "$repoRoot\Tests\Host\test_system_indicator.c",
    "$repoRoot\System\Indicator\Src\system_indicator.c"
)

$calibrationSources = @(
    "$repoRoot\Tests\Host\test_system_calibration.c",
    $hostPlatformMock,
    "$repoRoot\System\Calibration\Src\system_calibration.c",
    "$repoRoot\System\Calibration\Src\system_calibration_correction.c",
    "$repoRoot\Algorithm\Calibration\Src\imu_six_face_calibration.c"
)
Invoke-HostTest -Name 'system_calibration_default' -ExtraCompilerArgs @(
    '-DTEST_EXPECT_DEFAULT_Y_POSITIVE=1'
) -Sources $calibrationSources
foreach ($direction in @(
    'SYSTEM_AXIS_DIRECTION_X_POSITIVE',
    'SYSTEM_AXIS_DIRECTION_X_NEGATIVE',
    'SYSTEM_AXIS_DIRECTION_Y_POSITIVE',
    'SYSTEM_AXIS_DIRECTION_Y_NEGATIVE',
    'SYSTEM_AXIS_DIRECTION_Z_POSITIVE',
    'SYSTEM_AXIS_DIRECTION_Z_NEGATIVE')) {
    Invoke-HostTest -Name ("system_calibration_" + $direction.ToLower()) `
        -ExtraCompilerArgs @("-DSYSTEM_IMU_STARTUP_GRAVITY_DIRECTION=$direction") `
        -Sources $calibrationSources
}

$capabilitySource = "$repoRoot\Tests\Host\test_build_capability_contract.c"
Invoke-ExpectedCompileSuccess -Name 'capability_default_jy901b' `
    -ExtraCompilerArgs @('-DTEST_EXPECT_DEFAULT_JY901B_PROFILE=1') `
    -Source $capabilitySource
Invoke-ExpectedCompileFailure -Name 'capability_missing_imu_noise' `
    -ExtraCompilerArgs @(
        '-DSYSTEM_SELECTED_IMU_ESTIMATOR_NOISE_RECOMMENDATION_AVAILABLE=0U'
    ) -Source $capabilitySource
Invoke-ExpectedCompileFailure -Name 'capability_missing_gnss_noise' `
    -ExtraCompilerArgs @(
        '-DSYSTEM_SELECTED_GNSS_ESTIMATOR_NOISE_RECOMMENDATION_AVAILABLE=0U'
    ) -Source $capabilitySource
Invoke-ExpectedCompileFailure -Name 'capability_missing_baro_noise' `
    -ExtraCompilerArgs @(
        '-DSYSTEM_SELECTED_BAROMETER_ESTIMATOR_NOISE_RECOMMENDATION_AVAILABLE=0U'
    ) -Source $capabilitySource
Invoke-ExpectedCompileSuccess -Name 'capability_noise_overrides' `
    -ExtraCompilerArgs ($estimatorNoiseOverrideArgs + @(
        '-DSYSTEM_SELECTED_IMU_ESTIMATOR_NOISE_RECOMMENDATION_AVAILABLE=0U',
        '-DSYSTEM_SELECTED_GNSS_ESTIMATOR_NOISE_RECOMMENDATION_AVAILABLE=0U',
        '-DSYSTEM_SELECTED_BAROMETER_ESTIMATOR_NOISE_RECOMMENDATION_AVAILABLE=0U'
    )) -Source $capabilitySource
Invoke-ExpectedCompileSuccess -Name 'capability_future_triad' `
    -ExtraCompilerArgs @(
        '-DSYSTEM_ALIGNMENT_BUILD_ALGORITHM=SYSTEM_ALIGNMENT_GRAVITY_MAG_TRIAD',
        '-DSYSTEM_USER_MAGNETOMETER_ENABLE=1U',
        '-DJY901B_MAGNETOMETER_ADAPTER_ENABLE=1U',
        '-DSYSTEM_SELECTED_MAGNETOMETER_PHYSICAL_UNIT_AVAILABLE=1U',
        '-DSYSTEM_SELECTED_MAGNETOMETER_ABSOLUTE_VECTOR_QUALIFIED=1U'
    ) -Source $capabilitySource
Invoke-ExpectedCompileFailure -Name 'capability_hw_quat_6axis_unqualified' `
    -ExtraCompilerArgs @(
        '-DSYSTEM_ALIGNMENT_BUILD_ALGORITHM=SYSTEM_ALIGNMENT_HW_QUAT_6AXIS_KNOWN_YAW'
    ) -Source $capabilitySource
Invoke-ExpectedCompileFailure -Name 'capability_hw_quat_9axis_unqualified' `
    -ExtraCompilerArgs @(
        '-DSYSTEM_ALIGNMENT_BUILD_ALGORITHM=SYSTEM_ALIGNMENT_HW_QUAT_9AXIS'
    ) -Source $capabilitySource
Invoke-ExpectedCompileFailure -Name 'capability_impact_unqualified' `
    -ExtraCompilerArgs @(
        '-DSYSTEM_BUILD_LANDING_MODE=SYSTEM_LANDING_MODE_IMPACT_THEN_STILLNESS'
    ) -Source $capabilitySource
Invoke-ExpectedCompileSuccess -Name 'capability_future_impact_qualified' `
    -ExtraCompilerArgs @(
        '-DSYSTEM_BUILD_LANDING_MODE=SYSTEM_LANDING_MODE_IMPACT_THEN_STILLNESS',
        '-DSYSTEM_SELECTED_IMU_LANDING_IMPACT_QUALIFIED=1U'
    ) -Source $capabilitySource
Invoke-ExpectedCompileFailure -Name 'capability_deploy_without_action' `
    -ExtraCompilerArgs @('-DSYSTEM_USER_MISSION_ACTION_ENABLE=0U') `
    -Source $capabilitySource
Invoke-ExpectedCompileFailure -Name 'capability_required_baro_missing' `
    -ExtraCompilerArgs @(
        '-DSYSTEM_USER_BAROMETER_ENABLE=0U',
        '-DSYSTEM_USER_ALIGNMENT_REQUIRED_MASK=(SYSTEM_ALIGNMENT_SOURCE_MASK_ATTITUDE|SYSTEM_ALIGNMENT_SOURCE_MASK_BARO_ORIGIN)'
    ) -Source $capabilitySource
Invoke-ExpectedCompileFailure -Name 'capability_required_gnss_missing' `
    -ExtraCompilerArgs @(
        '-DSYSTEM_USER_GNSS_ENABLE=0U',
        '-DSYSTEM_USER_ALIGNMENT_REQUIRED_MASK=(SYSTEM_ALIGNMENT_SOURCE_MASK_ATTITUDE|SYSTEM_ALIGNMENT_SOURCE_MASK_GNSS_ORIGIN)'
    ) -Source $capabilitySource
Invoke-ExpectedCompileFailure -Name 'capability_stillness_without_gyro' `
    -ExtraCompilerArgs @(
        '-DSYSTEM_BUILD_LANDING_MODE=SYSTEM_LANDING_MODE_STILLNESS',
        '-DSYSTEM_SELECTED_IMU_GYRO_AVAILABLE=0U'
    ) -Source $capabilitySource
Invoke-ExpectedCompileFailure -Name 'capability_tilt_without_propagation' `
    -ExtraCompilerArgs @(
        '-DSYSTEM_FLIGHT_DEPLOY_TRIGGER_MASK=SYSTEM_DEPLOY_TRIGGER_TILT',
        '-DSYSTEM_SELECTED_IMU_SOFTWARE_PROPAGATION_QUALIFIED=0U'
    ) -Source $capabilitySource
Invoke-ExpectedCompileFailure -Name 'capability_delay_without_time' `
    -ExtraCompilerArgs @(
        '-DSYSTEM_FLIGHT_DEPLOY_TRIGGER_MASK=SYSTEM_DEPLOY_TRIGGER_DELAY',
        '-DSYSTEM_BUILD_MISSION_MONOTONIC_TIME_AVAILABLE=0U'
    ) -Source $capabilitySource

Invoke-HostTest -Name 'air_kf' -Sources @(
    "$repoRoot\Tests\Host\test_air_kf.c",
    "$repoRoot\Protocol\Src\air_protocol.c",
    "$repoRoot\Algorithm\Estimator\KF6\Src\navigation_kf.c",
    "$repoRoot\Algorithm\Common\Src\attitude_frame.c",
    "$repoRoot\System\Src\system_estimator_profile.c"
)

Invoke-HostTest -Name 'jy901b_device' -Sources @(
    "$repoRoot\Tests\Host\test_jy901b_device.c",
    $hostPlatformMock,
    "$repoRoot\Devices\IMU\JY901B\Src\jy901b_device.c"
)
Invoke-HostTest -Name 'jy901b_adapter' -ExtraCompilerArgs @(
    '-DJY901B_BAUD_RESCUE_ENABLE=0U'
) -Sources @(
    "$repoRoot\Tests\Host\test_jy901b_adapter.c",
    $hostPlatformMock,
    "$repoRoot\Devices\IMU\JY901B\Src\jy901b_device.c",
    "$repoRoot\Devices\IMU\JY901B\Adapter\Src\jy901b_imu_adapter.c"
)
Invoke-HostTest -Name 'neo_m9n_device' -Sources @(
    "$repoRoot\Tests\Host\test_neo_m9n_device.c",
    "$repoRoot\Devices\GNSS\NEO_M9N\Src\neo_m9n_device.c"
)
Invoke-HostTest -Name 'neo_m9n_adapter' -Sources @(
    "$repoRoot\Tests\Host\test_neo_m9n_adapter.c",
    $hostPlatformMock,
    "$repoRoot\Devices\GNSS\NEO_M9N\Src\neo_m9n_device.c",
    "$repoRoot\Devices\GNSS\NEO_M9N\Adapter\Src\neo_m9n_system_adapter.c",
    "$repoRoot\System\Src\system_gnss_quality.c"
)
Invoke-HostTest -Name 'sx1281_device' -Sources @(
    "$repoRoot\Tests\Host\test_sx1281_device.c",
    "$repoRoot\Devices\Telemetry\SX1281\Src\sx1281_device.c"
)
Invoke-HostTest -Name 'board_power_service' -Sources @(
    "$repoRoot\Tests\Host\test_board_power_service.c",
    $hostPlatformMock,
    "$repoRoot\Board\SilverStar_0_5\Services\Src\power_service.c"
)
Invoke-HostTest -Name 'board_mission_action_service' -Sources @(
    "$repoRoot\Tests\Host\test_board_mission_action_service.c",
    "$repoRoot\Board\SilverStar_0_5\Services\Src\mission_action_service.c"
)

Invoke-HostTest -Name 'sensor_quality' -Sources @(
    "$repoRoot\Tests\Host\test_sensor_quality.c",
    $hostPlatformMock,
    "$repoRoot\System\Src\system_gnss_quality.c",
    "$repoRoot\System\Src\system_barometer.c",
    "$repoRoot\System\Src\system_estimator_diagnostics.c"
)
Invoke-HostTest -Name 'estimator_barometer_pending' -Sources @(
    "$repoRoot\Tests\Host\test_estimator_barometer_pending.c",
    "$repoRoot\APP\Src\estimator_barometer_pending.c"
)
Invoke-HostTest -Name 'sensor_status' -Sources @(
    "$repoRoot\Tests\Host\test_sensor_status.c",
    $hostPlatformMock,
    "$repoRoot\System\Src\system_sensor_status.c"
)
Invoke-HostTest -Name 'lifecycle' -Sources @(
    "$repoRoot\Tests\Host\test_lifecycle.c",
    $hostPlatformMock,
    "$repoRoot\FlightLogic\FlightCycle\Src\silverstar_flight_cycle.c"
)

$recoverySources = @(
    "$repoRoot\Tests\Host\test_flight_recovery.c",
    $hostPlatformMock,
    "$repoRoot\FlightLogic\FlightCycle\Src\silverstar_flight_recovery.c",
    "$repoRoot\FlightLogic\Deployment\MultiTrigger\Src\flight_deployment.c",
    "$repoRoot\FlightLogic\Landing\BarometerImuWindow\Src\flight_landing.c"
)
Invoke-HostTest -Name 'flight_recovery_apogee' -ExtraCompilerArgs @(
    '-DTEST_EXPECT_APOGEE=1', '-DSYSTEM_FLIGHT_DEPLOY_CONFIRM_MS=100U'
) -Sources $recoverySources
Invoke-HostTest -Name 'flight_recovery_apogee_immediate' -ExtraCompilerArgs @(
    '-DTEST_EXPECT_APOGEE=1'
) -Sources $recoverySources
Invoke-HostTest -Name 'flight_recovery_tilt' -ExtraCompilerArgs @(
    '-DTEST_EXPECT_TILT=1',
    '-DSYSTEM_FLIGHT_DEPLOY_TRIGGER_MASK=SYSTEM_DEPLOY_TRIGGER_TILT',
    '-DSYSTEM_FLIGHT_TILT_THRESHOLD_DEG=30.0f',
    '-DSYSTEM_FLIGHT_DEPLOY_CONFIRM_MS=100U'
) -Sources $recoverySources
Invoke-HostTest -Name 'flight_recovery_tilt_immediate' -ExtraCompilerArgs @(
    '-DTEST_EXPECT_TILT=1',
    '-DSYSTEM_FLIGHT_DEPLOY_TRIGGER_MASK=SYSTEM_DEPLOY_TRIGGER_TILT',
    '-DSYSTEM_FLIGHT_TILT_THRESHOLD_DEG=30.0f'
) -Sources $recoverySources
Invoke-HostTest -Name 'flight_recovery_apogee_or_tilt' -ExtraCompilerArgs @(
    '-DTEST_EXPECT_OR=1',
    '-DSYSTEM_FLIGHT_DEPLOY_TRIGGER_MASK=(SYSTEM_DEPLOY_TRIGGER_APOGEE_VZ|SYSTEM_DEPLOY_TRIGGER_TILT)',
    '-DSYSTEM_FLIGHT_TILT_THRESHOLD_DEG=30.0f'
) -Sources $recoverySources
Invoke-HostTest -Name 'flight_recovery_apogee_or_delay' `
    -ExtraCompilerArgs @(
        '-DTEST_EXPECT_PAIR=1',
        '-DTEST_EXPECTED_DEPLOY_MASK=(SYSTEM_DEPLOY_TRIGGER_APOGEE_VZ|SYSTEM_DEPLOY_TRIGGER_DELAY)',
        '-DSYSTEM_FLIGHT_DEPLOY_TRIGGER_MASK=(SYSTEM_DEPLOY_TRIGGER_APOGEE_VZ|SYSTEM_DEPLOY_TRIGGER_DELAY)',
        '-DSYSTEM_FLIGHT_DEPLOY_DELAY_MS=5000U'
    ) -Sources $recoverySources
Invoke-HostTest -Name 'flight_recovery_tilt_or_delay' `
    -ExtraCompilerArgs @(
        '-DTEST_EXPECT_PAIR=1',
        '-DTEST_EXPECTED_DEPLOY_MASK=(SYSTEM_DEPLOY_TRIGGER_TILT|SYSTEM_DEPLOY_TRIGGER_DELAY)',
        '-DSYSTEM_FLIGHT_DEPLOY_TRIGGER_MASK=(SYSTEM_DEPLOY_TRIGGER_TILT|SYSTEM_DEPLOY_TRIGGER_DELAY)',
        '-DSYSTEM_FLIGHT_TILT_THRESHOLD_DEG=30.0f',
        '-DSYSTEM_FLIGHT_DEPLOY_DELAY_MS=5000U'
    ) -Sources $recoverySources
Invoke-HostTest -Name 'flight_recovery_delay' -ExtraCompilerArgs @(
    '-DTEST_EXPECT_DELAY=1',
    '-DSYSTEM_FLIGHT_DEPLOY_TRIGGER_MASK=SYSTEM_DEPLOY_TRIGGER_DELAY',
    '-DSYSTEM_FLIGHT_DEPLOY_DELAY_MS=5000U'
) -Sources $recoverySources
Invoke-HostTest -Name 'flight_recovery_all_triggers' -ExtraCompilerArgs @(
    '-DTEST_EXPECT_ALL=1',
    '-DSYSTEM_FLIGHT_DEPLOY_TRIGGER_MASK=(SYSTEM_DEPLOY_TRIGGER_TILT|SYSTEM_DEPLOY_TRIGGER_APOGEE_VZ|SYSTEM_DEPLOY_TRIGGER_DELAY)',
    '-DSYSTEM_FLIGHT_TILT_THRESHOLD_DEG=30.0f',
    '-DSYSTEM_FLIGHT_DEPLOY_DELAY_MS=5000U'
) -Sources $recoverySources
Invoke-HostTest -Name 'flight_recovery_none_landing' -ExtraCompilerArgs @(
    '-DTEST_EXPECT_NONE=1', '-DTEST_EXPECT_STILLNESS=1',
    '-DSYSTEM_FLIGHT_DEPLOY_TRIGGER_MASK=SYSTEM_DEPLOY_TRIGGER_NONE',
    '-DSYSTEM_BUILD_LANDING_MODE=SYSTEM_LANDING_MODE_STILLNESS',
    '-DSYSTEM_FLIGHT_LANDING_CONFIRM_MS=100U'
) -Sources $recoverySources
Invoke-HostTest -Name 'flight_recovery_impact_landing' -ExtraCompilerArgs @(
    '-DTEST_EXPECT_NONE=1', '-DTEST_EXPECT_IMPACT=1',
    '-DSYSTEM_FLIGHT_DEPLOY_TRIGGER_MASK=SYSTEM_DEPLOY_TRIGGER_NONE',
    '-DSYSTEM_BUILD_LANDING_MODE=SYSTEM_LANDING_MODE_IMPACT_THEN_STILLNESS',
    '-DSYSTEM_FLIGHT_LANDING_IMPACT_INHIBIT_MS=100U',
    '-DSYSTEM_FLIGHT_LANDING_IMPACT_THRESHOLD_MPS2=20.0f',
    '-DSYSTEM_FLIGHT_LANDING_CONFIRM_MS=100U',
    '-DSYSTEM_SELECTED_IMU_LANDING_IMPACT_QUALIFIED=1U'
) -Sources $recoverySources
Invoke-HostTest -Name 'flight_recovery_baro_imu_landing' -ExtraCompilerArgs @(
    '-DTEST_EXPECT_NONE=1', '-DTEST_EXPECT_BARO=1',
    '-DSYSTEM_FLIGHT_DEPLOY_TRIGGER_MASK=SYSTEM_DEPLOY_TRIGGER_NONE',
    '-DSYSTEM_BUILD_LANDING_MODE=SYSTEM_LANDING_MODE_BARO_IMU_WINDOW',
    '-DSYSTEM_FLIGHT_LANDING_BARO_TRIGGER_WINDOW_MS=100U',
    '-DSYSTEM_FLIGHT_LANDING_BARO_TRIGGER_MIN_SAMPLES=3U',
    '-DSYSTEM_FLIGHT_LANDING_CANDIDATE_DURATION_MS=200U',
    '-DSYSTEM_FLIGHT_LANDING_BARO_MIN_SAMPLES=3U',
    '-DSYSTEM_FLIGHT_LANDING_IMU_MIN_SAMPLES=3U',
    '-DSYSTEM_FLIGHT_LANDING_MIN_COVERAGE_PERCENT=80U'
) -Sources $recoverySources

Invoke-ExpectedCompileFailure -Name 'impact_capability_guard' `
    -ExtraCompilerArgs @(
        '-DSYSTEM_BUILD_LANDING_MODE=SYSTEM_LANDING_MODE_IMPACT_THEN_STILLNESS',
        '-DSYSTEM_SELECTED_IMU_LANDING_IMPACT_QUALIFIED=0U'
    ) -Source "$repoRoot\Tests\Host\test_flight_config_compile.c"

Invoke-HostTest -Name 'lifecycle_logging' -Sources @(
    "$repoRoot\Tests\Host\test_lifecycle_logging.c",
    $hostPlatformMock,
    "$repoRoot\APP\Src\flight_task.c",
    "$repoRoot\APP\Src\logger_task.c",
    "$repoRoot\FlightLogic\FlightCycle\Src\silverstar_flight_cycle.c",
    "$repoRoot\System\Alignment\Src\system_alignment.c"
)

$startupSources = @(
    "$repoRoot\Tests\Host\test_system_startup.c",
    "$repoRoot\System\Src\system_startup.c"
)
Invoke-HostTest -Name 'system_startup' -Sources $startupSources
Invoke-HostTest -Name 'system_startup_write_verify' -ExtraCompilerArgs @(
    '-DSYSTEM_GNSS_BOOT_WRITE_CONFIG=1U',
    '-DSYSTEM_GNSS_BOOT_VERIFY_CONFIG=1U'
) -Sources $startupSources
Invoke-HostTest -Name 'system_startup_no_writes' -ExtraCompilerArgs @(
    '-DSYSTEM_GNSS_BOOT_WRITE_CONFIG=0U',
    '-DSYSTEM_IMU_BOOT_WRITE_CONFIG=0U'
) -Sources $startupSources

Invoke-HostTest -Name 'health' -Sources @(
    "$repoRoot\Tests\Host\test_health.c",
    $hostPlatformMock,
    "$repoRoot\System\Src\system_health.c",
    "$repoRoot\System\Src\system_navigation_profile.c"
)
Invoke-HostTest -Name 'console' -Sources @(
    "$repoRoot\Tests\Host\test_console.c",
    $hostPlatformMock,
    "$repoRoot\Common\Src\common_format.c",
    "$repoRoot\System\Src\system_console.c",
    "$repoRoot\System\Src\system_barometer.c",
    "$repoRoot\System\Src\system_estimator_diagnostics.c",
    "$repoRoot\System\Alignment\Src\system_alignment_source.c"
)
Invoke-HostTest -Name 'telemetry' -Sources @(
    "$repoRoot\Tests\Host\test_telemetry.c",
    "$repoRoot\Modules\Src\telemetry_service.c",
    "$repoRoot\System\Calibration\Src\system_calibration_correction.c",
    "$repoRoot\Protocol\Src\air_protocol.c"
)

$loggerSources = @(
    "$repoRoot\Tests\Host\test_logger.c",
    $hostPlatformMock,
    "$repoRoot\APP\Src\logger_bus.c",
    "$repoRoot\Common\Src\common_spsc_queue.c",
    "$repoRoot\System\Src\system_log_policy.c",
    "$repoRoot\System\Src\system_profile.c",
    "$repoRoot\System\Src\system_navigation_profile.c",
    "$repoRoot\System\Src\system_estimator_profile.c",
    "$repoRoot\Generated\Src\project_metadata.c",
    "$repoRoot\Generated\Src\project_log_config.c"
) + $sslogSources
Invoke-HostTest -Name 'logger' -Sources $loggerSources
Invoke-HostTest -Name 'logger_estimator_noise_overrides' `
    -ExtraCompilerArgs $estimatorNoiseOverrideArgs -Sources $loggerSources

$alignmentRuntimeFiles = @(
    "$repoRoot\Modules\Src\telemetry_service.c",
    "$repoRoot\System\Src\system_health.c",
    "$repoRoot\FlightLogic\FlightCycle\Src\silverstar_flight_cycle.c",
    "$repoRoot\System\Indicator\Src\system_indicator.c"
)
foreach ($runtimeFile in $alignmentRuntimeFiles) {
    $largeLocal = Select-String -LiteralPath $runtimeFile `
        -Pattern '\bSystemAlignmentStatus\s+[A-Za-z_][A-Za-z0-9_]*\s*;'
    $fullStatusCall = Select-String -LiteralPath $runtimeFile `
        -Pattern '\bSystemAlignment_StatusGet\s*\('
    if (($null -ne $largeLocal) -or ($null -ne $fullStatusCall)) {
        throw "Full Alignment status returned to periodic runtime path: $runtimeFile"
    }
}
Write-Output 'Alignment periodic runtime stack audit passed.'

$hostSummary = ("SilverStar host summary: executables={0} checks={1} " +
    "failures={2} compile_pass_cases={3} expected_compile_failures={4}") -f `
    $script:hostExecutableCount, $script:hostCheckCount, `
    $script:hostFailureCount, $script:compilePassCaseCount, `
    $script:expectedCompileFailureCount
Write-Output $hostSummary
Write-Output 'All SilverStar host tests passed.'
