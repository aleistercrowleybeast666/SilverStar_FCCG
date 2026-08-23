from __future__ import annotations

from silverstar_fccg.project.model import (
    BuildOptions,
    HardwareConfiguration,
    LogStreamConfig,
    ProjectIdentity,
    ProjectModel,
)


REFERENCE_COMPONENT_IDS = {
    "core": "silverstar.core.0_0_9",
    "mcu": "silverstar.mcu.stm32f407vet6",
    "board": "silverstar.board.silverstar_0_5",
    "os": "silverstar.os.freertos_11_3_0",
    "jy901b": "silverstar.device.imu.jy901b",
    "neo_m9n": "silverstar.device.gnss.neo_m9n",
    "sx1281": "silverstar.device.telemetry.sx1281",
    "console": "silverstar.device.console.uart",
    "algorithm_common": "silverstar.algorithm.common",
    "alignment_common": "silverstar.algorithm.alignment.common",
    "alignment": "silverstar.algorithm.alignment.gravity_known_yaw",
    "calibration": "silverstar.algorithm.calibration",
    "ins": "silverstar.algorithm.ins.coning2_sculling2",
    "kf6": "silverstar.algorithm.estimator.kf6",
    "flight_cycle": "silverstar.flight_logic.cycle.reference",
    "deployment": "silverstar.flight_logic.deployment.multi_trigger",
    "landing": "silverstar.flight_logic.landing.baro_imu_window",
    "protocol": "silverstar.protocol.reference_v0",
    "environment": "silverstar.environment.vscode_eide_gcc",
    "hardware_provider": "silverstar.hardware_provider.stm32_cubemx",
}


def ReferenceLogStreams_Get() -> list[LogStreamConfig]:
    values = (
        ("FLIGHT_LOG_RECORD_SAMPLE", False, "DECIMATION", 1, 0),
        ("FLIGHT_LOG_RECORD_EVENT", True, "EVENT", 1, 0),
        ("FLIGHT_LOG_RECORD_STATS", False, "PERIODIC", 1, 1_000_000),
        ("FLIGHT_LOG_RECORD_ESTIMATOR", True, "DECIMATION", 4, 0),
        ("FLIGHT_LOG_RECORD_SYSTEM_CONFIG", True, "ONE_SHOT", 1, 0),
        ("FLIGHT_LOG_RECORD_RAW_SENSOR", False, "DECIMATION", 1, 0),
        ("FLIGHT_LOG_RECORD_PURE_INS", True, "DECIMATION", 1, 0),
        ("FLIGHT_LOG_RECORD_KF6_DIAGNOSTIC", True, "DECIMATION", 4, 0),
        ("FLIGHT_LOG_RECORD_KF6_FULL_P", True, "DECIMATION", 4, 0),
        ("FLIGHT_LOG_RECORD_POWER", True, "PERIODIC", 1, 20_000),
        ("FLIGHT_LOG_RECORD_HEALTH", True, "PERIODIC", 1, 1_000_000),
        ("FLIGHT_LOG_RECORD_TELEMETRY_DIAG", False, "PERIODIC", 1, 200_000),
        ("FLIGHT_LOG_RECORD_INITIAL_STATE", True, "ONE_SHOT", 1, 0),
        ("FLIGHT_LOG_RECORD_IMU_NATIVE", False, "DECIMATION", 1, 0),
        ("FLIGHT_LOG_RECORD_GNSS_NATIVE", True, "DECIMATION", 1, 0),
        ("FLIGHT_LOG_RECORD_BARO_NATIVE", True, "DECIMATION", 1, 0),
        ("FLIGHT_LOG_RECORD_MAG_NATIVE", True, "DECIMATION", 1, 0),
        ("FLIGHT_LOG_RECORD_HW_QUAT_NATIVE", True, "DECIMATION", 1, 0),
        ("FLIGHT_LOG_RECORD_INERTIAL_INCREMENT", True, "DECIMATION", 1, 0),
        ("FLIGHT_LOG_RECORD_GNSS_MEASUREMENT", True, "EVERY", 1, 0),
        ("FLIGHT_LOG_RECORD_BARO_MEASUREMENT", True, "EVERY", 1, 0),
        ("FLIGHT_LOG_RECORD_IMU_CORRECTED", True, "DECIMATION", 1, 0),
        ("FLIGHT_LOG_RECORD_CALIBRATION_RESULT", True, "EVENT", 1, 0),
        ("FLIGHT_LOG_RECORD_ALIGNMENT_RESULT", True, "EVENT", 1, 0),
        ("FLIGHT_LOG_RECORD_MISSION_CONFIG", True, "ONE_SHOT", 1, 0),
        ("FLIGHT_LOG_RECORD_DEVICE_DESCRIPTOR", True, "ONE_SHOT", 1, 0),
        ("FLIGHT_LOG_RECORD_ALGORITHM_DESCRIPTOR", True, "ONE_SHOT", 1, 0),
        ("FLIGHT_LOG_RECORD_LOG_STREAM_DESCRIPTOR", True, "ONE_SHOT", 1, 0),
    )
    return [LogStreamConfig(*value) for value in values]


