from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from silverstar_fccg.plugins.manifest import PluginManifest_Load
from silverstar_fccg.project.logging import (
    LoggingProfile_SelectAllAvailable,
    ProtocolLogDefinitions_Load,
    ProtocolLogMetadataPath_Get,
)

if TYPE_CHECKING:
    from silverstar_fccg.plugins.catalog import PluginCatalog
from silverstar_fccg.project.model import (
    BuildOptions,
    DeviceInstance,
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
    "input_voltage": "silverstar.device.sensor.input_voltage",
    "launch_ignition": "silverstar.device.actuator.launch_ignition",
    "parachute_pyro": "silverstar.device.actuator.parachute_pyro",
    "system_indicator": "silverstar.device.indicator.system_status",
    "gnss_indicator": "silverstar.device.indicator.gnss_status",
    "algorithm_common": "silverstar.algorithm.common",
    "alignment_common": "silverstar.algorithm.alignment.common",
    "alignment": "silverstar.algorithm.alignment.gravity_known_yaw",
    "calibration": "silverstar.algorithm.calibration",
    "ins": "silverstar.algorithm.ins.coning2_sculling2",
    "kf6": "silverstar.algorithm.estimator.kf6",
    "flight_cycle": "silverstar.flight_logic.cycle.reference",
    "deployment": "silverstar.flight_logic.deployment.multi_trigger",
    "landing_common": "silverstar.flight_logic.landing.baro_imu_window",
    "landing": "silverstar.flight_logic.landing.baro_imu_window_strategy",
    "protocol": "silverstar.protocol.reference_v0",
    "environment": "silverstar.environment.vscode_eide_gcc",
    "hardware_provider": "silverstar.hardware_provider.stm32_cubemx",
}


def ProtocolDefaultStreams_Get() -> list[LogStreamConfig]:
    """Load new-project defaults from Protocol-owned metadata.

    Every record available in the reference composition starts enabled. Existing
    projects retain their serialized choices when they are opened.
    """
    repository_root = Path(__file__).resolve().parents[3]
    manifest = PluginManifest_Load(
        repository_root
        / "plugins"
        / "builtin"
        / "silverstar_protocol_reference_v0"
        / "plugin.json"
    )
    return [
        LogStreamConfig(
            definition.record,
            True,
            definition.default_stream.policy,
            definition.default_stream.decimation,
            definition.default_stream.period_us,
        )
        for definition in ProtocolLogDefinitions_Load(
            ProtocolLogMetadataPath_Get(manifest)
        )
    ]


def ReferenceResourceAssignments_Get() -> dict[str, str]:
    ids = REFERENCE_COMPONENT_IDS
    return {
        "imu0:data": "PLATFORM_UART_1",
        "imu0:time": "PLATFORM_TIME_1",
        "gnss0:data": "PLATFORM_UART_2",
        "gnss0:reset": "PLATFORM_GPIO_7",
        "gnss0:timepulse": "PLATFORM_GPIO_8",
        "gnss0:time": "PLATFORM_TIME_1",
        "telemetry0:radio_bus": "PLATFORM_SPI_1",
        "telemetry0:radio_nss": "PLATFORM_GPIO_0",
        "telemetry0:radio_reset": "PLATFORM_GPIO_1",
        "telemetry0:radio_busy": "PLATFORM_GPIO_2",
        "telemetry0:radio_dio1": "PLATFORM_GPIO_3",
        "telemetry0:time": "PLATFORM_TIME_1",
        "maintenance0:console": "PLATFORM_UART_3",
        "launch_ignition0:output": "PLATFORM_GPIO_4",
        "parachute_pyro0:output": "PLATFORM_GPIO_5",
        "system_indicator0:output": "PLATFORM_GPIO_6",
        "voltage_monitor0:input_voltage": "PLATFORM_ADC_1",
        f"{ids['board']}:storage": "PLATFORM_SDIO_1",
    }


def ReferenceProject_Create(
    name: str = "SilverStar_F407_Reference_Generated",
    *,
    reference_provenance: dict | None = None,
    catalog: PluginCatalog | None = None,
) -> ProjectModel:
    ids = REFERENCE_COMPONENT_IDS
    model = ProjectModel(
        identity=ProjectIdentity(name=name),
        core=ids["core"],
        mcu=ids["mcu"],
        board=ids["board"],
        os=ids["os"],
        device_instances=[
            DeviceInstance("imu0", ids["jy901b"]),
            DeviceInstance("gnss0", ids["neo_m9n"]),
            DeviceInstance("telemetry0", ids["sx1281"]),
            DeviceInstance("maintenance0", ids["console"]),
            DeviceInstance("voltage_monitor0", ids["input_voltage"]),
            DeviceInstance("launch_ignition0", ids["launch_ignition"]),
            DeviceInstance("parachute_pyro0", ids["parachute_pyro"]),
            DeviceInstance("system_indicator0", ids["system_indicator"]),
        ],
        base_components=[
            ids["algorithm_common"],
            ids["alignment_common"],
            ids["calibration"],
            ids["flight_cycle"],
            ids["deployment"],
            ids["landing_common"],
        ],
        strategies={
            "alignment": ids["alignment"],
            "ins": ids["ins"],
            "estimator": ids["kf6"],
            "landing": ids["landing"],
        },
        modes={
            "calibration": ["Existing", "OneFace", "SixFace"],
            "deployment": ["ApogeeVerticalVelocity", "Tilt"],
        },
        protocol_bundles=[ids["protocol"]],
        development_environment=ids["environment"],
        hardware=HardwareConfiguration(
            mode="board_plugin",
            source_kind="verified_builtin",
        ),
        resource_assignments=ReferenceResourceAssignments_Get(),
        logging_streams=ProtocolDefaultStreams_Get(),
        build=BuildOptions(),
        reference_provenance=dict(reference_provenance or {}),
    )
    if catalog is None:
        from silverstar_fccg.plugins.catalog import PluginCatalog

        repository_root = Path(__file__).resolve().parents[3]
        catalog = PluginCatalog(
            repository_root / "plugins" / "builtin",
            repository_root / "plugins" / "installed",
        )
        catalog.Scan()
    LoggingProfile_SelectAllAvailable(model, catalog)
    return model