def ReferenceResourceAssignments_Get() -> dict[str, str]:
    ids = REFERENCE_COMPONENT_IDS
    return {
        f"{ids['jy901b']}:data": "PLATFORM_UART_1",
        f"{ids['jy901b']}:time": "PLATFORM_TIME_1",
        f"{ids['neo_m9n']}:data": "PLATFORM_UART_2",
        f"{ids['neo_m9n']}:reset": "PLATFORM_GPIO_7",
        f"{ids['neo_m9n']}:timepulse": "PLATFORM_GPIO_8",
        f"{ids['neo_m9n']}:time": "PLATFORM_TIME_1",
        f"{ids['sx1281']}:radio_bus": "PLATFORM_SPI_1",
        f"{ids['sx1281']}:radio_nss": "PLATFORM_GPIO_0",
        f"{ids['sx1281']}:radio_reset": "PLATFORM_GPIO_1",
        f"{ids['sx1281']}:radio_busy": "PLATFORM_GPIO_2",
        f"{ids['sx1281']}:radio_dio1": "PLATFORM_GPIO_3",
        f"{ids['sx1281']}:time": "PLATFORM_TIME_1",
        f"{ids['console']}:console": "PLATFORM_UART_3",
        f"{ids['board']}:power_output_1": "PLATFORM_GPIO_4",
        f"{ids['board']}:power_output_2": "PLATFORM_GPIO_5",
        f"{ids['board']}:system_indicator": "PLATFORM_GPIO_6",
        f"{ids['board']}:input_voltage": "PLATFORM_ADC_1",
        f"{ids['board']}:storage": "PLATFORM_SDIO_1",
    }


def ReferenceProject_Create(
    name: str = "SilverStar_F407_Reference_Generated",
    *,
    reference_provenance: dict | None = None,
) -> ProjectModel:
    ids = REFERENCE_COMPONENT_IDS
    return ProjectModel(
        identity=ProjectIdentity(name=name),
        core=ids["core"],
        mcu=ids["mcu"],
        board=ids["board"],
        os=ids["os"],
        devices=[ids["jy901b"], ids["neo_m9n"], ids["sx1281"], ids["console"]],
        base_components=[
            ids["algorithm_common"],
            ids["alignment_common"],
            ids["calibration"],
            ids["flight_cycle"],
            ids["deployment"],
        ],
        strategies={
            "alignment": ids["alignment"],
            "ins": ids["ins"],
            "estimator": ids["kf6"],
            "landing": ids["landing"],
        },
        modes={
            "calibration": ["Existing"],
            "deployment": ["ApogeeVerticalVelocity"],
        },
        protocol_bundles=[ids["protocol"]],
        development_environment=ids["environment"],
        hardware=HardwareConfiguration(
            mode="board_plugin",
            source_kind="verified_builtin",
        ),
        resource_assignments=ReferenceResourceAssignments_Get(),
        logging_streams=ReferenceLogStreams_Get(),
        build=BuildOptions(),
        reference_provenance=dict(reference_provenance or {}),
    )
