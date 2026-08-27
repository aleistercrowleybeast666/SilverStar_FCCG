from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = WORKSPACE_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from silverstar_fccg.core.workspace import WorkspacePolicy  # noqa: E402
from silverstar_fccg.plugins.catalog import PluginCatalog  # noqa: E402


BUILTIN_ROOT = WORKSPACE_ROOT / "plugins" / "builtin"
REFERENCE_OVERLAY_ROOT = WORKSPACE_ROOT / "tools" / "reference_overlays"
REFERENCE_MARKERS = (
    "SilverStar.ssproject",
    "AGENTS.md",
    "Algorithm/module.mk",
    "FlightLogic/module.mk",
    "Targets/SilverStar_F407",
    "Platform",
    "Devices",
    "Generated",
)

REFERENCE_REQUIRED_FILES = (
    "Generated/Inc/project_device_instances.h",
    "Generated/Inc/project_log_decoder_profile.h",
    "Generated/Src/project_device_instances.c",
    "Generated/Src/project_log_decoder_profile.c",
    "Generated/Src/project_log_config.c",
    "Generated/Src/project_metadata.c",
    "Generated/project_semantics.json",
    "Interfaces/Inc/system_descriptor_if.h",
    "System/Src/system_console.c",
    "System/Src/system_sensor_status.c",
    "Protocol/SSLOG/Inc/sslog_records.h",
    "Protocol/SSLOG/Src/sslog_records.c",
    "Protocol/SSLOG/schema/sslog_schema.json",
    "Protocol/SSLOG/schema/sslog_parser_metadata.json",
    "Protocol/SSLOG/schema/sslog_record_catalog.schema.json",
    "APP/Inc/diagnostic_log.h",
    "APP/Src/diagnostic_log.c",
    "APP/Src/device_task.c",
    "APP/Src/device_native_log.c",
    "APP/Src/logger_task.c",
    "APP/Src/telemetry_task.c",
    "Tests/Host/Fixtures/multi_instance_project_fixture.c",
    "Tests/Host/run_tests.ps1",
    "Tests/Host/test_console.c",
    "Tests/Host/test_device_native_log.c",
    "Tests/Host/test_logger.c",
    "Tools/check_architecture.ps1",
    "Tools/validate_sslog_record_catalog.py",
    "docs/details/MAINTENANCE_PROTOCOL.md",
    "docs/details/STORAGE_AND_FLIGHT_LOG.md",
    "docs/details/AIR_PROTOCOL.md",
    "docs/details/ARCHITECTURE.md",
    "docs/details/FCCG_COMPONENT_BOUNDARIES.md",
    "docs/details/VALIDATION_REQUIREMENTS.md",
)

REFERENCE_IMPORT_GROUPS = (
    "Generated device-instance facade contract",
    "Generated decoder-profile descriptor and project-semantics contract",
    "descriptor and physical-device identity interfaces",
    "native capability logging production code and Host Tests",
    "periodic STATS and TELEMETRY_DIAG producers and Host validation",
    "SSLOG codec, schema and parser metadata",
    "SSLOG Record Catalog schema and validator",
    "maintenance instance-command implementation and Host Tests",
    "AIR M0 Sensor Status metadata and golden tests",
    "official architecture, protocol and component-boundary documents",
)


def _Git_Run(reference: Path, *arguments: str) -> str:
    safe_path = reference.as_posix()
    environment = os.environ.copy()
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    result = subprocess.run(
        ["git", "-c", f"safe.directory={safe_path}", *arguments],
        cwd=reference,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
    )
    return result.stdout


def _ReferenceCandidate_Is(path: Path) -> bool:
    return path.is_dir() and all((path / marker).exists() for marker in REFERENCE_MARKERS)


def ReferenceCandidates_Find(search_roots: list[Path]) -> tuple[Path, ...]:
    candidates: set[Path] = set()
    for search_root in search_roots:
        root = search_root.resolve()
        if _ReferenceCandidate_Is(root):
            candidates.add(root)
        if not root.is_dir():
            continue
        for project_file in root.rglob("SilverStar.ssproject"):
            candidate = project_file.parent.resolve()
            if _ReferenceCandidate_Is(candidate):
                candidates.add(candidate)
    return tuple(sorted(candidates, key=lambda path: path.as_posix().casefold()))


def ReferencePath_Resolve(
    reference: Path | None, search_roots: list[Path]
) -> Path:
    if reference is not None:
        resolved = reference.resolve()
        if not _ReferenceCandidate_Is(resolved):
            raise RuntimeError(
                f"Reference does not contain the required SilverStar markers: {resolved}"
            )
        return resolved
    candidates = ReferenceCandidates_Find(search_roots or [WORKSPACE_ROOT])
    if len(candidates) != 1:
        listing = "\n".join(f"  - {path}" for path in candidates) or "  (none)"
        raise RuntimeError(
            "Reference discovery requires exactly one candidate. "
            "Use --reference <path>. Candidates:\n" + listing
        )
    return candidates[0]


def _ReferenceSnapshotDigest_Get(reference: Path) -> str:
    tracked = _Git_Run(reference, "ls-files", "-z").split("\0")
    digest = hashlib.sha256()
    for relative_text in sorted(item for item in tracked if item):
        path = reference.joinpath(*relative_text.split("/"))
        if not path.is_file():
            continue
        digest.update(relative_text.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def ReferenceProvenance_Get(reference: Path) -> dict[str, Any]:
    commit = _Git_Run(reference, "rev-parse", "HEAD").strip()
    commit_time_utc = _Git_Run(
        reference, "show", "-s", "--format=%cI", "HEAD"
    ).strip()
    branch = _Git_Run(reference, "branch", "--show-current").strip()
    status_lines = tuple(
        line for line in _Git_Run(reference, "status", "--porcelain").splitlines() if line
    )
    return {
        "path": str(reference),
        "commit": commit,
        "commit_time_utc": commit_time_utc,
        "branch": branch,
        "working_tree": "clean" if not status_lines else "modified",
        "status": list(status_lines),
        "snapshot_digest": _ReferenceSnapshotDigest_Get(reference),
        "recorded_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
    }


def ReferenceAudit_Get(reference: Path) -> dict[str, Any]:
    missing = tuple(
        relative
        for relative in REFERENCE_REQUIRED_FILES
        if not reference.joinpath(*relative.split("/")).is_file()
    )
    maintenance_path = reference / "docs" / "details" / "MAINTENANCE_PROTOCOL.md"
    maintenance_text = (
        maintenance_path.read_text(encoding="utf-8")
        if maintenance_path.is_file()
        else ""
    )
    expected_examples = (
        "| `IMU STATUS` | `BAD_FORMAT/INSTANCE_REQUIRED` |",
        "| `IMU -1 STATUS` | `BAD_INSTANCE/FORMAT` |",
        "| `IMU X STATUS` | `BAD_INSTANCE/FORMAT` |",
        "| `IMU 256 STATUS` | `BAD_INSTANCE/RANGE` |",
        "| `GNSS 0 STATUS EXTRA` | `BAD_FORMAT/TOKEN_COUNT` |",
    )
    public_semantics_reference = (
        "按第4节的公共命令错误语义" in maintenance_text
        or "公共命令错误语义" in maintenance_text
    )
    findings: list[str] = []
    if not public_semantics_reference:
        findings.append(
            "MAINTENANCE_PROTOCOL.md does not reference the public command "
            "semantics for CONFIG VERIFY/APPLY capability failures."
        )
    missing_examples = tuple(
        example for example in expected_examples if example not in maintenance_text
    )
    if missing_examples:
        findings.append(
            "MAINTENANCE_PROTOCOL.md instance-format examples are incomplete: "
            + ", ".join(missing_examples)
        )
    return {
        "required_files": list(REFERENCE_REQUIRED_FILES),
        "missing_required_files": list(missing),
        "maintenance_document_findings": findings,
        "maintenance_document_accepted": not findings,
        "import_groups": list(REFERENCE_IMPORT_GROUPS),
    }


def _ManifestValues_Get(reference: Path, relative: str, variable: str) -> list[str]:
    text = (reference / relative).read_text(encoding="utf-8")
    collapsed = re.sub(r"\\\s*\r?\n", " ", text)
    values: list[str] = []
    for match in re.finditer(
        rf"(?m)^\s*{re.escape(variable)}\s*\+=\s*(.*)$", collapsed
    ):
        values.extend(match.group(1).split())
    return values


def _Component(
    component_id: str,
    name: str,
    component_type: str,
    component_class: str,
    roots: list[str],
    *,
    description: str,
    provenance: dict[str, Any],
    sources: list[str] | None = None,
    asm_sources: list[str] | None = None,
    includes: list[str] | None = None,
    defines: list[str] | None = None,
    dependencies: list[str] | None = None,
    resources_required: list[dict[str, Any]] | None = None,
    resources_provided: list[dict[str, Any]] | None = None,
    resource_roles: list[dict[str, Any]] | None = None,
    resource_conflicts: list[dict[str, Any]] | None = None,
    provides: list[str] | None = None,
    capabilities_required: list[str | dict[str, str]] | None = None,
    build_extra: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    selection: dict[str, Any] | None = None,
    board: dict[str, Any] | None = None,
    hardware_provider: dict[str, Any] | None = None,
    environment: dict[str, Any] | None = None,
    instance_policy: dict[str, Any] | None = None,
    physical_device: dict[str, str] | None = None,
    protocol: dict[str, str] | None = None,
    transports: list[dict[str, Any]] | None = None,
    docs: list[str] | None = None,
    version: str = "0.0.9",
) -> dict[str, Any]:
    build: dict[str, Any] = {
        "sources": sources or [],
        "asm_sources": asm_sources or [],
        "include_dirs": includes or [],
        "defines": defines or [],
    }
    build.update(build_extra or {})
    manifest: dict[str, Any] = {
        "schema_version": 0,
        "id": component_id,
        "name": name,
        "type": component_type,
        "class": component_class,
        "version": version,
        "description": description,
        "requires": {
            "components": [
                {"id": dependency, "optional": False}
                for dependency in (dependencies or [])
            ],
            "resources": resources_required or [],
            "capabilities": capabilities_required or [],
        },
        "resources": {
            "provides": resources_provided or [],
            "roles": resource_roles or [],
            "conflicts": resource_conflicts or [],
        },
        "provides": provides or [],
        "build": build,
        "payload": {"roots": roots},
        "metadata": {
            "reference": provenance,
            **(metadata or {}),
        },
    }
    for key, value in (
        ("selection", selection),
        ("board", board),
        ("hardware_provider", hardware_provider),
        ("environment", environment),
        ("instance_policy", instance_policy),
        ("physical_device", physical_device),
        ("protocol", protocol),
        ("transports", transports),
    ):
        if value is not None:
            manifest[key] = value
    return {"manifest": manifest, "docs": docs or []}


def _PlatformResources_Get() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    provisions: list[dict[str, Any]] = []
    for index in range(1, 4):
        provisions.append(
            {
                "id": f"PLATFORM_UART_{index}",
                "kind": "uart",
                "metadata": {
                    "c_id": f"PLATFORM_UART_{index}",
                    "header": "platform_uart.h",
                },
            }
        )
    provisions.append(
        {
            "id": "PLATFORM_SPI_1",
            "kind": "spi",
            "metadata": {"c_id": "PLATFORM_SPI_1", "header": "platform_spi.h"},
        }
    )
    gpio_kinds = (
        "gpio_output",
        "gpio_output",
        "gpio_input",
        "gpio_interrupt",
        "gpio_output",
        "gpio_output",
        "gpio_output",
        "gpio_output",
        "gpio_interrupt",
    )
    for index, kind in enumerate(gpio_kinds):
        provisions.append(
            {
                "id": f"PLATFORM_GPIO_{index}",
                "kind": kind,
                "metadata": {
                    "c_id": f"PLATFORM_GPIO_{index}",
                    "header": "platform_gpio.h",
                },
            }
        )
    provisions.extend(
        [
            {
                "id": "PLATFORM_ADC_1",
                "kind": "adc",
                "metadata": {"c_id": "PLATFORM_ADC_1", "header": "platform_adc.h"},
            },
            {"id": "PLATFORM_SDIO_1", "kind": "sdio", "metadata": {}},
            {"id": "PLATFORM_TIME_1", "kind": "time", "metadata": {}},
        ]
    )
    platform = {
        "uarts": [
            {"id": "PLATFORM_UART_1", "handle": "huart1"},
            {"id": "PLATFORM_UART_2", "handle": "huart2"},
            {"id": "PLATFORM_UART_3", "handle": "huart3"},
        ],
        "spis": [{"id": "PLATFORM_SPI_1", "handle": "hspi1"}],
        "adcs": [{"id": "PLATFORM_ADC_1", "handle": "hadc1"}],
        "gpios": [
            {"id": "PLATFORM_GPIO_0", "port": "RADIO_NSS_GPIO_Port", "pin": "RADIO_NSS_Pin"},
            {"id": "PLATFORM_GPIO_1", "port": "RADIO_RST_GPIO_Port", "pin": "RADIO_RST_Pin"},
            {"id": "PLATFORM_GPIO_2", "port": "RADIO_BUSY_GPIO_Port", "pin": "RADIO_BUSY_Pin"},
            {"id": "PLATFORM_GPIO_3", "port": "RADIO_DIO1_GPIO_Port", "pin": "RADIO_DIO1_Pin", "active_high": 1},
            {"id": "PLATFORM_GPIO_4", "port": "P_CONTROL1_GPIO_Port", "pin": "P_CONTROL1_Pin"},
            {"id": "PLATFORM_GPIO_5", "port": "P_CONTROL2_GPIO_Port", "pin": "P_CONTROL2_Pin"},
            {"id": "PLATFORM_GPIO_6", "port": "IMU_CAL_LED_GPIO_Port", "pin": "IMU_CAL_LED_Pin"},
            {"id": "PLATFORM_GPIO_7", "port": "GNSS_RST_GPIO_Port", "pin": "GNSS_RST_Pin"},
            {"id": "PLATFORM_GPIO_8", "port": "GNSS_TIMEPULSE_GPIO_Port", "pin": "GNSS_TIMEPULSE_Pin", "active_high": 1},
        ],
    }
    return provisions, platform


def _BoardRoles_Get() -> list[dict[str, Any]]:
    mappings = (
        ("imu:data", "uart", "PLATFORM_UART_1"),
        ("imu:time", "time", "PLATFORM_TIME_1"),
        ("gnss:data", "uart", "PLATFORM_UART_2"),
        ("gnss:reset", "gpio_output", "PLATFORM_GPIO_7"),
        ("gnss:timepulse", "gpio_interrupt", "PLATFORM_GPIO_8"),
        ("gnss:time", "time", "PLATFORM_TIME_1"),
        ("telemetry:radio_bus", "spi", "PLATFORM_SPI_1"),
        ("telemetry:radio_nss", "gpio_output", "PLATFORM_GPIO_0"),
        ("telemetry:radio_reset", "gpio_output", "PLATFORM_GPIO_1"),
        ("telemetry:radio_busy", "gpio_input", "PLATFORM_GPIO_2"),
        ("telemetry:radio_dio1", "gpio_interrupt", "PLATFORM_GPIO_3"),
        ("telemetry:time", "time", "PLATFORM_TIME_1"),
        ("console:console", "uart", "PLATFORM_UART_3"),
        (
            "silverstar.device.actuator.launch_ignition:output",
            "gpio_output",
            "PLATFORM_GPIO_4",
        ),
        (
            "silverstar.device.actuator.parachute_pyro:output",
            "gpio_output",
            "PLATFORM_GPIO_5",
        ),
        (
            "silverstar.device.indicator.system_status:output",
            "gpio_output",
            "PLATFORM_GPIO_6",
        ),
        (
            "silverstar.device.sensor.input_voltage:input_voltage",
            "adc",
            "PLATFORM_ADC_1",
        ),
        ("flight_controller_board:storage", "sdio", "PLATFORM_SDIO_1"),
    )
    return [
        {
            "key": key,
            "kind": kind,
            "default": resource_id,
            "candidates": [resource_id],
            "fixed": True,
        }
        for key, kind, resource_id in mappings
    ]


def _BoardConnections_Get() -> dict[str, Any]:
    mappings = (
        ("PLATFORM_UART_1", "USART1", "imu.data"),
        ("PLATFORM_UART_2", "USART2", "gnss.data"),
        ("PLATFORM_UART_3", "USART3", "console.data"),
        ("PLATFORM_SPI_1", "SPI1", "telemetry.bus"),
        ("PLATFORM_GPIO_0", "RADIO_NSS", "telemetry.nss"),
        ("PLATFORM_GPIO_1", "RADIO_RST", "telemetry.reset"),
        ("PLATFORM_GPIO_2", "RADIO_BUSY", "telemetry.busy"),
        ("PLATFORM_GPIO_3", "RADIO_DIO1", "telemetry.dio1"),
        ("PLATFORM_GPIO_4", "P_CONTROL1", "actuator.launch_ignition"),
        ("PLATFORM_GPIO_5", "P_CONTROL2", "actuator.parachute_pyro"),
        ("PLATFORM_GPIO_6", "IMU_CAL_LED", "system.indicator"),
        ("PLATFORM_GPIO_7", "GNSS_RST", "gnss.reset"),
        ("PLATFORM_GPIO_8", "GNSS_TIMEPULSE", "gnss.timepulse"),
        ("PLATFORM_ADC_1", "ADC1", "power.input_voltage"),
        ("PLATFORM_SDIO_1", "SDIO", "storage"),
        ("PLATFORM_TIME_1", "SYSTEM_TIME", "system.time"),
    )
    return {
        "format_version": 1,
        "resources": {
            alias: {"physical": physical, "fixed": True, "purpose": purpose}
            for alias, physical, purpose in mappings
        },
    }


def _Components_Get(
    reference: Path, provenance: dict[str, Any]
) -> list[dict[str, Any]]:
    first_party = _ManifestValues_Get(reference, "BuildSystem/first_party.mk", "C_SOURCES")
    core_sources = [
        path
        for path in first_party
        if path.startswith(("APP/", "Common/", "Modules/", "System/"))
    ]
    board_sources = [path for path in first_party if path.startswith("Core/")]
    board_sources += _ManifestValues_Get(reference, "Board/SilverStar_0_5/module.mk", "C_SOURCES")
    board_sources += _ManifestValues_Get(reference, "BuildSystem/fatfs.mk", "C_SOURCES")
    mcu_sources = _ManifestValues_Get(reference, "Platform/STM32F4/module.mk", "C_SOURCES")
    mcu_sources += _ManifestValues_Get(reference, "BuildSystem/stm32_hal.mk", "C_SOURCES")
    os_sources = [
        path
        for path in first_party
        if path.startswith(("OS/", "Targets/SilverStar_F407/Src/freertos"))
    ]
    os_sources += _ManifestValues_Get(reference, "BuildSystem/freertos.mk", "C_SOURCES")
    protocol_sources = [path for path in first_party if path.startswith("Protocol/")]
    core_id = "silverstar.core.0_0_9"
    mcu_id = "silverstar.mcu.stm32f407vet6"
    board_id = "silverstar.board.silverstar_0_5"
    device_flags = "SYSTEM_DESCRIPTOR_FLAG_ENABLED"
    primary_flags = f"{device_flags} | SYSTEM_DESCRIPTOR_FLAG_PRIMARY"
    components: list[dict[str, Any]] = []

    components.append(
        _Component(
            core_id,
            "SilverStar Core 0.0.9",
            "core",
            "flight_controller_core",
            ["APP", "Common", "Interfaces", "Modules", "System", "Tests", "Tools", "BuildSystem/first_party.mk", ".clang-format"],
            description="MCU-independent SilverStar application, system, interfaces and host validation sources.",
            provenance=provenance,
            sources=core_sources,
            includes=["APP/Inc", "Common/Inc", "Modules/Inc", "Interfaces/Inc", "System/Inc", "System/Alignment/Inc", "System/Calibration/Inc", "System/Indicator/Inc", "System/Inertial/Inc", "System/User"],
            capabilities_required=[],
            provides=["core.silverstar", "interface.canonical", "system.lifecycle"],
            metadata={
                "display_names": {"zh_CN": "SilverStar 核心 0.0.9", "en_US": "SilverStar Core 0.0.9"},
                "log_producers": [
                    "silverstar.core.device_task",
                    "silverstar.core.telemetry_task",
                ],
                "device_descriptors": [{"order": 12, "physical_device_id": "PROJECT_PHYSICAL_DEVICE_ID_NONE", "class": "SYSTEM_DEVICE_CLASS_TIME", "instance": 0, "driver_id": 1, "flags": primary_flags, "capability": "0U", "rate": "1000000UL", "driver_hash": "0x162F2C94UL", "name_hash": "0xADE08D82UL"}],
            },
            docs=[
                "docs/SilverStar_0_0_9.md",
                "docs/details/ARCHITECTURE.md",
                "docs/details/SYSTEM_LIFECYCLE.md",
                "docs/details/SYSTEM_PROFILE.md",
                "docs/details/FCCG_COMPONENT_BOUNDARIES.md",
                "docs/details/VALIDATION_REQUIREMENTS.md",
                "VALIDATION.md",
            ],
        )
    )
    components.append(
        _Component(
            mcu_id,
            "STM32F407VET6",
            "mcu",
            "stm32f4",
            ["Platform", "Drivers", "BuildSystem/stm32_hal.mk", "Targets/SilverStar_F407/Inc/platform_memory_target.h", "Targets/SilverStar_F407/Inc/target_system_config.h", "Targets/SilverStar_F407/Inc/target_build_capabilities.h", "startup_stm32f407xx.s", "STM32F407XX_FLASH.ld"],
            description="STM32F407VET6 capabilities, STM32F4 Platform backend, HAL/CMSIS dependency and target memory contract.",
            provenance=provenance,
            sources=mcu_sources,
            asm_sources=["startup_stm32f407xx.s"],
            includes=["Platform/Inc", "Platform/STM32F4/Inc", "Drivers/STM32F4xx_HAL_Driver/Inc", "Drivers/STM32F4xx_HAL_Driver/Inc/Legacy", "Drivers/CMSIS/Device/ST/STM32F4xx/Include", "Drivers/CMSIS/Include", "Targets/SilverStar_F407/Inc"],
            defines=["USE_HAL_DRIVER", "STM32F407xx"],
            provides=["mcu.cortex_m4f", "platform.stm32f4", "memory.ccmram", "hardware_provider.stm32_cubemx"],
            build_extra={"mcu_flags": ["-mcpu=cortex-m4", "-mthumb", "-mfpu=fpv4-sp-d16", "-mfloat-abi=hard"], "specs": ["-specs=nano.specs"], "libraries": ["-lc", "-lm", "-lnosys"], "forced_includes": ["Targets/SilverStar_F407/Inc/platform_memory_target.h"], "linker_script": "STM32F407XX_FLASH.ld", "toolchain_prefix": "arm-none-eabi-"},
            metadata={"vendor": "STM32", "mcu_model": "STM32F407VET6", "display_names": {"zh_CN": "STM32F407VET6", "en_US": "STM32F407VET6"}, "supported_environments": ["silverstar.environment.vscode_eide_gcc"], "supported_toolchains": ["arm-none-eabi-gcc"]},
            docs=["docs/details/PLATFORM_INTERFACE.md", "docs/details/BUILD_AND_TARGETS.md"],
        )
    )

    provisions, _legacy_platform_resources = _PlatformResources_Get()
    components.append(
        _Component(
            board_id,
            "SS0.5",
            "board",
            "flight_controller_board",
            ["Board/SilverStar_0_5", "Core", "FATFS", "Middlewares/Third_Party/FatFs", "BuildSystem/fatfs.mk", "Flight_Controller0.5.ioc", ".mxproject"],
            description="Verified SS0.5 PCB, CubeMX hardware source, fixed services and resource mapping.",
            provenance=provenance,
            sources=board_sources,
            includes=["Core/Inc", "Board/SilverStar_0_5/Services/Inc", "FATFS/Target", "FATFS/App", "Middlewares/Third_Party/FatFs/src"],
            dependencies=[core_id, mcu_id],
            resources_required=[
                {"name": "storage", "kind": "sdio"},
            ],
            resources_provided=provisions,
            resource_roles=_BoardRoles_Get(),
            provides=["board.silverstar_0_5", "hardware.stm32.generated", "service.output", "service.storage", "service.log_sink", "transport.sequential_file_sink"],
            metadata={
                "build_symbol": "SILVERSTAR_0_5",
                "display_names": {"zh_CN": "SS0.5（已验证）", "en_US": "SS0.5 (Validated)"},
                "descriptions": {
                    "zh_CN": "已验证的SS0.5板卡、CubeMX硬件源、固定服务与资源映射。",
                    "en_US": "Verified SS0.5 PCB, CubeMX hardware source, fixed services, and resource mapping.",
                },
                "optional_resource_bindings": [
                    {
                        "binding_macro": "PROJECT_RESOURCE_SYSTEM_INDICATOR",
                        "enabled_macro": "PROJECT_FEATURE_SYSTEM_STATUS_INDICATOR",
                        "fallback": "PLATFORM_GPIO_COUNT",
                        "header": "platform_gpio.h",
                    },
                    {
                        "binding_macro": "PROJECT_RESOURCE_GNSS_INDICATOR",
                        "enabled_macro": "PROJECT_FEATURE_GNSS_STATUS_INDICATOR",
                        "fallback": "PLATFORM_GPIO_COUNT",
                        "header": "platform_gpio.h",
                    },
                    {
                        "binding_macro": "PROJECT_RESOURCE_INPUT_VOLTAGE_ADC",
                        "enabled_macro": "PROJECT_FEATURE_INPUT_VOLTAGE_MONITOR",
                        "fallback": "PLATFORM_ADC_COUNT",
                        "header": "platform_adc.h",
                    },
                    {
                        "binding_macro": "PROJECT_RESOURCE_LAUNCH_IGNITION_OUTPUT",
                        "enabled_macro": "PROJECT_FEATURE_LAUNCH_IGNITION_OUTPUT",
                        "fallback": "PLATFORM_GPIO_COUNT",
                        "header": "platform_gpio.h",
                    },
                    {
                        "binding_macro": "PROJECT_RESOURCE_PARACHUTE_PYRO_OUTPUT",
                        "enabled_macro": "PROJECT_FEATURE_PARACHUTE_PYRO_OUTPUT",
                        "fallback": "PLATFORM_GPIO_COUNT",
                        "header": "platform_gpio.h",
                    },
                ],
                "device_descriptors": [
                    {"order": 8, "physical_device_id": "PROJECT_PHYSICAL_DEVICE_ID_STORAGE", "class": "SYSTEM_DEVICE_CLASS_STORAGE", "flags": f"{device_flags} | SYSTEM_DESCRIPTOR_FLAG_SHARED_PHYSICAL", "capability": "SYSTEM_CAPABILITY_STORAGE", "rate": "0U", "driver_hash": "0xF02E45D5UL", "name_hash": "0x3A7B5375UL"},
                    {"order": 9, "physical_device_id": "PROJECT_PHYSICAL_DEVICE_ID_STORAGE", "class": "SYSTEM_DEVICE_CLASS_LOG_SINK", "flags": f"{device_flags} | SYSTEM_DESCRIPTOR_FLAG_SHARED_PHYSICAL", "capability": "SYSTEM_CAPABILITY_STORAGE", "rate": "0U", "driver_hash": "0x6DB00410UL", "name_hash": "0xCD7C84A3UL"},
                ],
            },
            build_extra={"exclude_sources": ["Core/Src/sysmem.c"]},
            board={"source_kind": "verified_builtin", "compatible_mcus": [mcu_id], "vendor": "STM32", "provider": "silverstar.hardware_provider.stm32_cubemx", "verified": True, "hardware_root": "Core", "ioc_file": "payload/Flight_Controller0.5.ioc", "connections_file": "connections.json"},
            transports=[{"capability": "transport.sequential_file_sink", "kind": "sequential_file_sink", "mtu": 65535, "ordered": True, "bidirectional": False, "reliable": True, "mode": "file"}],
            docs=["docs/details/STORAGE_AND_FLIGHT_LOG.md", "docs/details/BUILD_AND_TARGETS.md"],
        )
    )

    device_specs = (
        ("silverstar.device.imu.jy901b", "JY901B", "imu", "Devices/IMU/JY901B/module.mk", ["Devices/IMU/JY901B"], ["Devices/IMU/JY901B/Inc", "Devices/IMU/JY901B/Adapter/Inc"], [
            {"name": "data", "kind": "uart", "binding_macro": "PROJECT_RESOURCE_IMU_UART", "constraints": {"uart": {"baud": {"exact": 230400, "configurable": False}, "word_length": 8, "parity": "none", "stop_bits": 1.0, "rx_dma": True, "tx_dma": False, "irq": True}}},
            {"name": "time", "kind": "time", "mode": "shared"},
        ], [
            "device.imu",
            "imu.acceleration",
            "imu.angular_rate",
            "attitude.external",
            "magnetometer.field",
            "barometer.altitude",
            "attitude.external.preflight_alignment_6axis_qualified",
            "attitude.external.preflight_alignment_9axis_qualified",
            "attitude.external.preflight_fallback_qualified",
            "imu.software_alignment_qualified",
            "imu.software_propagation_qualified",
            "imu.landing_stillness_qualified",
            "barometer.landing_window_qualified",
        ], [
            {"order": 1, "physical_device_id": "PROJECT_PHYSICAL_DEVICE_ID_JY901B", "class": "SYSTEM_DEVICE_CLASS_IMU", "flags": f"{device_flags} | SYSTEM_DESCRIPTOR_FLAG_REQUIRED | SYSTEM_DESCRIPTOR_FLAG_PRIMARY | SYSTEM_DESCRIPTOR_FLAG_SHARED_PHYSICAL", "capability": "SYSTEM_CAPABILITY_IMU", "rate": "SYSTEM_IMU_OUTPUT_RATE_HZ", "driver_hash": "0xADF02482UL", "name_hash": "0x53692179UL"},
            {"order": 3, "physical_device_id": "PROJECT_PHYSICAL_DEVICE_ID_JY901B", "class": "SYSTEM_DEVICE_CLASS_BAROMETER", "flags": f"{device_flags} | SYSTEM_DESCRIPTOR_FLAG_SHARED_PHYSICAL", "capability": "SYSTEM_CAPABILITY_BAROMETER", "rate": "SYSTEM_BAROMETER_OUTPUT_RATE_HZ", "driver_hash": "0xADF02482UL", "name_hash": "0x53692179UL"},
            {"order": 4, "physical_device_id": "PROJECT_PHYSICAL_DEVICE_ID_JY901B", "class": "SYSTEM_DEVICE_CLASS_HARDWARE_QUATERNION", "flags": f"{device_flags} | SYSTEM_DESCRIPTOR_FLAG_SHARED_PHYSICAL", "capability": "SYSTEM_CAPABILITY_HARDWARE_QUATERNION", "rate": "SYSTEM_HARDWARE_QUATERNION_OUTPUT_RATE_HZ", "driver_hash": "0xADF02482UL", "name_hash": "0x53692179UL"},
            {"order": 13, "physical_device_id": "PROJECT_PHYSICAL_DEVICE_ID_JY901B", "class": "SYSTEM_DEVICE_CLASS_MAGNETOMETER", "flags": f"SYSTEM_DESCRIPTOR_FLAG_SHARED_PHYSICAL | ((SYSTEM_USER_MAGNETOMETER_ENABLE != 0U) ? {device_flags} : 0U)", "capability": "SYSTEM_CAPABILITY_MAGNETOMETER", "rate": "SYSTEM_MAGNETOMETER_OUTPUT_RATE_HZ", "driver_hash": "0xADF02482UL", "name_hash": "0x53692179UL"},
        ], ["docs/details/IMU_JY901B.md", "docs/details/DEVICE_INTERFACE.md"]),
        ("silverstar.device.gnss.neo_m9n", "NEO-M9N", "gnss", "Devices/GNSS/NEO_M9N/module.mk", ["Devices/GNSS/NEO_M9N"], ["Devices/GNSS/NEO_M9N/Inc"], [
            {"name": "data", "kind": "uart", "binding_macro": "PROJECT_RESOURCE_GNSS_UART", "constraints": {"uart": {"baud": {"exact": 921600, "configurable": False}, "word_length": 8, "parity": "none", "stop_bits": 1.0, "rx_dma": True, "tx_dma": False, "irq": True}}},
            {"name": "reset", "kind": "gpio_output", "binding_macro": "PROJECT_RESOURCE_GNSS_RESET", "electrical_constraints": {"mode": "gpio_output", "output_type": "push_pull", "pull": "none", "speed": "low", "safe_initial_level": "inactive", "active_polarity": "low", "startup_glitch_free": True}},
            {"name": "timepulse", "kind": "gpio_interrupt", "binding_macro": "PROJECT_RESOURCE_GNSS_TIMEPULSE", "electrical_constraints": {"mode": "gpio_interrupt", "pull": "none", "exti_trigger": "rising", "irq": True, "maximum_irq_priority": 5}},
            {"name": "time", "kind": "time", "mode": "shared"},
        ], ["device.gnss", "gnss.position", "gnss.velocity"], [{"order": 2, "physical_device_id": "PROJECT_PHYSICAL_DEVICE_ID_NEO_M9N", "class": "SYSTEM_DEVICE_CLASS_GNSS", "flags": primary_flags, "capability": "SYSTEM_CAPABILITY_GNSS", "rate": "SYSTEM_GNSS_NAVIGATION_RATE_HZ", "driver_hash": "0xC751E890UL", "name_hash": "0xA8E98337UL"}], ["docs/details/GNSS_NEO_M9N.md", "docs/details/GNSS_UBX.md"]),
        ("silverstar.device.telemetry.sx1281", "E28-2G4M12SX (SX1281)", "telemetry", "Devices/Telemetry/SX1281/module.mk", ["Devices/Telemetry/SX1281", "Middlewares/Third_Party/SX1280lib"], ["Devices/Telemetry/SX1281/Inc", "Middlewares/Third_Party/SX1280lib"], [
            {"name": "radio_bus", "kind": "spi", "binding_macro": "PROJECT_RESOURCE_RADIO_SPI", "constraints": {"spi": {"mode": "master", "cpol": "low", "cpha": "1edge", "data_bits": 8, "bit_order": "msb", "minimum_clock_hz": 100000, "maximum_clock_hz": 18000000, "dma": False, "irq": False}}},
            {"name": "radio_nss", "kind": "gpio_output", "binding_macro": "PROJECT_RESOURCE_RADIO_NSS", "electrical_constraints": {"mode": "gpio_output", "output_type": "push_pull", "pull": "none", "speed": "low", "safe_initial_level": "inactive", "active_polarity": "low", "startup_glitch_free": True}},
            {"name": "radio_reset", "kind": "gpio_output", "binding_macro": "PROJECT_RESOURCE_RADIO_RESET", "electrical_constraints": {"mode": "gpio_output", "output_type": "push_pull", "pull": "none", "speed": "low", "safe_initial_level": "inactive", "active_polarity": "low", "startup_glitch_free": True}},
            {"name": "radio_busy", "kind": "gpio_input", "binding_macro": "PROJECT_RESOURCE_RADIO_BUSY", "electrical_constraints": {"mode": "gpio_input", "pull": "none"}},
            {"name": "radio_dio1", "kind": "gpio_interrupt", "binding_macro": "PROJECT_RESOURCE_RADIO_DIO1", "electrical_constraints": {"mode": "gpio_interrupt", "pull": "none", "exti_trigger": "rising", "irq": True, "maximum_irq_priority": 5}},
            {"name": "time", "kind": "time", "mode": "shared"},
        ], ["device.telemetry", "transport.packet", "transport.lora", "transport.integrity.hardware_crc"], [{"order": 5, "physical_device_id": "PROJECT_PHYSICAL_DEVICE_ID_E28_SX1281", "class": "SYSTEM_DEVICE_CLASS_TELEMETRY", "flags": device_flags, "capability": "SYSTEM_CAPABILITY_TELEMETRY", "rate": "0U", "driver_hash": "0x3C6CF5BAUL", "name_hash": "0xC4A6E024UL"}], ["docs/details/SX1281_TRANSPORT.md"]),
        ("silverstar.device.console.uart", "Serial Maintenance Protocol 0.0", "console", "Devices/Console/UART/module.mk", ["Devices/Console/UART"], ["Devices/Console/UART/Inc"], [{"name": "console", "kind": "uart", "binding_macro": "PROJECT_RESOURCE_CONSOLE_UART", "constraints": {"uart": {"baud": {"exact": 230400, "configurable": False}, "word_length": 8, "parity": "none", "stop_bits": 1.0, "rx_dma": False, "tx_dma": False, "irq": True}}}], ["device.console", "maintenance.console", "transport.byte_stream"], [{"order": 6, "physical_device_id": "PROJECT_PHYSICAL_DEVICE_ID_CONSOLE", "class": "SYSTEM_DEVICE_CLASS_CONSOLE", "flags": device_flags, "capability": "SYSTEM_CAPABILITY_CONSOLE", "rate": "0U", "driver_hash": "0x92850855UL", "name_hash": "0xC8A9F404UL"}], ["docs/details/MAINTENANCE_PROTOCOL.md"]),
    )
    device_details = {
        "silverstar.device.imu.jy901b": {
            "display_names": {"zh_CN": "JY901B", "en_US": "JY901B"},
            "physical_device": {"vendor": "WitMotion", "model": "JY901B", "chipset": "JY901B", "driver": "JY901B Driver"},
            "description": "Reference JY901B Device driver and canonical adapter.",
        },
        "silverstar.device.gnss.neo_m9n": {
            "display_names": {"zh_CN": "NEO-M9N", "en_US": "NEO-M9N"},
            "physical_device": {"vendor": "u-blox", "model": "NEO-M9N", "chipset": "UBX-M9", "driver": "NEO-M9N Driver"},
            "description": "Reference NEO-M9N Device driver and canonical adapter.",
        },
        "silverstar.device.telemetry.sx1281": {
            "display_names": {"zh_CN": "E28-2G4M12SX（SX1281）", "en_US": "E28-2G4M12SX (SX1281)"},
            "physical_device": {"vendor": "Ebyte", "model": "E28-2G4M12SX", "chipset": "SX1281", "driver": "SX1281 Driver"},
            "description": "Reference SX1281 Device driver and canonical adapter.",
        },
        "silverstar.device.console.uart": {
            "display_names": {"zh_CN": "串口维护协议 0.0", "en_US": "Serial Maintenance Protocol 0.0"},
            "physical_device": {"vendor": "SilverStar", "model": "UART Maintenance Endpoint", "chipset": "STM32 UART", "driver": "UART Console Adapter"},
            "description": "Reference UART Console Device driver and canonical adapter.",
        },
    }
    for component_id, name, component_class, module, roots, includes, requirements, provides, descriptors, docs in device_specs:
        details = device_details[component_id]
        group_by_class = {
            "imu": ("primary_devices", 20),
            "gnss": ("primary_devices", 20),
            "telemetry": ("telemetry_links", 60),
            "console": ("maintenance_endpoints", 70),
        }
        device_group, device_group_order = group_by_class.get(
            component_class, ("other_sensors", 40)
        )
        device_metadata: dict[str, Any] = {
            "display_names": details["display_names"],
            "device_descriptors": descriptors,
            "device_group": device_group,
            "device_group_order": device_group_order,
            "device_selection_style": "instance",
        }
        facade_bindings: dict[str, dict[str, Any]] = {
            "silverstar.device.imu.jy901b": {
                "SYSTEM_DEVICE_CLASS_IMU": {"function_prefix": "SystemImu"},
                "SYSTEM_DEVICE_CLASS_BAROMETER": {
                    "function_prefix": "SystemBarometer"
                },
                "SYSTEM_DEVICE_CLASS_MAGNETOMETER": {
                    "function_prefix": "SystemMagnetometer"
                },
                "SYSTEM_DEVICE_CLASS_HARDWARE_QUATERNION": {
                    "function_prefix": "SystemHardwareQuaternion"
                },
            },
            "silverstar.device.gnss.neo_m9n": {
                "SYSTEM_DEVICE_CLASS_GNSS": {"function_prefix": "SystemGnss"}
            },
            "silverstar.device.telemetry.sx1281": {
                "SYSTEM_DEVICE_CLASS_TELEMETRY": {
                    "function_prefix": "SystemTelemetry"
                }
            },
        }.get(component_id, {})
        if facade_bindings:
            device_metadata["device_instance_bindings"] = facade_bindings
        if component_id == "silverstar.device.imu.jy901b":
            device_metadata.update(
                {
                    "capability_qualifications": {
                        "attitude.external.preflight_alignment_6axis_qualified": {
                            "evidence": "JY901B_QUATERNION_BUILD_PREFLIGHT_ALIGNMENT_6AXIS_QUALIFIED=1U"
                        },
                        "attitude.external.preflight_alignment_9axis_qualified": {
                            "evidence": "JY901B_QUATERNION_BUILD_PREFLIGHT_ALIGNMENT_9AXIS_QUALIFIED=1U"
                        },
                        "attitude.external.preflight_fallback_qualified": {
                            "evidence": "JY901B_QUATERNION_BUILD_PREFLIGHT_FALLBACK_QUALIFIED=1U"
                        },
                        "imu.software_alignment_qualified": {
                            "evidence": "JY901B_IMU_BUILD_SOFTWARE_ALIGNMENT_QUALIFIED=1U"
                        },
                        "imu.software_propagation_qualified": {
                            "evidence": "JY901B_IMU_BUILD_SOFTWARE_PROPAGATION_QUALIFIED=1U"
                        },
                        "imu.landing_stillness_qualified": {
                            "evidence": "Derived from the reference Stillness gate requiring selected acceleration and angular-rate data"
                        },
                        "barometer.landing_window_qualified": {
                            "evidence": "JY901B_BAROMETER_BUILD_LANDING_WINDOW_QUALIFIED=1U"
                        },
                    },
                    "unqualified_capabilities": {
                        "magnetometer.absolute_vector_qualified": "JY901B_MAGNETOMETER_BUILD_ABSOLUTE_VECTOR_QUALIFIED=0U",
                        "attitude.external.authoritative_6axis_qualified": "JY901B_QUATERNION_BUILD_AUTHORITATIVE_6AXIS_QUALIFIED=0U",
                        "attitude.external.authoritative_9axis_qualified": "JY901B_QUATERNION_BUILD_AUTHORITATIVE_9AXIS_QUALIFIED=0U",
                        "imu.landing_impact_qualified": "JY901B_IMU_BUILD_LANDING_IMPACT_QUALIFIED=0U",
                    },
                    "recordable_outputs": {
                        "imu.acceleration": {"enabled": True},
                        "imu.angular_rate": {"enabled": True},
                        "attitude.external": {"enabled": True},
                        "barometer.altitude": {"enabled": True},
                        "magnetometer.field": {
                            "enabled": False,
                            "reason_code": "logging.unavailable.magnetometer_output_disabled",
                        },
                    },
                }
            )
        elif component_id == "silverstar.device.gnss.neo_m9n":
            device_metadata["recordable_outputs"] = {
                "gnss.position": {"enabled": True},
                "gnss.velocity": {"enabled": True},
            }
        transports: list[dict[str, Any]] = []
        if component_id == "silverstar.device.telemetry.sx1281":
            transports = [{"capability": "transport.packet", "kind": "packet", "mtu": 255, "ordered": True, "bidirectional": True, "reliable": False, "mode": "datagram"}]
        elif component_id == "silverstar.device.console.uart":
            transports = [{"capability": "transport.byte_stream", "kind": "byte_stream", "mtu": 1, "ordered": True, "bidirectional": True, "reliable": True, "mode": "stream"}]
        components.append(
            _Component(
                component_id,
                name,
                "device",
                component_class,
                roots,
                description=details["description"],
                provenance=provenance,
                sources=_ManifestValues_Get(reference, module, "C_SOURCES"),
                includes=includes,
                dependencies=[core_id],
                resources_required=requirements,
                provides=provides,
                instance_policy={
                    "plugin_max": 1,
                    "class_max": (
                        4 if component_class in {"imu", "gnss", "telemetry"} else 1
                    ),
                    "same_plugin_multiple": False,
                    "multi_instance_ready": False,
                },
                physical_device=details["physical_device"],
                transports=transports,
                metadata=device_metadata,
                docs=(
                    docs
                    + [
                        "docs/details/IMU_INTERFACE.md",
                        "docs/details/HARDWARE_QUATERNION_INTERFACE.md",
                    ]
                    if component_id == "silverstar.device.imu.jy901b"
                    else docs
                ),
            )
        )

    logical_device_specs = (
        (
            "silverstar.device.sensor.input_voltage",
            "Input Voltage Monitor",
            "输入电压监测",
            "other_sensor",
            [
                {
                    "name": "input_voltage",
                    "kind": "adc",
                    "binding_macro": "PROJECT_RESOURCE_INPUT_VOLTAGE_ADC",
                    "display_names": {
                        "zh_CN": "输入电压监测",
                        "en_US": "Input Voltage Monitor",
                    },
                }
            ],
            ["power.voltage", "power.monitor"],
            {
                "device_category": "sensor",
                "device_group": "other_sensors",
                "device_group_order": 40,
                "device_selection_style": "toggle",
                "default_instance_id": "voltage_monitor0",
                "recordable_outputs": {"power.voltage": {"enabled": True}},
                "device_descriptors": [
                    {
                        "order": 7,
                        "physical_device_id": "PROJECT_PHYSICAL_DEVICE_ID_POWER_ADC",
                        "class": "SYSTEM_DEVICE_CLASS_POWER",
                        "flags": device_flags,
                        "capability": "SYSTEM_CAPABILITY_POWER",
                        "rate": "(uint32_t)(1000000ULL / SYSTEM_POWER_SAMPLE_PERIOD_US)",
                        "driver_hash": "0x7C755741UL",
                        "name_hash": "0xEF288B50UL",
                    }
                ],
            },
        ),
        (
            "silverstar.device.actuator.launch_ignition",
            "Launch Ignition Power Output",
            "起飞点火功率输出",
            "mission_action_actuator",
            [
                {
                    "name": "output",
                    "kind": "gpio_output",
                    "binding_macro": "PROJECT_RESOURCE_LAUNCH_IGNITION_OUTPUT",
                    "electrical_constraints": {
                        "mode": "gpio_output",
                        "output_type": "push_pull",
                        "pull": "none",
                        "speed": "low",
                        "safe_initial_level": "inactive",
                        "active_polarity": "high",
                        "startup_glitch_free": True,
                    },
                    "display_names": {
                        "zh_CN": "起飞点火功率输出",
                        "en_US": "Launch Ignition Power Output",
                    },
                }
            ],
            ["actuator.mission_action.launch_ignition"],
            {
                "device_category": "mission_action_actuator",
                "device_group": "actuators",
                "device_group_order": 50,
                "device_selection_style": "toggle",
                "independent_class_member": True,
                "default_instance_id": "launch_ignition0",
                "auto_select_when_required": False,
                "device_descriptors": [
                    {
                        "order": 10,
                        "physical_device_id": "PROJECT_PHYSICAL_DEVICE_ID_OUTPUT",
                        "class": "SYSTEM_DEVICE_CLASS_OUTPUT",
                        "flags": f"{device_flags} | SYSTEM_DESCRIPTOR_FLAG_REQUIRED | SYSTEM_DESCRIPTOR_FLAG_SHARED_PHYSICAL",
                        "capability": "SYSTEM_CAPABILITY_OUTPUT",
                        "rate": "0U",
                        "driver_hash": "0xA03101D4UL",
                        "name_hash": "0x30FDFAB9UL",
                    }
                ],
            },
        ),
        (
            "silverstar.device.actuator.parachute_pyro",
            "Parachute Pyro Power Output",
            "火工开伞功率输出",
            "mission_action_actuator",
            [
                {
                    "name": "output",
                    "kind": "gpio_output",
                    "binding_macro": "PROJECT_RESOURCE_PARACHUTE_PYRO_OUTPUT",
                    "electrical_constraints": {
                        "mode": "gpio_output",
                        "output_type": "push_pull",
                        "pull": "none",
                        "speed": "low",
                        "safe_initial_level": "inactive",
                        "active_polarity": "high",
                        "startup_glitch_free": True,
                    },
                    "display_names": {
                        "zh_CN": "火工开伞功率输出",
                        "en_US": "Parachute Pyro Power Output",
                    },
                }
            ],
            ["actuator.mission_action.parachute_deploy"],
            {
                "device_category": "mission_action_actuator",
                "device_group": "actuators",
                "device_group_order": 50,
                "device_selection_style": "toggle",
                "independent_class_member": True,
                "default_instance_id": "parachute_pyro0",
                "auto_select_when_required": False,
                "device_descriptors": [
                    {
                        "order": 11,
                        "physical_device_id": "PROJECT_PHYSICAL_DEVICE_ID_OUTPUT",
                        "class": "SYSTEM_DEVICE_CLASS_MISSION_ACTION",
                        "flags": f"{device_flags} | SYSTEM_DESCRIPTOR_FLAG_SHARED_PHYSICAL",
                        "capability": "SYSTEM_CAPABILITY_OUTPUT",
                        "rate": "0U",
                        "driver_hash": "0x8BC9C34EUL",
                        "name_hash": "0x3870C351UL",
                    }
                ],
            },
        ),
    )
    for (
        component_id,
        name,
        chinese_name,
        component_class,
        resources,
        provides,
        logical_metadata,
    ) in logical_device_specs:
        physical_devices = {
            "silverstar.device.sensor.input_voltage": {
                "vendor": "SilverStar",
                "model": "SS0.5 Input Voltage Monitor",
                "chipset": "SS0.5 ADC Input",
                "driver": "power_service",
            },
            "silverstar.device.actuator.launch_ignition": {
                "vendor": "SilverStar",
                "model": "SS0.5 P_CONTROL1",
                "chipset": "SS0.5 GPIO Output",
                "driver": "output_service",
            },
            "silverstar.device.actuator.parachute_pyro": {
                "vendor": "SilverStar",
                "model": "SS0.5 P_CONTROL2",
                "chipset": "SS0.5 GPIO Output",
                "driver": "output_service",
            },
        }
        components.append(
            _Component(
                component_id,
                name,
                "device",
                component_class,
                [],
                description=(
                    "Declarative logical device backed by the selected Board service; "
                    "it owns capability and physical-resource selection, not Board source."
                ),
                provenance=provenance,
                resources_required=resources,
                provides=provides,
                instance_policy={
                    "plugin_max": 1,
                    "class_max": 4 if component_class == "other_sensor" else 1,
                    "same_plugin_multiple": False,
                    "multi_instance_ready": False,
                },
                physical_device=physical_devices[component_id],
                metadata={
                    "declarative": True,
                    "logical_device": True,
                    "display_names": {"zh_CN": chinese_name, "en_US": name},
                    **(
                        {
                            "device_instance_bindings": {
                                "SYSTEM_DEVICE_CLASS_POWER": {
                                    "function_prefix": "SystemPower"
                                }
                            }
                        }
                        if component_id
                        == "silverstar.device.sensor.input_voltage"
                        else {}
                    ),
                    **logical_metadata,
                },
            )
        )

    indicator_specs = (
        (
            "silverstar.device.indicator.system_status",
            "System Status Indicator",
            "系统状态指示灯",
            "system_indicator0",
            "system",
            "PROJECT_RESOURCE_SYSTEM_INDICATOR",
            "SYSTEM_INDICATOR_SYSTEM_ENABLE",
            [],
            "SilverStar",
            "SS0.5 IMU_CAL_LED",
            "Active-low GPIO Indicator",
            "显示校准、系统就绪及任务阶段状态；SS0.5使用PA1上的IMU_CAL_LED，低电平点亮。",
            "Shows calibration, readiness, and mission state; SS0.5 uses the active-low IMU_CAL_LED on PA1.",
        ),
        (
            "silverstar.device.indicator.gnss_status",
            "GNSS Status Indicator",
            "GNSS状态指示灯",
            "gnss_indicator0",
            "gnss",
            "PROJECT_RESOURCE_GNSS_INDICATOR",
            "SYSTEM_INDICATOR_GNSS_ENABLE",
            [{"capability": "device.gnss", "purpose": "status_indication"}],
            "Generic",
            "External GNSS Status Indicator",
            "GPIO Indicator",
            "离线或无样本时熄灭，在线但不可导航时慢闪，可用于导航时常亮；需要独立GPIO输出。",
            "Off while offline or without a sample, slow blink while online but unusable, and solid while navigation-usable; requires an independent GPIO output.",
        ),
    )
    for (
        component_id,
        name,
        chinese_name,
        instance_id,
        indicator_role,
        binding_macro,
        enable_symbol,
        capabilities_required,
        vendor,
        model_name,
        chipset,
        chinese_description,
        english_description,
    ) in indicator_specs:
        components.append(
            _Component(
                component_id,
                name,
                "device",
                "indicator",
                [],
                description="Declarative software-controlled status indicator.",
                provenance=provenance,
                dependencies=[core_id],
                resources_required=[
                    {
                        "name": "output",
                        "kind": "gpio_output",
                        "binding_macro": binding_macro,
                        "electrical_constraints": {
                            "mode": "gpio_output",
                            "output_type": "push_pull",
                            "pull": "none",
                            "speed": "low",
                            "safe_initial_level": "inactive",
                            "active_polarity": "low",
                            "startup_glitch_free": True,
                        },
                        "display_names": {
                            "zh_CN": f"{chinese_name} · GPIO输出",
                            "en_US": f"{name} · GPIO Output",
                        },
                    }
                ],
                capabilities_required=capabilities_required,
                provides=[f"device.indicator.{indicator_role}_status"],
                instance_policy={
                    "plugin_max": 1,
                    "class_max": 1,
                    "same_plugin_multiple": False,
                    "multi_instance_ready": False,
                },
                physical_device={
                    "vendor": vendor,
                    "model": model_name,
                    "chipset": chipset,
                    "driver": "indicator_service",
                },
                metadata={
                    "declarative": True,
                    "logical_device": True,
                    "optional_device": indicator_role == "gnss",
                    "device_category": "indicator",
                    "device_group": "indicators",
                    "device_group_order": 45,
                    "device_selection_style": "toggle",
                    "default_instance_id": instance_id,
                    "indicator_role": indicator_role,
                    "indicator_enable_symbol": enable_symbol,
                    "display_names": {
                        "zh_CN": chinese_name,
                        "en_US": name,
                    },
                    "descriptions": {
                        "zh_CN": chinese_description,
                        "en_US": english_description,
                    },
                },
            )
        )

    components.append(
        _Component(
            "silverstar.algorithm.common",
            "Navigation Algorithm Common",
            "algorithm",
            "common",
            ["Algorithm/Common"],
            description="Shared MCU-independent attitude-frame and local-geodesy algorithms.",
            provenance=provenance,
            sources=_ManifestValues_Get(reference, "Algorithm/Common/module.mk", "C_SOURCES"),
            includes=["Algorithm/Common/Inc"],
            provides=["algorithm.common"],
            metadata={"display_names": {"zh_CN": "导航算法公共层", "en_US": "Navigation Algorithm Common"}},
            docs=["docs/details/NAVIGATION_AND_ESTIMATION.md"],
        )
    )
    components.append(
        _Component(
            "silverstar.algorithm.calibration",
            "IMU Calibration",
            "algorithm",
            "calibration",
            ["Algorithm/Calibration"],
            description="One-face and six-face calibration modes in one component.",
            provenance=provenance,
            sources=_ManifestValues_Get(reference, "Algorithm/Calibration/module.mk", "C_SOURCES"),
            includes=["Algorithm/Calibration/Inc"],
            provides=["algorithm.calibration"],
            capabilities_required=[
                {"capability": "imu.acceleration", "purpose": "calibration"},
                {"capability": "imu.angular_rate", "purpose": "calibration"},
            ],
            selection={"kind": "mode", "slot": "calibration", "required": True, "allow_none": False, "allow_multiple": True, "ui_order": 10, "options": ["Existing", "OneFace", "SixFace"], "default": ["Existing", "OneFace", "SixFace"], "labels": {"zh_CN": {"Existing": "使用现有校准", "OneFace": "单面校准", "SixFace": "六面校准"}, "en_US": {"Existing": "Use existing calibration", "OneFace": "One-face", "SixFace": "Six-face"}}},
            metadata={"display_names": {"zh_CN": "IMU 校准", "en_US": "IMU Calibration"}},
            docs=["docs/details/CALIBRATION.md"],
        )
    )
    alignment_common_id = "silverstar.algorithm.alignment.common"
    components.append(
        _Component(
            alignment_common_id,
            "Alignment Common",
            "algorithm",
            "alignment_common",
            ["Algorithm/Alignment/Common"],
            description="Shared alignment window, preflight and strategy contracts.",
            provenance=provenance,
            sources=_ManifestValues_Get(reference, "Algorithm/Alignment/Common/module.mk", "C_SOURCES"),
            includes=["Algorithm/Alignment/Common/Inc"],
            dependencies=["silverstar.algorithm.common"],
            provides=["algorithm.alignment_common"],
            metadata={"display_names": {"zh_CN": "初始对准公共层", "en_US": "Alignment Common"}},
            docs=["docs/details/NAVIGATION_AND_ESTIMATION.md"],
        )
    )
    alignment_specs = (
        ("gravity_known_yaw", "Gravity + Known Yaw", "GravityKnownYaw", ["SYSTEM_ALIGNMENT_BUILD_ALGORITHM=SYSTEM_ALIGNMENT_GRAVITY_KNOWN_YAW", "SYSTEM_ALIGNMENT_BUILD_SOURCE=SYSTEM_ALIGNMENT_ATTITUDE_SOURCE_GRAVITY_KNOWN_YAW", "SYSTEM_ALIGNMENT_BUILD_CAPABILITY_IMU=1U", "SYSTEM_ALIGNMENT_BUILD_CAPABILITY_MAGNETOMETER=0U", "SYSTEM_ALIGNMENT_BUILD_CAPABILITY_HARDWARE_QUATERNION=0U", "SYSTEM_ALIGNMENT_BUILD_GUARD_HARDWARE_QUATERNION=0U"], "重力 + 已知航向角"),
        ("gravity_mag_triad", "Gravity + Magnetic-Field Two-Vector Alignment", "GravityMagTriad", ["SYSTEM_ALIGNMENT_BUILD_ALGORITHM=SYSTEM_ALIGNMENT_GRAVITY_MAG_TRIAD", "SYSTEM_ALIGNMENT_BUILD_SOURCE=SYSTEM_ALIGNMENT_ATTITUDE_SOURCE_GRAVITY_MAG_TRIAD", "SYSTEM_ALIGNMENT_BUILD_CAPABILITY_IMU=1U", "SYSTEM_ALIGNMENT_BUILD_CAPABILITY_MAGNETOMETER=1U", "SYSTEM_ALIGNMENT_BUILD_CAPABILITY_HARDWARE_QUATERNION=0U", "SYSTEM_ALIGNMENT_BUILD_GUARD_HARDWARE_QUATERNION=0U"], "重力磁场双矢量对准"),
        ("hardware_quat_6axis_known_yaw", "6-Axis Hardware Quaternion + Known Yaw", "HardwareQuat6AxisKnownYaw", ["SYSTEM_ALIGNMENT_BUILD_ALGORITHM=SYSTEM_ALIGNMENT_HW_QUAT_6AXIS_KNOWN_YAW", "SYSTEM_ALIGNMENT_BUILD_SOURCE=SYSTEM_ALIGNMENT_ATTITUDE_SOURCE_HARDWARE_QUATERNION", "SYSTEM_ALIGNMENT_BUILD_CAPABILITY_IMU=0U", "SYSTEM_ALIGNMENT_BUILD_CAPABILITY_MAGNETOMETER=0U", "SYSTEM_ALIGNMENT_BUILD_CAPABILITY_HARDWARE_QUATERNION=1U", "SYSTEM_ALIGNMENT_BUILD_GUARD_HARDWARE_QUATERNION=1U"], "六轴硬件四元数 + 已知航向角"),
        ("hardware_quat_9axis", "9-Axis Hardware Quaternion Static Sampling", "HardwareQuat9Axis", ["SYSTEM_ALIGNMENT_BUILD_ALGORITHM=SYSTEM_ALIGNMENT_HW_QUAT_9AXIS", "SYSTEM_ALIGNMENT_BUILD_SOURCE=SYSTEM_ALIGNMENT_ATTITUDE_SOURCE_HARDWARE_QUATERNION", "SYSTEM_ALIGNMENT_BUILD_CAPABILITY_IMU=0U", "SYSTEM_ALIGNMENT_BUILD_CAPABILITY_MAGNETOMETER=0U", "SYSTEM_ALIGNMENT_BUILD_CAPABILITY_HARDWARE_QUATERNION=1U", "SYSTEM_ALIGNMENT_BUILD_GUARD_HARDWARE_QUATERNION=1U"], "九轴硬件四元数静态取样"),
    )
    alignment_capabilities = {
        "gravity_known_yaw": [
            {"capability": "imu.acceleration", "purpose": "initialization"},
            {"capability": "imu.angular_rate", "purpose": "initialization"},
            {"capability": "imu.software_alignment_qualified", "purpose": "initialization"},
        ],
        "gravity_mag_triad": [
            {"capability": "imu.acceleration", "purpose": "initialization"},
            {"capability": "imu.angular_rate", "purpose": "initialization"},
            {"capability": "imu.software_alignment_qualified", "purpose": "initialization"},
            {"capability": "magnetometer.field", "purpose": "initialization"},
            {"capability": "magnetometer.absolute_vector_qualified", "purpose": "initialization"},
        ],
        "hardware_quat_6axis_known_yaw": [
            {"capability": "attitude.external", "purpose": "initialization"},
            {"capability": "attitude.external.preflight_alignment_6axis_qualified", "purpose": "initialization"},
        ],
        "hardware_quat_9axis": [
            {"capability": "attitude.external", "purpose": "initialization"},
            {"capability": "attitude.external.preflight_alignment_9axis_qualified", "purpose": "initialization"},
        ],
    }
    for suffix, name, directory, defines, chinese_name in alignment_specs:
        components.append(
            _Component(
                f"silverstar.algorithm.alignment.{suffix}",
                name,
                "algorithm",
                "alignment",
                [f"Algorithm/Alignment/{directory}"],
                description=f"Build-selected {name} alignment strategy.",
                provenance=provenance,
                sources=_ManifestValues_Get(reference, f"Algorithm/Alignment/{directory}/module.mk", "C_SOURCES"),
                includes=[f"Algorithm/Alignment/{directory}/Inc"],
                defines=defines,
                dependencies=[alignment_common_id],
                provides=["algorithm.alignment"],
                capabilities_required=alignment_capabilities[suffix],
                selection={"kind": "strategy", "slot": "alignment", "required": True, "allow_none": False, "ui_order": 10},
                metadata={"display_names": {"zh_CN": chinese_name, "en_US": name}, "descriptions": {"zh_CN": f"构建时选择的{chinese_name}初始对准策略。", "en_US": f"Build-selected {name} alignment strategy."}, "algorithm_descriptors": [{"order": 1, "class": "SYSTEM_ALGORITHM_CLASS_ALIGNMENT", "algorithm": "SYSTEM_ALIGNMENT_ALGORITHM", "flags": primary_flags, "name_hash": "0x4B7BE479UL"}, {"order": 2, "class": "SYSTEM_ALGORITHM_CLASS_ATTITUDE", "algorithm": "SYSTEM_ATTITUDE_POLICY", "flags": primary_flags, "name_hash": "0xB6F9F6C7UL"}]},
                docs=[
                    "docs/details/NAVIGATION_AND_ESTIMATION.md",
                    "docs/details/CALIBRATION_AND_ALIGNMENT.md",
                    "docs/details/HARDWARE_QUATERNION_INTERFACE.md",
                ],
            )
        )
    components.append(
        _Component(
            "silverstar.algorithm.ins.coning2_sculling2", "Coning2 + Sculling2 INS", "algorithm", "ins", ["Algorithm/INS/Coning2Sculling2"],
            description="Build-selected Coning2 + Sculling2 inertial mechanization strategy.", provenance=provenance,
            sources=_ManifestValues_Get(reference, "Algorithm/INS/Coning2Sculling2/module.mk", "C_SOURCES"), includes=["Algorithm/INS/Coning2Sculling2/Inc"],
            defines=["SYSTEM_BUILD_MECHANIZATION_ALGORITHM=SYSTEM_MECHANIZATION_CONING2_SCULLING2"], dependencies=["silverstar.algorithm.common"], provides=["algorithm.mechanization", "attitude.estimated", "navigation.vertical_velocity"],
            capabilities_required=[{"capability": "imu.acceleration", "purpose": "runtime"}, {"capability": "imu.angular_rate", "purpose": "runtime"}],
            selection={"kind": "strategy", "slot": "ins", "required": True, "allow_none": False, "ui_order": 20},
            metadata={"display_names": {"zh_CN": "二阶锥运动补偿+二阶划桨效应补偿", "en_US": "Coning2 + Sculling2 INS"}, "descriptions": {"zh_CN": "构建时选择的二阶锥运动补偿+二阶划桨效应补偿惯性导航解算策略。", "en_US": "Build-selected Coning2 + Sculling2 inertial mechanization strategy."}, "algorithm_descriptors": [{"order": 3, "class": "SYSTEM_ALGORITHM_CLASS_MECHANIZATION", "algorithm": "SYSTEM_MECHANIZATION_ALGORITHM", "flags": primary_flags, "name_hash": "0x982C9707UL"}]}, docs=["docs/details/NAVIGATION_AND_ESTIMATION.md"],
        )
    )
    components.append(
        _Component(
            "silverstar.algorithm.estimator.kf6", "KF6 Navigation Estimator", "algorithm", "estimator", ["Algorithm/Estimator/KF6"],
            description="Optional build-selected KF6 fusion estimator.", provenance=provenance,
            sources=_ManifestValues_Get(reference, "Algorithm/Estimator/KF6/module.mk", "C_SOURCES"), includes=["Algorithm/Estimator/KF6/Inc"],
            defines=["SYSTEM_BUILD_FUSION_ALGORITHM=SYSTEM_FUSION_KF6", "SYSTEM_BUILD_ESTIMATOR_ENABLED=1U"], dependencies=["silverstar.algorithm.common"], provides=["algorithm.estimator"],
            capabilities_required=[{"capability": "gnss.position", "purpose": "measurement_update"}, {"capability": "gnss.velocity", "purpose": "measurement_update"}, {"capability": "barometer.altitude", "purpose": "measurement_update"}],
            selection={"kind": "strategy", "slot": "estimator", "required": False, "allow_none": True, "ui_order": 30, "none_defines": ["SYSTEM_BUILD_FUSION_ALGORITHM=SYSTEM_FUSION_NONE", "SYSTEM_BUILD_ESTIMATOR_ENABLED=0U"]},
            metadata={"display_names": {"zh_CN": "KF6 融合估计", "en_US": "KF6 Navigation Estimator"}, "descriptions": {"zh_CN": "可选的构建时 KF6 融合估计策略。", "en_US": "Optional build-selected KF6 fusion estimator."}, "algorithm_descriptors": [{"order": 4, "class": "SYSTEM_ALGORITHM_CLASS_FUSION", "algorithm": "SYSTEM_FUSION_ALGORITHM", "flags": primary_flags, "name_hash": "0x81C3E556UL"}]}, docs=["docs/details/NAVIGATION_AND_ESTIMATION.md"],
        )
    )

    components.append(
        _Component(
            "silverstar.flight_logic.cycle.reference", "SilverStar Flight Cycle", "flight_logic", "cycle", ["FlightLogic/FlightCycle"],
            description="Validated SilverStar lifecycle and recovery decision component.", provenance=provenance,
            sources=_ManifestValues_Get(reference, "FlightLogic/module.mk", "C_SOURCES"), dependencies=[core_id], capabilities_required=["flight_logic.deployment", "flight_logic.landing"], provides=["flight_logic.cycle"],
            metadata={"display_names": {"zh_CN": "SilverStar 飞行周期", "en_US": "SilverStar Flight Cycle"}}, docs=["docs/details/SYSTEM_LIFECYCLE.md"],
        )
    )
    components.append(
        _Component(
            "silverstar.flight_logic.deployment.multi_trigger", "Multi-Trigger Deployment", "flight_logic", "deployment", ["FlightLogic/Deployment/MultiTrigger"],
            description="Deployment component with independently selectable apogee, tilt and delay modes.", provenance=provenance,
            sources=_ManifestValues_Get(reference, "FlightLogic/Deployment/MultiTrigger/module.mk", "C_SOURCES"), includes=["FlightLogic/Deployment/MultiTrigger/Inc"], dependencies=[core_id], provides=["flight_logic.deployment"],
            selection={"kind": "mode", "slot": "deployment", "required": False, "allow_none": True, "allow_multiple": True, "ui_order": 20, "options": ["ApogeeVerticalVelocity", "Tilt", "Delay"], "default": ["ApogeeVerticalVelocity", "Tilt"], "option_requirements": {"ApogeeVerticalVelocity": {"capabilities": ["navigation.vertical_velocity", "actuator.mission_action.parachute_deploy"]}, "Tilt": {"capabilities": ["attitude.estimated", "imu.angular_rate", "imu.software_propagation_qualified", "actuator.mission_action.parachute_deploy"]}, "Delay": {"capabilities": ["actuator.mission_action.parachute_deploy"]}}, "parameters": {"ApogeeVerticalVelocity": [{"id": "vertical_velocity_threshold", "type": "float", "default": -2.0, "minimum": -100.0, "maximum": -0.01, "unit": "m/s", "generated_symbol": "SYSTEM_FLIGHT_APOGEE_VZ_THRESHOLD_MPS", "display_names": {"zh_CN": "垂直速度阈值", "en_US": "Vertical velocity threshold"}}], "Tilt": [{"id": "tilt_threshold", "type": "float", "default": 45.0, "minimum": 0.01, "maximum": 180.0, "unit": "°", "generated_symbol": "SYSTEM_FLIGHT_TILT_THRESHOLD_DEG", "display_names": {"zh_CN": "倾斜角阈值", "en_US": "Tilt angle threshold"}}], "Delay": [{"id": "delay", "type": "float", "default": 60.0, "minimum": 0.0, "maximum": 4294967.0, "unit": "s", "generated_symbol": "SYSTEM_FLIGHT_DEPLOY_DELAY_MS", "generated_scale": 1000.0, "display_names": {"zh_CN": "延时时间", "en_US": "Delay"}}]}, "option_symbols": {"ApogeeVerticalVelocity": "SYSTEM_DEPLOY_TRIGGER_APOGEE_VZ", "Tilt": "SYSTEM_DEPLOY_TRIGGER_TILT", "Delay": "SYSTEM_DEPLOY_TRIGGER_DELAY"}, "aggregate_symbol": "SYSTEM_FLIGHT_DEPLOY_TRIGGER_MASK", "labels": {"zh_CN": {"ApogeeVerticalVelocity": "越过最高点 / 垂直速度", "Tilt": "姿态倾斜", "Delay": "延时"}, "en_US": {"ApogeeVerticalVelocity": "Apogee / vertical velocity", "Tilt": "Tilt", "Delay": "Delay"}}},
            metadata={"display_names": {"zh_CN": "多条件开伞", "en_US": "Multi-Trigger Deployment"}}, docs=["docs/details/SYSTEM_LIFECYCLE.md"],
        )
    )
    components.append(
        _Component(
            "silverstar.flight_logic.landing.baro_imu_window", "Landing Detection Common", "flight_logic", "landing_common", ["FlightLogic/Landing/BarometerImuWindow"],
            description="Shared landing metrics, windows, and regression primitives used by build-selected landing strategies.", provenance=provenance,
            sources=_ManifestValues_Get(reference, "FlightLogic/Landing/BarometerImuWindow/module.mk", "C_SOURCES"), includes=["FlightLogic/Landing/BarometerImuWindow/Inc"], dependencies=[core_id], provides=["flight_logic.landing.common"],
            metadata={"display_names": {"zh_CN": "着陆判定公共实现", "en_US": "Landing Detection Common"}, "descriptions": {"zh_CN": "三种着陆策略共享的采样新鲜度、静止指标、冲击指标与气压回归实现。", "en_US": "Shared sample-freshness, stillness, impact, and barometer-regression primitives for all landing strategies."}}, docs=["docs/details/SYSTEM_LIFECYCLE.md"],
        )
    )
    landing_common_id = "silverstar.flight_logic.landing.baro_imu_window"
    landing_specs = (
        (
            "silverstar.flight_logic.landing.stillness",
            "Stillness Landing",
            "静止着陆判断",
            "Uses qualified acceleration and angular-rate stillness data for landing detection.",
            "使用具备静止着陆资格的加速度与角速度数据判断着陆。",
            "SYSTEM_BUILD_LANDING_MODE=SYSTEM_LANDING_MODE_STILLNESS",
            [
                {"capability": "imu.acceleration", "purpose": "landing_detection"},
                {"capability": "imu.angular_rate", "purpose": "landing_detection"},
                {"capability": "imu.landing_stillness_qualified", "purpose": "landing_detection"},
            ],
        ),
        (
            "silverstar.flight_logic.landing.impact_then_stillness",
            "Impact Then Stillness Landing",
            "冲击后静止着陆判断",
            "Detects a qualified landing impact and then confirms landing with a stillness window.",
            "先检测具备资格的着陆冲击，再以静止窗口确认着陆。",
            "SYSTEM_BUILD_LANDING_MODE=SYSTEM_LANDING_MODE_IMPACT_THEN_STILLNESS",
            [
                {"capability": "imu.acceleration", "purpose": "landing_detection"},
                {"capability": "imu.angular_rate", "purpose": "landing_detection"},
                {"capability": "imu.landing_stillness_qualified", "purpose": "landing_detection"},
                {"capability": "imu.landing_impact_qualified", "purpose": "landing_detection"},
            ],
        ),
        (
            "silverstar.flight_logic.landing.baro_imu_window_strategy",
            "Barometer + IMU Window Landing",
            "气压计 + IMU窗口着陆判断",
            "Uses qualified barometric-window and IMU-stillness data for landing detection.",
            "使用具备窗口判定资格的气压高度与IMU静止指标判断着陆。",
            "SYSTEM_BUILD_LANDING_MODE=SYSTEM_LANDING_MODE_BARO_IMU_WINDOW",
            [
                {"capability": "imu.acceleration", "purpose": "landing_detection"},
                {"capability": "imu.angular_rate", "purpose": "landing_detection"},
                {"capability": "imu.landing_stillness_qualified", "purpose": "landing_detection"},
                {"capability": "barometer.altitude", "purpose": "landing_detection"},
                {"capability": "barometer.landing_window_qualified", "purpose": "landing_detection"},
            ],
        ),
    )
    for component_id, name, chinese_name, description, chinese_description, define, requirements in landing_specs:
        components.append(
            _Component(
                component_id,
                name,
                "flight_logic",
                "landing",
                [],
                description=description,
                provenance=provenance,
                defines=[define],
                dependencies=[landing_common_id],
                provides=["flight_logic.landing"],
                capabilities_required=requirements,
                selection={"kind": "strategy", "slot": "landing", "required": True, "allow_none": False, "ui_order": 40},
                metadata={
                    "display_names": {"zh_CN": chinese_name, "en_US": name},
                    "descriptions": {"zh_CN": chinese_description, "en_US": description},
                    "implementation": "Compile-time selector for the shared reference recovery state machine; no duplicated strategy payload.",
                },
            )
        )
    components.append(
        _Component(
            "silverstar.os.freertos_11_3_0", "FreeRTOS Kernel 11.3.0", "os", "rtos", ["OS/FreeRTOS", "ThirdParty/FreeRTOS-Kernel/list.c", "ThirdParty/FreeRTOS-Kernel/queue.c", "ThirdParty/FreeRTOS-Kernel/tasks.c", "ThirdParty/FreeRTOS-Kernel/include", "ThirdParty/FreeRTOS-Kernel/portable/GCC/ARM_CM4F", "ThirdParty/FreeRTOS-Kernel/LICENSE.md", "ThirdParty/FreeRTOS-Kernel/README.md", "ThirdParty/FreeRTOS-Kernel/FreeRTOS-Kernel-V11.3.0-repository-SPDX2.3.spdx", "BuildSystem/freertos.mk", "Targets/SilverStar_F407/Inc/freertos_target_config.h", "Targets/SilverStar_F407/Src/freertos_target_irq.c"],
            description="Official FreeRTOS 11.3.0 static kernel subset and SilverStar hooks.", provenance=provenance,
            sources=os_sources, includes=["OS/FreeRTOS", "ThirdParty/FreeRTOS-Kernel/include", "ThirdParty/FreeRTOS-Kernel/portable/GCC/ARM_CM4F"], dependencies=[core_id, mcu_id], provides=["os.freertos", "os.static_allocation"],
            build_extra={"virtual_sources": ["ThirdParty/FreeRTOS-Kernel/list.c", "ThirdParty/FreeRTOS-Kernel/queue.c", "ThirdParty/FreeRTOS-Kernel/tasks.c"]}, metadata={"display_names": {"zh_CN": "FreeRTOS Kernel 11.3.0", "en_US": "FreeRTOS Kernel 11.3.0"}}, docs=["docs/details/BUILD_AND_TARGETS.md"], version="11.3.0",
        )
    )
    components.append(
        _Component(
            "silverstar.protocol.reference_v0", "SilverStar Protocol Bundle 0.0", "protocol_bundle", "reference_protocols", ["Protocol"],
            description="Complete AIR, SSLOG, Maintenance protocol sources and documentation.", provenance=provenance,
            sources=protocol_sources, includes=["Protocol/Inc", "Protocol/SSLOG/Inc"], dependencies=[core_id], provides=["protocol.air", "protocol.sslog", "protocol.maintenance"], metadata={"display_names": {"zh_CN": "SilverStar 协议包 0.0", "en_US": "SilverStar Protocol Bundle 0.0"}}, docs=["docs/details/AIR_PROTOCOL.md", "docs/details/STORAGE_AND_FLIGHT_LOG.md", "docs/details/MAINTENANCE_PROTOCOL.md"],
            protocol={
                "logging_metadata": "Protocol/SSLOG/schema/sslog_parser_metadata.json",
                "maintenance_protocol_version": "0.0",
                "firmware_version": "0.0.9",
                "documentation_version": "0.0.9",
                "profiles": {
                    "telemetry": [{
                        "id": "air.m0",
                        "version": "0.0",
                        "display_names": {"zh_CN": "AIR遥测协议 M0", "en_US": "AIR Telemetry Protocol M0"},
                        "service": "telemetry_service",
                        "slot": "telemetry_protocol",
                        "codec_sources": ["Protocol/Src/air_protocol.c"],
                        "parser_sources": ["Protocol/Src/air_protocol.c"],
                        "include_dirs": ["Protocol/Inc"],
                        "defines": [],
                        "binding": "telemetry_transport",
                        "transport": {
                            "capability": "transport.packet",
                            "kind": "packet",
                            "minimum_mtu": 50,
                            "ordered": True,
                            "bidirectional": True,
                            "reliable": False,
                            "mode": "datagram",
                        },
                        "decoder_metadata": "Protocol/metadata/air_m0.json",
                        "documentation": ["docs/AIR_PROTOCOL.md"],
                        "host_tests": ["Tests/Host/test_air_kf.c", "Tests/Host/test_telemetry.c"],
                        "golden_tests": ["Tests/Host/test_air_kf.c", "Tests/Host/test_telemetry.c"],
                    }],
                    "maintenance": [{
                        "id": "maintenance.serial.0_0",
                        "version": "0.0",
                        "display_names": {"zh_CN": "串口维护协议 0.0", "en_US": "Serial Maintenance Protocol 0.0"},
                        "service": "maintenance_service",
                        "slot": "maintenance_protocol",
                        "codec_sources": ["System/Src/system_console.c"],
                        "parser_sources": ["System/Src/system_console.c"],
                        "include_dirs": ["System/Inc", "Interfaces/Inc"],
                        "defines": [],
                        "binding": "maintenance_console",
                        "transport": {
                            "capability": "transport.byte_stream",
                            "kind": "byte_stream",
                            "minimum_mtu": 1,
                            "ordered": True,
                            "bidirectional": True,
                            "reliable": True,
                            "mode": "stream",
                        },
                        "decoder_metadata": "Protocol/metadata/maintenance_serial_0_0.json",
                        "documentation": ["docs/MAINTENANCE_PROTOCOL.md"],
                        "host_tests": ["Tests/Host/test_console.c"],
                        "golden_tests": ["Tests/Host/test_console.c"],
                    }],
                    "logging": [{
                        "id": "flight_log.0_0",
                        "version": "0.0",
                        "display_names": {"zh_CN": "飞行日志格式 0.0", "en_US": "Flight Log Format 0.0"},
                        "service": "flight_log_service",
                        "slot": "log_format",
                        "codec_sources": ["Protocol/SSLOG/Src/sslog_protocol.c", "Protocol/SSLOG/Src/sslog_records.c"],
                        "parser_sources": ["Protocol/SSLOG/Src/sslog_protocol.c"],
                        "include_dirs": ["Protocol/SSLOG/Inc"],
                        "defines": [],
                        "binding": "flight_log_sink",
                        "transport": {
                            "capability": "transport.sequential_file_sink",
                            "kind": "sequential_file_sink",
                            "minimum_mtu": 280,
                            "ordered": True,
                            "bidirectional": False,
                            "reliable": True,
                            "mode": "file",
                        },
                        "decoder_metadata": "Protocol/SSLOG/schema/sslog_parser_metadata.json",
                        "documentation": ["docs/STORAGE_AND_FLIGHT_LOG.md"],
                        "host_tests": ["Tests/Host/test_logger.c", "Tests/Host/test_device_native_log.c"],
                        "golden_tests": ["Tests/Host/test_logger.c"],
                    }],
                },
            },
        )
    )
    components.append(
        _Component(
            "silverstar.hardware_provider.stm32_cubemx", "STM32CubeMX Hardware Provider", "hardware_configuration_provider", "stm32_cubemx", [],
            description="Trusted FCCG provider for validating and importing generated STM32CubeMX projects as data.", provenance=provenance,
            provides=["hardware_provider.stm32_cubemx"], metadata={"display_names": {"zh_CN": "STM32CubeMX 硬件配置导入", "en_US": "STM32CubeMX Hardware Provider"}}, hardware_provider={"vendor": "STM32", "handler": "stm32_cubemx", "accepted_inputs": ["ioc", "directory"]}, docs=["docs/details/BUILD_AND_TARGETS.md"],
        )
    )
    components.append(
        _Component(
            "silverstar.environment.vscode_eide_gcc", "VS Code + EIDE + Arm GNU Toolchain", "development_environment", "vscode_eide_gcc", [],
            description="Native Make, VS Code and EIDE project environment resolved from one source graph.", provenance=provenance,
            provides=["environment.vscode", "environment.eide", "toolchain.arm_gnu"], metadata={"display_names": {"zh_CN": "VS Code + EIDE + Arm GNU 工具链", "en_US": "VS Code + EIDE + Arm GNU Toolchain"}},
            environment={"renderer": "vscode_eide_gcc", "toolchain": "arm-none-eabi-gcc", "outputs": ["Makefile", ".vscode/tasks.json", ".vscode/settings.json", ".vscode/extensions.json", ".eide/eide.yml", ".eide/files.options.yml", "SilverStar.code-workspace"], "tasks": ["build", "clean", "host_tests", "architecture_check", "power10_check", "static_analysis", "artifact_check"], "eide_native": True}, docs=["docs/details/BUILD_AND_TARGETS.md"],
        )
    )
    return components


def _Tree_Copy(policy: WorkspacePolicy, source: Path, destination: Path) -> None:
    if source.is_symlink():
        raise RuntimeError(f"Reference symlink is not accepted: {source}")
    if source.is_file():
        policy.File_Copy(source, destination)
        return
    if not source.is_dir():
        raise FileNotFoundError(source)
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise RuntimeError(f"Reference symlink is not accepted: {path}")
        if path.is_file():
            policy.File_Copy(path, destination / path.relative_to(source))


def _ArchitectureChecker_Adapt(path: Path, policy: WorkspacePolicy) -> None:
    text = path.read_text(encoding="utf-8")
    changed = False

    documentation_marker = "$fccgMaintenanceDocumentationPath"
    if documentation_marker not in text:
        legacy_documentation_check = """Assert-FileContainsPattern `
    -RelativePath 'docs\\details\\MAINTENANCE_PROTOCOL.md' `
    -Pattern '<CAPABILITY_MODULE>\\s+<INSTANCE>\\s+<COMMAND>' `
    -Message 'Maintenance documentation does not define indexed capability syntax.'
Assert-NoArchitecturePattern -Name `
    'Maintenance documentation addresses a physical device model as a module.' `
    -Paths @('docs\\details\\MAINTENANCE_PROTOCOL.md') `
    -Extensions @('.md') `
    -Pattern '(?i)\\b(?:JY901B|NEO[_-]?M9N|E28[^\\s]*)\\s+[0-9]+\\s+STATUS\\b'
"""
        generated_documentation_check = """$fccgMaintenanceDocumentationPath = Join-Path $repoRoot `
    'docs\\details\\MAINTENANCE_PROTOCOL.md'
if (Test-Path -LiteralPath $fccgMaintenanceDocumentationPath -PathType Leaf) {
    Assert-FileContainsPattern `
        -RelativePath 'docs\\details\\MAINTENANCE_PROTOCOL.md' `
        -Pattern '<CAPABILITY_MODULE>\\s+<INSTANCE>\\s+<COMMAND>' `
        -Message 'Maintenance documentation does not define indexed capability syntax.'
    Assert-NoArchitecturePattern -Name `
        'Maintenance documentation addresses a physical device model as a module.' `
        -Paths @('docs\\details\\MAINTENANCE_PROTOCOL.md') `
        -Extensions @('.md') `
        -Pattern '(?i)\\b(?:JY901B|NEO[_-]?M9N|E28[^\\s]*)\\s+[0-9]+\\s+STATUS\\b'
}
else {
    Write-Output ('FCCG architecture note: generated source omits installed-plugin ' +
        'documentation; maintenance Markdown was audited during reference import.')
}
"""
        if legacy_documentation_check not in text:
            raise RuntimeError(
                "Reference architecture checker maintenance-document check changed"
            )
        text = text.replace(
            legacy_documentation_check,
            generated_documentation_check,
            1,
        )
        changed = True

    required_generated_files = (
        "Generated\\Inc\\project_capability_routes.h",
        "Generated\\Src\\project_capability_routes.c",
        "Generated\\Inc\\project_flight_config.h",
        "Generated\\project_sources.mk",
    )
    missing_generated_files = tuple(
        relative
        for relative in required_generated_files
        if f"'{relative}'" not in text
    )
    if missing_generated_files:
        needle = "    'Generated\\module.mk'"
        if needle not in text:
            raise RuntimeError("Reference architecture checker Generated allowlist changed")
        insertion = "".join(
            f"    '{relative}',\n" for relative in missing_generated_files
        )
        replacement = insertion + needle
        text = text.replace(needle, replacement, 1)
        changed = True

    source_graph_marker = "$fccgResolvedSourceGraph"
    if source_graph_marker not in text:
        none_start = (
            "    $noneOutput = @(& mingw32-make -s TARGET_PROFILE=SilverStar_F407 `\n"
        )
        selected_start = "    $selectedAssemblySources = @($makeOutput | Where-Object {"
        start_index = text.find(none_start)
        selected_index = text.find(selected_start, start_index)
        if start_index < 0 or selected_index < 0:
            raise RuntimeError("Reference architecture checker Estimator=None check changed")
        legacy_block = text[start_index:selected_index]
        indented_block = "".join(
            ("    " + line if line.strip() else line)
            for line in legacy_block.splitlines(keepends=True)
        )
        replacement = (
            "    # FCCG resolves strategies before rendering one immutable source graph.\n"
            "    $fccgResolvedSourceGraph = Test-Path -LiteralPath "
            "(Join-Path $repoRoot 'Generated\\project_sources.mk')\n"
            "    if (-not $fccgResolvedSourceGraph) {\n"
            f"{indented_block}"
            "    }\n\n"
        )
        text = text[:start_index] + replacement + text[selected_index:]
        changed = True

    estimator_source_marker = "$selectedEstimatorTaskSources"
    if estimator_source_marker not in text:
        kf_requirement = (
            "        'Algorithm/Estimator/KF6/Src/navigation_kf.c',\n"
        )
        missing_sources_start = (
            "    $missingStrategySources = @($requiredStrategySources | Where-Object {"
        )
        if kf_requirement not in text or missing_sources_start not in text:
            raise RuntimeError(
                "Reference architecture checker estimator source check changed"
            )
        estimator_check = (
            "    $selectedEstimatorTaskSources = @($uniqueSources | Where-Object {\n"
            "        $_ -eq 'APP/Src/estimator_task.c'\n"
            "    })\n"
            "    Assert-ArchitectureCondition `\n"
            "        -Condition ($selectedEstimatorTaskSources.Count -eq 1) `\n"
            "        -Message (\"Expected the unified estimator task facade: \" +\n"
            "            ($selectedEstimatorTaskSources -join ', '))\n"
            "    $selectedKfSources = @($uniqueSources | Where-Object {\n"
            "        $_ -like 'Algorithm/Estimator/KF6/*'\n"
            "    })\n"
            "    if ($selectedKfSources.Count -gt 0) {\n"
            "        $requiredStrategySources += "
            "'Algorithm/Estimator/KF6/Src/navigation_kf.c'\n"
            "    }\n"
        )
        text = text.replace(kf_requirement, "", 1)
        text = text.replace(
            missing_sources_start,
            estimator_check + missing_sources_start,
            1,
        )
        changed = True

    legacy_eide_flags = (
        "(?m)^\\s+C_FLAGS:\\s*-include "
        "Targets/SilverStar_F407/Inc/platform_memory_target\\.h\\s*$"
    )
    flight_eide_flags = (
        "(?m)^\\s+C_FLAGS:\\s*-include "
        "Targets/SilverStar_F407/Inc/platform_memory_target\\.h "
        "-include Generated/Inc/project_flight_config\\.h\\s*$"
    )
    if flight_eide_flags not in text:
        if legacy_eide_flags not in text:
            raise RuntimeError("Reference architecture checker EIDE flags changed")
        text = text.replace(legacy_eide_flags, flight_eide_flags, 1)
        text = text.replace(
            "EIDE does not force-include the target memory policy.",
            "EIDE does not force-include the target memory and flight "
            "configuration policies.",
            1,
        )
        changed = True

    build_root_legacy = (
        "BUILD_ROOT\\s*:=\\s*build/\\$\\(TARGET_PROFILE\\)/\\$\\(CONFIG\\)"
    )
    build_root_current = (
        "BUILD_ROOT\\s*:=\\s*build/FCCG/\\$\\(TARGET_PROFILE\\)/"
        "\\$\\(CONFIG\\)"
    )
    if build_root_legacy in text:
        text = text.replace(build_root_legacy, build_root_current, 1)
        changed = True
    elif build_root_current not in text:
        raise RuntimeError("Reference architecture checker build-root check changed")

    eide_root_legacy = "outDir:\\s*build\\\\EIDE\\\\SilverStar_F407"
    eide_root_current = (
        "outDir:\\s*build\\\\FCCG\\\\SilverStar_F407\\\\EIDE"
    )
    if eide_root_legacy in text:
        text = text.replace(eide_root_legacy, eide_root_current, 1)
        text = text.replace(
            "build\\EIDE\\SilverStar_F407",
            "build\\FCCG\\SilverStar_F407\\EIDE",
        )
        changed = True
    elif eide_root_current not in text:
        raise RuntimeError("Reference architecture checker EIDE-root check changed")

    # Windows PowerShell 5 interprets UTF-8 JSON without a BOM through the
    # active ANSI code page unless the encoding is explicit.  The SSLOG
    # metadata contains localized display names, so mojibake can otherwise
    # turn valid JSON into an apparent ConvertFrom-Json syntax error.
    utf8_json_reads = (
        (
            "Get-Content -Raw -LiteralPath $sslogSchemaPath |",
            "Get-Content -Raw -Encoding UTF8 -LiteralPath $sslogSchemaPath |",
        ),
        (
            "Get-Content -Raw -LiteralPath (Join-Path $repoRoot `\n"
            "        'Protocol\\SSLOG\\schema\\sslog_parser_metadata.json') |",
            "Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $repoRoot `\n"
            "        'Protocol\\SSLOG\\schema\\sslog_parser_metadata.json') |",
        ),
    )
    for legacy_read, utf8_read in utf8_json_reads:
        if utf8_read in text:
            continue
        if legacy_read not in text:
            raise RuntimeError("Reference architecture checker SSLOG JSON read changed")
        text = text.replace(legacy_read, utf8_read, 1)
        changed = True

    if "FCCG_PROGRESS|ARCHITECTURE|PLAN|6" not in text:
        progress_replacements = (
            (
                "$script:failures = New-Object 'System.Collections.Generic.List[string]'\n",
                "$script:failures = New-Object 'System.Collections.Generic.List[string]'\n"
                "Write-Output 'FCCG_PROGRESS|ARCHITECTURE|PLAN|6'\n"
                "Write-Output 'FCCG_PROGRESS|ARCHITECTURE|BEGIN|1|6|source_graph'\n",
            ),
            (
                "$legacyPaths = @(\n",
                "Write-Output 'FCCG_PROGRESS|ARCHITECTURE|DONE|1|6|source_graph'\n"
                "Write-Output 'FCCG_PROGRESS|ARCHITECTURE|BEGIN|2|6|directory_boundaries'\n"
                "$legacyPaths = @(\n",
            ),
            (
                "Assert-FileContainsPattern -RelativePath 'Makefile' `\n",
                "Write-Output 'FCCG_PROGRESS|ARCHITECTURE|DONE|2|6|directory_boundaries'\n"
                "Write-Output 'FCCG_PROGRESS|ARCHITECTURE|BEGIN|3|6|eide_consistency'\n"
                "Assert-FileContainsPattern -RelativePath 'Makefile' `\n",
            ),
            (
                "Assert-FileContainsPattern -RelativePath 'ThirdParty\\FreeRTOS-Kernel\\include\\task.h' `\n",
                "Write-Output 'FCCG_PROGRESS|ARCHITECTURE|DONE|3|6|eide_consistency'\n"
                "Write-Output 'FCCG_PROGRESS|ARCHITECTURE|BEGIN|4|6|freertos'\n"
                "Assert-FileContainsPattern -RelativePath 'ThirdParty\\FreeRTOS-Kernel\\include\\task.h' `\n",
            ),
            (
                "Assert-FileContainsPattern -RelativePath 'System\\User\\system_user_config.h' `\n",
                "Write-Output 'FCCG_PROGRESS|ARCHITECTURE|DONE|4|6|freertos'\n"
                "Write-Output 'FCCG_PROGRESS|ARCHITECTURE|BEGIN|5|6|protocol'\n"
                "Assert-FileContainsPattern -RelativePath 'System\\User\\system_user_config.h' `\n",
            ),
            (
                "if ($script:failures.Count -ne 0) {\n",
                "Write-Output 'FCCG_PROGRESS|ARCHITECTURE|DONE|5|6|protocol'\n"
                "Write-Output 'FCCG_PROGRESS|ARCHITECTURE|BEGIN|6|6|summary'\n"
                "if ($script:failures.Count -ne 0) {\n",
            ),
        )
        for needle, replacement in progress_replacements:
            if needle not in text:
                raise RuntimeError(
                    "Reference architecture checker progress anchor changed: "
                    + needle.splitlines()[0]
                )
            text = text.replace(needle, replacement, 1)
        text = text.rstrip() + (
            "\nWrite-Output 'FCCG_PROGRESS|ARCHITECTURE|DONE|6|6|summary'\n"
        )
        changed = True

    if changed:
        policy.Text_AtomicWrite(path, text)


def _PowerShellFunction_Adapt(
    text: str,
    function_name: str,
    replacements: tuple[tuple[str, str], ...],
) -> str:
    start = text.find(f"function {function_name} {{")
    if start < 0:
        raise RuntimeError(f"Reference host function is missing: {function_name}")
    end = text.find("\nfunction ", start + 1)
    if end < 0:
        end = text.find("\nInitialize-HostCompiler", start + 1)
    if end < 0:
        raise RuntimeError(f"Reference host function boundary changed: {function_name}")
    block = text[start:end]
    for needle, replacement in replacements:
        if needle not in block:
            raise RuntimeError(
                f"Reference host function progress anchor changed: {function_name}: "
                + needle.splitlines()[0]
            )
        block = block.replace(needle, replacement, 1)
    return text[:start] + block + text[end:]


def _HostTestProgress_Adapt(text: str) -> str:
    if "FCCG_PROGRESS|$taskKind|PLAN|$total" in text:
        return text
    variables = "$script:expectedCompileFailureCount = 0\n"
    if variables not in text:
        raise RuntimeError("Reference host progress counter contract changed")
    text = text.replace(
        variables,
        variables
        + "$script:collectHostJobs = $true\n"
        + "$script:hostJobs = [System.Collections.Generic.List[object]]::new()\n"
        + "$script:progressCompleted = @{}\n"
        + "$script:progressTotals = @{}\n",
        1,
    )
    output_marker = "$silverstarAssertSource = \"$repoRoot\\Common\\Src\\silverstar_assert.c\"\n"
    if output_marker not in text:
        raise RuntimeError("Reference host detail-log anchor changed")
    text = text.replace(
        output_marker,
        output_marker
        + "$detailLogPath = Join-Path $outputDir 'host-tests-detail.log'\n"
        + "if (Test-Path -LiteralPath $detailLogPath) {\n"
        + "    Remove-Item -LiteralPath $detailLogPath -Force\n"
        + "}\n",
        1,
    )
    function_anchor = "function Invoke-HostTest {\n"
    if function_anchor not in text:
        raise RuntimeError("Reference host test function anchor changed")
    progress_functions = r'''function Write-FccgProgressBegin {
    param(
        [Parameter(Mandatory = $true)][string]$Task,
        [Parameter(Mandatory = $true)][string]$Subject
    )

    $current = [int]$script:progressCompleted[$Task] + 1
    $total = [int]$script:progressTotals[$Task]
    Write-Output "FCCG_PROGRESS|$Task|BEGIN|$current|$total|$Subject"
}

function Write-FccgProgressDone {
    param(
        [Parameter(Mandatory = $true)][string]$Task,
        [Parameter(Mandatory = $true)][string]$Subject
    )

    $script:progressCompleted[$Task] = `
        [int]$script:progressCompleted[$Task] + 1
    $current = [int]$script:progressCompleted[$Task]
    $total = [int]$script:progressTotals[$Task]
    Write-Output "FCCG_PROGRESS|$Task|DONE|$current|$total|$Subject"
}

function Write-HostTestDetail {
    param([Parameter(Mandatory = $true)][string]$Text)

    [System.IO.File]::AppendAllText(
        $detailLogPath,
        $Text + [Environment]::NewLine,
        [System.Text.UTF8Encoding]::new($false)
    )
    Write-Output "FCCG_DETAIL|$Text"
}

'''
    text = text.replace(function_anchor, progress_functions + function_anchor, 1)

    parameter_end = "        [string[]]$ExtraCompilerArgs = @()\n    )\n\n"
    text = _PowerShellFunction_Adapt(
        text,
        "Invoke-HostTest",
        (
            (
                parameter_end,
                parameter_end
                + "    if ($script:collectHostJobs) {\n"
                + "        $script:hostJobs.Add([pscustomobject]@{\n"
                + "            Kind = 'HOST_TEST'\n"
                + "            Name = $Name\n"
                + "            Sources = @($Sources)\n"
                + "            ExtraCompilerArgs = @($ExtraCompilerArgs)\n"
                + "        })\n"
                + "        return\n"
                + "    }\n\n"
                + "    Write-FccgProgressBegin -Task 'HOST_TEST' -Subject $Name\n\n",
            ),
            (
                "    $script:hostExecutableCount++\n",
                "    $script:hostExecutableCount++\n"
                + "    Write-FccgProgressDone -Task 'HOST_TEST' -Subject $Name\n",
            ),
        ),
    )
    expected_failure_completion_legacy = (
        "    $script:expectedCompileFailureCount++\n"
        "    Write-Output \"Expected host compile failure passed: $Name\"\n"
    )
    expected_failure_completion_current = (
        "    $diagnosticLine = $compileResult.Output | Where-Object {\n"
        "        ([string]$_) -match '(?i)(fatal error:|error:|#error)'\n"
        "    } | Select-Object -First 1\n"
        "    if ($null -eq $diagnosticLine) {\n"
        "        Write-HostCompileDiagnostic -Name $Name -CompilerArgs $compilerArgs `\n"
        "            -ExitCode $compileResult.ExitCode -CompilerOutput $compileResult.Output\n"
        "        throw \"Expected host compile failure had no GCC diagnostic: $Name\"\n"
        "    }\n"
        "    $script:expectedCompileFailureCount++\n"
        "    Write-Output ((\"Expected host compile failure passed: {0} \" +\n"
        "        \"compiler={1} target={2} diagnostic={3}\") -f $Name,\n"
        "        $script:hostCompilerPath, $script:hostCompilerTarget,\n"
        "        ([string]$diagnosticLine).Trim())\n"
    )
    if expected_failure_completion_legacy in text:
        expected_failure_completion = expected_failure_completion_legacy
    elif expected_failure_completion_current in text:
        expected_failure_completion = expected_failure_completion_current
    else:
        raise RuntimeError(
            "Reference expected-compile-failure completion contract changed"
        )
    text = _PowerShellFunction_Adapt(
        text,
        "Invoke-ExpectedCompileFailure",
        (
            (
                parameter_end,
                parameter_end
                + "    if ($script:collectHostJobs) {\n"
                + "        $script:hostJobs.Add([pscustomobject]@{\n"
                + "            Kind = 'HOST_EXPECTED_FAILURE'\n"
                + "            Name = $Name\n"
                + "            Source = $Source\n"
                + "            ExtraCompilerArgs = @($ExtraCompilerArgs)\n"
                + "        })\n"
                + "        return\n"
                + "    }\n\n"
                + "    Write-FccgProgressBegin -Task 'HOST_EXPECTED_FAILURE' -Subject $Name\n\n",
            ),
            (
                expected_failure_completion,
                "    $diagnosticLine = $compileResult.Output | Where-Object {\n"
                "        ([string]$_) -match '(?i)(static assertion failed|#error)'\n"
                "    } | Select-Object -First 1\n"
                "    if ($null -eq $diagnosticLine) {\n"
                "        Write-HostCompileDiagnostic -Name $Name -CompilerArgs $compilerArgs `\n"
                "            -ExitCode $compileResult.ExitCode -CompilerOutput $compileResult.Output\n"
                "        throw \"Expected host compile failure did not match a configuration gate: $Name\"\n"
                "    }\n"
                "    $script:expectedCompileFailureCount++\n"
                "    Write-Output \"FCCG_EXPECTED_REJECTION|$Name\"\n"
                "    Write-HostTestDetail -Text (\"Expected compile rejection: {0}\" -f $Name)\n"
                "    Write-HostTestDetail -Text (\"Compiler: {0}\" -f $script:hostCompilerPath)\n"
                "    Write-HostTestDetail -Text (\"Target: {0}\" -f $script:hostCompilerTarget)\n"
                "    foreach ($diagnostic in $compileResult.Output) {\n"
                "        Write-HostTestDetail -Text ([string]$diagnostic)\n"
                "    }\n"
                "    Write-FccgProgressDone -Task 'HOST_EXPECTED_FAILURE' -Subject $Name\n",
            ),
        ),
    )
    text = _PowerShellFunction_Adapt(
        text,
        "Invoke-ExpectedCompileSuccess",
        (
            (
                parameter_end,
                parameter_end
                + "    if ($script:collectHostJobs) {\n"
                + "        $script:hostJobs.Add([pscustomobject]@{\n"
                + "            Kind = 'HOST_COMPILE_PASS'\n"
                + "            Name = $Name\n"
                + "            Source = $Source\n"
                + "            ExtraCompilerArgs = @($ExtraCompilerArgs)\n"
                + "        })\n"
                + "        return\n"
                + "    }\n\n"
                + "    Write-FccgProgressBegin -Task 'HOST_COMPILE_PASS' -Subject $Name\n\n",
            ),
            (
                "    Write-Output \"Expected host compile success passed: $Name\"\n",
                "    Write-Output \"Expected host compile success passed: $Name\"\n"
                + "    Write-FccgProgressDone -Task 'HOST_COMPILE_PASS' -Subject $Name\n",
            ),
        ),
    )
    replay_anchor = "$alignmentRuntimeFiles = @(\n"
    if replay_anchor not in text:
        raise RuntimeError("Reference host test replay anchor changed")
    replay = r'''$script:collectHostJobs = $false
$plannedJobs = @($script:hostJobs | Where-Object {
    (($_.Kind -eq 'HOST_TEST') -and
        (@($_.Sources | Where-Object { -not (Test-Path -LiteralPath $_) }).Count -eq 0)) -or
    (($_.Kind -ne 'HOST_TEST') -and (Test-Path -LiteralPath $_.Source))
})
foreach ($taskKind in @(
    'HOST_TEST',
    'HOST_COMPILE_PASS',
    'HOST_EXPECTED_FAILURE'
)) {
    $total = @($plannedJobs | Where-Object { $_.Kind -eq $taskKind }).Count
    $script:progressCompleted[$taskKind] = 0
    $script:progressTotals[$taskKind] = $total
    if ($total -gt 0) {
        Write-Output "FCCG_PROGRESS|$taskKind|PLAN|$total"
    }
}
foreach ($skippedJob in @($script:hostJobs | Where-Object {
    ($_.Kind -eq 'HOST_TEST') -and
    (@($_.Sources | Where-Object { -not (Test-Path -LiteralPath $_) }).Count -ne 0)
})) {
    Write-Output ("Skipped host test {0}: unselected component sources" -f `
        $skippedJob.Name)
}
foreach ($job in $plannedJobs) {
    switch ($job.Kind) {
        'HOST_TEST' {
            Invoke-HostTest -Name $job.Name -Sources $job.Sources `
                -ExtraCompilerArgs $job.ExtraCompilerArgs
        }
        'HOST_COMPILE_PASS' {
            Invoke-ExpectedCompileSuccess -Name $job.Name `
                -Source $job.Source `
                -ExtraCompilerArgs $job.ExtraCompilerArgs
        }
        'HOST_EXPECTED_FAILURE' {
            Invoke-ExpectedCompileFailure -Name $job.Name `
                -Source $job.Source `
                -ExtraCompilerArgs $job.ExtraCompilerArgs
        }
    }
}

'''
    return text.replace(replay_anchor, replay + replay_anchor, 1)


def _HostTestRunner_Adapt(path: Path, policy: WorkspacePolicy) -> None:
    text = path.read_text(encoding="utf-8")
    legacy_output = "$outputDir = Join-Path $repoRoot 'build\\Host\\Tests'"
    current_output = "$outputDir = Join-Path $repoRoot 'build\\FCCG\\Host\\Tests'"
    if legacy_output in text:
        text = text.replace(legacy_output, current_output, 1)
    elif current_output not in text:
        raise RuntimeError("Reference host test output directory contract changed")
    marker = "$fccgMissingSources"
    if marker not in text:
        needle = "    $executable = Join-Path $outputDir ($Name + '.exe')"
        if needle not in text:
            raise RuntimeError("Reference host test runner Invoke-HostTest changed")
        replacement = (
            "    # A generated FCCG project contains only its selected component payloads.\n"
            "    $fccgMissingSources = @($Sources | Where-Object {\n"
            "        -not (Test-Path -LiteralPath $_)\n"
            "    })\n"
            "    if ($fccgMissingSources.Count -ne 0) {\n"
            "        Write-Output (\"Skipped host test {0}: unselected component sources {1}\" "
            "-f $Name, ($fccgMissingSources -join ', '))\n"
            "        return\n"
            "    }\n\n"
            f"{needle}"
        )
        text = text.replace(needle, replacement, 1)
    if "Host compiler return code:" not in text:
        parameter = (
            "        [Parameter(Mandatory = $true)][string[]]$CompilerArgs,\n"
            "        [object[]]$CompilerOutput = @()"
        )
        if parameter not in text:
            raise RuntimeError("Reference host diagnostic parameter contract changed")
        text = text.replace(
            parameter,
            "        [Parameter(Mandatory = $true)][string[]]$CompilerArgs,\n"
            "        [Parameter(Mandatory = $true)][int]$ExitCode,\n"
            "        [object[]]$CompilerOutput = @()",
            1,
        )
        target_line = (
            '    Write-Output "Host compiler target: '
            '$($script:hostCompilerTarget)"'
        )
        if target_line not in text:
            raise RuntimeError("Reference host diagnostic output contract changed")
        text = text.replace(
            target_line,
            target_line + '\n    Write-Output "Host compiler return code: $ExitCode"',
            1,
        )
        call = "            -CompilerOutput $compileResult.Output"
        if call not in text:
            raise RuntimeError("Reference host diagnostic call contract changed")
        text = text.replace(
            call,
            "            -ExitCode $compileResult.ExitCode "
            "-CompilerOutput $compileResult.Output",
        )
    runtime_marker = "Host compiler runtime directory:"
    if runtime_marker not in text:
        compiler_path_assignment = (
            "    $script:hostCompilerPath = $compilerCommand.Path\n"
        )
        if compiler_path_assignment not in text:
            raise RuntimeError("Reference Host compiler initialization changed")
        runtime_isolation = r'''    $script:hostCompilerPath = $compilerCommand.Path
    $hostCompilerDirectory = Split-Path -Parent $script:hostCompilerPath
    Write-Output "Host compiler runtime directory: $hostCompilerDirectory"
    $env:PATH = $hostCompilerDirectory + [System.IO.Path]::PathSeparator + `
        $env:PATH
    foreach ($variableName in @(
        'GCC_EXEC_PREFIX',
        'COMPILER_PATH',
        'CPATH',
        'C_INCLUDE_PATH',
        'CPLUS_INCLUDE_PATH',
        'OBJC_INCLUDE_PATH',
        'LIBRARY_PATH',
        'DEPENDENCIES_OUTPUT',
        'SUNPRO_DEPENDENCIES'
    )) {
        $environmentPath = "Env:$variableName"
        if (Test-Path -LiteralPath $environmentPath) {
            Remove-Item -LiteralPath $environmentPath -Force
        }
    }
'''
        text = text.replace(
            compiler_path_assignment,
            runtime_isolation,
            1,
        )
    text = _HostTestProgress_Adapt(text)
    golden_marker = "$env:SILVERSTAR_GOLDEN_OUTPUT"
    if golden_marker not in text:
        setup_anchor = "Initialize-HostCompiler\nInvoke-RecordCatalogValidator\n"
        if setup_anchor not in text:
            raise RuntimeError("Reference Host Test initialization changed")
        golden_setup = r'''Initialize-HostCompiler
Invoke-RecordCatalogValidator

$projectDocument = Get-Content -Raw -Encoding UTF8 -LiteralPath `
    (Join-Path $repoRoot 'SilverStar.ssproject') | ConvertFrom-Json
$goldenDirectory = Join-Path $repoRoot 'Logs\Golden'
New-Item -ItemType Directory -Force -Path $goldenDirectory | Out-Null
$goldenFilename = ([string]$projectDocument.project.name) + '_golden.sslog'
$env:SILVERSTAR_GOLDEN_OUTPUT = Join-Path $goldenDirectory $goldenFilename
'''
        text = text.replace(setup_anchor, golden_setup, 1)
        collection_anchor = "$script:collectHostJobs = $false\n"
        if collection_anchor not in text:
            raise RuntimeError("Reference Host Test collection boundary changed")
        golden_job = r'''Invoke-HostTest -Name 'golden_sample' -Sources (@(
    "$repoRoot\Tests\Host\generate_golden_sample.c",
    "$repoRoot\Generated\Src\project_log_decoder_profile.c"
) + $sslogSources)

'''
        text = text.replace(collection_anchor, golden_job + collection_anchor, 1)
    policy.Text_AtomicWrite(path, text)


def _ArtifactChecker_Adapt(path: Path, policy: WorkspacePolicy) -> None:
    text = path.read_text(encoding="utf-8")
    legacy = "(Join-Path 'build' `"
    current = "(Join-Path 'build\\FCCG' `"
    if legacy in text:
        text = text.replace(legacy, current, 1)
    elif current not in text:
        raise RuntimeError("Reference artifact checker build-root contract changed")
    if "FCCG_PROGRESS|ARTIFACT|PLAN|8" not in text:
        progress_replacements = (
            (
                "$failures = New-Object 'System.Collections.Generic.List[string]'\n",
                "$failures = New-Object 'System.Collections.Generic.List[string]'\n"
                "Write-Output 'FCCG_PROGRESS|ARTIFACT|PLAN|8'\n"
                "Write-Output 'FCCG_PROGRESS|ARTIFACT|BEGIN|1|8|ELF_MAP_BIN_HEX'\n",
            ),
            (
                "$nmCommand = Get-Command arm-none-eabi-nm -ErrorAction SilentlyContinue\n",
                "Write-Output 'FCCG_PROGRESS|ARTIFACT|DONE|1|8|ELF_MAP_BIN_HEX'\n"
                "Write-Output 'FCCG_PROGRESS|ARTIFACT|BEGIN|2|8|ELF'\n"
                "$nmCommand = Get-Command arm-none-eabi-nm -ErrorAction SilentlyContinue\n",
            ),
            (
                "$ccmStart = [uint64]0x10000000\n",
                "Write-Output 'FCCG_PROGRESS|ARTIFACT|DONE|2|8|ELF'\n"
                "Write-Output 'FCCG_PROGRESS|ARTIFACT|BEGIN|3|8|MAP'\n"
                "$ccmStart = [uint64]0x10000000\n",
            ),
            (
                "$flashSectionNames = @(\n",
                "Write-Output 'FCCG_PROGRESS|ARTIFACT|DONE|3|8|MAP'\n"
                "$flashSectionNames = @(\n",
            ),
            (
                "Assert-ArtifactCondition -Condition ($flashUsed -le $flashLength) `\n",
                "Write-Output 'FCCG_PROGRESS|ARTIFACT|BEGIN|4|8|FLASH'\n"
                "Assert-ArtifactCondition -Condition ($flashUsed -le $flashLength) `\n",
            ),
            (
                "Assert-ArtifactCondition -Condition ($mainSramUsed -le $mainSramLength) `\n",
                "Write-Output 'FCCG_PROGRESS|ARTIFACT|DONE|4|8|FLASH'\n"
                "Write-Output 'FCCG_PROGRESS|ARTIFACT|BEGIN|5|8|MAIN_SRAM'\n"
                "Assert-ArtifactCondition -Condition ($mainSramUsed -le $mainSramLength) `\n",
            ),
            (
                "Assert-ArtifactCondition -Condition ($ccmUsed -le $ccmLength) `\n",
                "Write-Output 'FCCG_PROGRESS|ARTIFACT|DONE|5|8|MAIN_SRAM'\n"
                "Write-Output 'FCCG_PROGRESS|ARTIFACT|BEGIN|6|8|CCMRAM'\n"
                "Assert-ArtifactCondition -Condition ($ccmUsed -le $ccmLength) `\n",
            ),
            (
                "$flashRemaining = $flashLength - [Math]::Min($flashUsed, $flashLength)\n",
                "Write-Output 'FCCG_PROGRESS|ARTIFACT|DONE|6|8|CCMRAM'\n"
                "Write-Output 'FCCG_PROGRESS|ARTIFACT|BEGIN|7|8|heap'\n"
                "$flashRemaining = $flashLength - [Math]::Min($flashUsed, $flashLength)\n",
            ),
            (
                "$largestStaticObjects = @($symbols.Values | Where-Object {\n",
                "Write-Output 'FCCG_PROGRESS|ARTIFACT|DONE|7|8|heap'\n"
                "Write-Output 'FCCG_PROGRESS|ARTIFACT|BEGIN|8|8|summary'\n"
                "$largestStaticObjects = @($symbols.Values | Where-Object {\n",
            ),
        )
        for needle, replacement in progress_replacements:
            if needle not in text:
                raise RuntimeError(
                    "Reference artifact checker progress anchor changed: "
                    + needle.splitlines()[0]
                )
            text = text.replace(needle, replacement, 1)
        text = text.rstrip() + (
            "\nWrite-Output 'FCCG_PROGRESS|ARTIFACT|DONE|8|8|summary'\n"
        )
    policy.Text_AtomicWrite(path, text)


def _PowerTenChecker_Adapt(path: Path, policy: WorkspacePolicy) -> None:
    text = path.read_text(encoding="utf-8")
    if "FCCG_PROGRESS|POWER10|PLAN|$progressTotal" in text:
        return
    replacements = (
        (
            "$files = Get-FirstPartyCFiles\n",
            "$files = Get-FirstPartyCFiles\n"
            "$progressTotal = $files.Count + 2\n"
            "$progressCurrent = 0\n"
            "Write-Output \"FCCG_PROGRESS|POWER10|PLAN|$progressTotal\"\n",
        ),
        (
            "foreach ($file in $files) {\n",
            "foreach ($file in $files) {\n"
            "    $progressCurrent++\n"
            "    $progressSubject = $file.FullName.Substring($repoRoot.Length + 1)\n"
            "    Write-Output \"FCCG_PROGRESS|POWER10|BEGIN|$progressCurrent|$progressTotal|$progressSubject\"\n",
        ),
        (
            "}\n\nforeach ($function in $allFunctions) {\n",
            "    Write-Output \"FCCG_PROGRESS|POWER10|DONE|$progressCurrent|$progressTotal|$progressSubject\"\n"
            "}\n\n"
            "$progressCurrent++\n"
            "Write-Output \"FCCG_PROGRESS|POWER10|BEGIN|$progressCurrent|$progressTotal|function_rules\"\n"
            "foreach ($function in $allFunctions) {\n",
        ),
        (
            "}\n\n$makefile = Get-Content -Raw -LiteralPath (Join-Path $repoRoot 'Makefile')\n",
            "}\n"
            "Write-Output \"FCCG_PROGRESS|POWER10|DONE|$progressCurrent|$progressTotal|function_rules\"\n\n"
            "$progressCurrent++\n"
            "Write-Output \"FCCG_PROGRESS|POWER10|BEGIN|$progressCurrent|$progressTotal|build_policy\"\n"
            "$makefile = Get-Content -Raw -LiteralPath (Join-Path $repoRoot 'Makefile')\n",
        ),
    )
    for needle, replacement in replacements:
        if needle not in text:
            raise RuntimeError(
                "Reference Power-of-Ten checker progress anchor changed: "
                + needle.splitlines()[0]
            )
        text = text.replace(needle, replacement, 1)
    text = text.rstrip() + (
        "\nWrite-Output \"FCCG_PROGRESS|POWER10|DONE|$progressCurrent|$progressTotal|build_policy\"\n"
    )
    policy.Text_AtomicWrite(path, text)


def _ProtocolProfileMetadata_Write(
    staged_builtin: Path, policy: WorkspacePolicy
) -> None:
    metadata_root = (
        staged_builtin
        / "silverstar_protocol_reference_v0"
        / "payload"
        / "Protocol"
        / "metadata"
    )
    documents = {
        "air_m0.json": {
            "format_version": 1,
            "profile_id": "air.m0",
            "service": "telemetry_service",
            "slot": "telemetry_protocol",
            "wire_value": 0,
            "framing": "packet",
            "minimum_mtu": 50,
            "sensor_status": {
                "message_type": "AIR_TYPE_SENSOR_STATUS",
                "device_identity_fields": ["sensor_id", "instance_id"],
                "wire_layout_unchanged": True,
            },
        },
        "maintenance_serial_0_0.json": {
            "format_version": 1,
            "profile_id": "maintenance.serial.0_0",
            "service": "maintenance_service",
            "slot": "maintenance_protocol",
            "framing": "utf8_line",
            "transport": "byte_stream",
            "device_addressing": {
                "classes": ["IMU", "BARO", "GNSS"],
                "instance_range": [0, 255],
                "identity_fields": [
                    "descriptor_id",
                    "instance_id",
                    "physical_device_id",
                ],
            },
        },
    }
    for filename, document in documents.items():
        policy.Text_AtomicWrite(
            metadata_root / filename,
            json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        )


def _GeneratedFacadeTemplates_Copy(
    reference: Path, staged_builtin: Path, policy: WorkspacePolicy
) -> None:
    template_root = (
        staged_builtin
        / "silverstar_core_0_0_9"
        / "templates"
        / "generated"
    )
    header_source = reference / "Generated" / "Inc" / "project_device_instances.h"
    implementation_source = (
        reference / "Generated" / "Src" / "project_device_instances.c"
    )
    decoder_header_source = (
        reference / "Generated" / "Inc" / "project_log_decoder_profile.h"
    )
    decoder_implementation_source = (
        reference / "Generated" / "Src" / "project_log_decoder_profile.c"
    )
    semantics_source = reference / "Generated" / "project_semantics.json"
    log_config_source = reference / "Generated" / "Src" / "project_log_config.c"
    header_text = header_source.read_text(encoding="utf-8")
    implementation_text = implementation_source.read_text(encoding="utf-8")
    legacy_validator = (
        "    SystemDeviceDescriptor descriptor;\n\n"
        "    switch (instance_id)\n"
        "    {\n"
        "        case 0U:\n"
        "            return SystemDescriptor_DeviceFind(\n"
        "                device_class, instance_id, &descriptor);\n"
        "        default:\n"
        "            return SYSTEM_DEVICE_NOT_PRESENT;\n"
        "    }"
    )
    generic_validator = (
        "    SystemDeviceDescriptor descriptor;\n\n"
        "    return SystemDescriptor_DeviceFind(\n"
        "        device_class, instance_id, &descriptor);"
    )
    compact_generic_validator = (
        "    SystemDeviceDescriptor descriptor;\n\n"
        "    return SystemDescriptor_DeviceFind(device_class, instance_id, &descriptor);"
    )
    if legacy_validator in implementation_text:
        implementation_text = implementation_text.replace(
            legacy_validator, generic_validator, 1
        )
    elif (
        generic_validator not in implementation_text
        and compact_generic_validator not in implementation_text
    ):
        raise RuntimeError("Reference project-device facade validation changed")
    policy.Text_AtomicWrite(
        template_root / "project_device_instances.h", header_text
    )
    policy.Text_AtomicWrite(
        template_root / "project_device_instances.c", implementation_text
    )
    policy.File_Copy(
        log_config_source,
        template_root / "project_log_config.c",
    )
    policy.File_Copy(
        decoder_header_source,
        template_root / "project_log_decoder_profile.h",
    )
    policy.File_Copy(
        decoder_implementation_source,
        template_root / "project_log_decoder_profile.c",
    )
    policy.File_Copy(
        semantics_source,
        template_root / "project_semantics.json",
    )


def _ProtocolMetadata_Adapt(
    path: Path, overlay_path: Path, policy: WorkspacePolicy
) -> None:
    metadata = json.loads(path.read_text(encoding="utf-8"))
    overlay = json.loads(overlay_path.read_text(encoding="utf-8"))
    if set(overlay) != {"fccg", "default_stream_enabled"}:
        raise RuntimeError("Protocol metadata overlay has unexpected fields")
    records = metadata.get("records")
    if not isinstance(records, list):
        raise RuntimeError("Reference Protocol metadata records changed")
    by_name = {
        str(record.get("name", "")): record
        for record in records
        if isinstance(record, dict)
    }
    enabled_overrides = overlay["default_stream_enabled"]
    if not isinstance(enabled_overrides, dict):
        raise RuntimeError("Protocol metadata default-stream overlay is invalid")
    for name, enabled in enabled_overrides.items():
        record = by_name.get(str(name))
        if record is None or not isinstance(enabled, bool):
            raise RuntimeError(f"Protocol metadata overlay record is invalid: {name}")
    fccg = overlay["fccg"]
    record_policies = fccg.get("records") if isinstance(fccg, dict) else None
    record_enums = {
        str(record.get("enum", ""))
        for record in records
        if isinstance(record, dict)
    }
    if not isinstance(record_policies, dict) or set(record_policies) != record_enums:
        raise RuntimeError("Protocol metadata overlay does not cover every record")
    for name, enabled in enabled_overrides.items():
        enum_name = str(by_name[str(name)]["enum"])
        policy_entry = record_policies.get(enum_name)
        if not isinstance(policy_entry, dict):
            raise RuntimeError(f"Protocol policy overlay is invalid: {enum_name}")
        policy_entry["default_enabled"] = enabled
    metadata["fccg"] = fccg
    policy.Text_AtomicWrite(
        path, json.dumps(metadata, ensure_ascii=False, indent=2) + "\n"
    )


def _BoardUserVisibleNames_Adapt(
    staged_builtin: Path, policy: WorkspacePolicy
) -> None:
    replacements = (
        (
            staged_builtin
            / "silverstar_board_silverstar_0_5"
            / "payload"
            / "Board"
            / "SilverStar_0_5"
            / "Services"
            / "Src"
            / "power_service.c",
            '"SilverStar 0.5 Voltage Input"',
            '"SS0.5 Voltage Input"',
        ),
        (
            staged_builtin
            / "silverstar_mcu_stm32f407vet6"
            / "payload"
            / "Targets"
            / "SilverStar_F407"
            / "Inc"
            / "target_system_config.h",
            "Adapters and SilverStar 0.5 Board services",
            "Adapters and SS0.5 Board services",
        ),
    )
    for path, legacy_text, current_text in replacements:
        content = path.read_text(encoding="utf-8")
        if legacy_text not in content and current_text not in content:
            raise RuntimeError(
                f"Reference Board naming contract changed unexpectedly: {path}"
            )
        policy.Text_AtomicWrite(
            path, content.replace(legacy_text, current_text)
        )


def _BoardLogicalDevices_Adapt(
    staged_builtin: Path, policy: WorkspacePolicy
) -> None:
    service_root = (
        staged_builtin
        / "silverstar_board_silverstar_0_5"
        / "payload"
        / "Board"
        / "SilverStar_0_5"
        / "Services"
        / "Src"
    )
    output_path = service_root / "output_service.c"
    output_text = output_path.read_text(encoding="utf-8")
    output_text = output_text.replace(
        "PROJECT_RESOURCE_POWER_OUTPUT_1",
        "PROJECT_RESOURCE_LAUNCH_IGNITION_OUTPUT",
    ).replace(
        "PROJECT_RESOURCE_POWER_OUTPUT_2",
        "PROJECT_RESOURCE_PARACHUTE_PYRO_OUTPUT",
    )
    output_text = output_text.replace(
        '#include "project_resources.h"\n',
        '#include "project_resources.h"\n'
        '#include "mission_action_output_config.h"\n',
        1,
    )
    output_text = output_text.replace(
        "#define OUTPUT_CHANNEL_COUNT 2U",
        "#define OUTPUT_CHANNEL_CAPACITY 2U",
        1,
    )
    channel_storage = "static GpioOutputChannel s_channels[OUTPUT_CHANNEL_COUNT];"
    channel_storage_configured = (
        "static GpioOutputChannel s_channels[OUTPUT_CHANNEL_CAPACITY];"
    )
    if channel_storage not in output_text:
        raise RuntimeError("Reference output service storage contract changed")
    output_text = output_text.replace(
        channel_storage, channel_storage_configured, 1
    )
    availability_function = (
        "static uint8_t SilverStarOutputService_ChannelAvailable(uint8_t channel)\n"
        "{\n"
        "    if (channel == MISSION_ACTION_START_OUTPUT_CHANNEL)\n"
        "    {\n"
        "        return PROJECT_FEATURE_LAUNCH_IGNITION_OUTPUT;\n"
        "    }\n"
        "    if (channel == MISSION_ACTION_DEPLOY_OUTPUT_CHANNEL)\n"
        "    {\n"
        "        return PROJECT_FEATURE_PARACHUTE_PYRO_OUTPUT;\n"
        "    }\n"
        "    return 0U;\n"
        "}\n\n"
    )
    irq_lock = "static uint32_t SilverStarOutputService_IrqLock(void)\n"
    if irq_lock not in output_text:
        raise RuntimeError("Reference output service IRQ contract changed")
    output_text = output_text.replace(
        irq_lock, availability_function + irq_lock, 1
    )
    channel_guard = (
        "if ((channel == 0U) || (channel > OUTPUT_CHANNEL_COUNT))"
    )
    channel_guard_configured = (
        "if ((channel == 0U) || (channel > OUTPUT_CHANNEL_CAPACITY) ||\n"
        "        (SilverStarOutputService_ChannelAvailable(channel) == 0U))"
    )
    if channel_guard not in output_text:
        raise RuntimeError("Reference output service channel guard changed")
    output_text = output_text.replace(
        channel_guard, channel_guard_configured, 1
    )
    safe_initialization = (
        "    SilverStarOutputService_ChannelSafe(&s_channels[0]);\n"
        "    SilverStarOutputService_ChannelSafe(&s_channels[1]);"
    )
    safe_initialization_configured = (
        "    if (PROJECT_FEATURE_LAUNCH_IGNITION_OUTPUT != 0U)\n"
        "    {\n"
        "        SilverStarOutputService_ChannelSafe(&s_channels[0]);\n"
        "    }\n"
        "    if (PROJECT_FEATURE_PARACHUTE_PYRO_OUTPUT != 0U)\n"
        "    {\n"
        "        SilverStarOutputService_ChannelSafe(&s_channels[1]);\n"
        "    }"
    )
    if safe_initialization not in output_text:
        raise RuntimeError("Reference output service channel initialization changed")
    output_text = output_text.replace(
        safe_initialization, safe_initialization_configured, 1
    )
    init_preamble = (
        "static SystemDeviceResult SilverStarOutputService_Init(void)\n"
        "{\n"
        "    uint32_t primask;\n\n"
    )
    init_preamble_configured = (
        f"{init_preamble}"
        "    SILVERSTAR_ASSERT(PROJECT_FEATURE_LAUNCH_IGNITION_OUTPUT <= 1U,\n"
        "                      SILVERSTAR_ASSERT_MODULE_BOARD,\n"
        "                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);\n"
        "    SILVERSTAR_ASSERT(PROJECT_FEATURE_PARACHUTE_PYRO_OUTPUT <= 1U,\n"
        "                      SILVERSTAR_ASSERT_MODULE_BOARD,\n"
        "                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);\n"
    )
    if init_preamble not in output_text:
        raise RuntimeError("Reference output service initialization contract changed")
    output_text = output_text.replace(
        init_preamble, init_preamble_configured, 1
    )
    output_text = output_text.replace(
        "index < OUTPUT_CHANNEL_COUNT", "index < OUTPUT_CHANNEL_CAPACITY"
    )
    set_safe_call = "        SilverStarOutputService_ChannelSafe(&s_channels[index]);"
    set_safe_call_configured = (
        "        if (SilverStarOutputService_ChannelAvailable(index + 1U) != 0U)\n"
        "        {\n"
        "            SilverStarOutputService_ChannelSafe(&s_channels[index]);\n"
        "        }"
    )
    if set_safe_call not in output_text:
        raise RuntimeError("Reference output service safe loop changed")
    output_text = output_text.replace(
        set_safe_call, set_safe_call_configured, 1
    )
    process_condition = (
        "if ((s_channels[index].status.state == SYSTEM_OUTPUT_ACTIVE) &&"
    )
    process_condition_configured = (
        "if ((SilverStarOutputService_ChannelAvailable(index + 1U) != 0U) &&\n"
        "            (s_channels[index].status.state == SYSTEM_OUTPUT_ACTIVE) &&"
    )
    if process_condition not in output_text:
        raise RuntimeError("Reference output service process loop changed")
    output_text = output_text.replace(
        process_condition, process_condition_configured, 1
    )
    policy.Text_AtomicWrite(output_path, output_text)

    power_path = service_root / "power_service.c"
    power_text = power_path.read_text(encoding="utf-8")
    adc_read = (
        "    platform_result = PlatformAdc_Read(PROJECT_RESOURCE_INPUT_VOLTAGE_ADC,\n"
        "                                       ADC_POWER_POLL_TIMEOUT_MS,\n"
        "                                       &adc_count);\n"
        "    if (platform_result != PLATFORM_OK)\n"
        "    {\n"
        "        SilverStarPowerService_ErrorRecord((platform_result == PLATFORM_TIMEOUT) ?\n"
        "            SYSTEM_DEVICE_TIMEOUT : SYSTEM_DEVICE_IO_ERROR);\n"
        "        return;\n"
        "    }"
    )
    adc_read_optional = (
        "    if (PROJECT_FEATURE_INPUT_VOLTAGE_MONITOR == 0U)\n"
        "    {\n"
        "        return;\n"
        "    }\n"
        f"{adc_read}"
    )
    if adc_read not in power_text:
        raise RuntimeError("Reference power service ADC sampling contract changed")
    power_text = power_text.replace(
        adc_read, adc_read_optional, 1
    )
    policy.Text_AtomicWrite(power_path, power_text)


def _EnvironmentTemplates_Copy(
    reference: Path, staged_builtin: Path, policy: WorkspacePolicy
) -> None:
    template_root = (
        staged_builtin
        / "silverstar_environment_vscode_eide_gcc"
        / "templates"
        / "reference"
    )
    relative_templates = (
        Path(".eide/eide.yml"),
        Path(".eide/files.options.yml"),
        Path("Flight_Controller0.5.code-workspace"),
        Path(".vscode/tasks.json"),
        Path(".vscode/extensions.json"),
        Path(".vscode/settings.json"),
    )
    copied: list[str] = []
    missing: list[str] = []
    for relative in relative_templates:
        source = reference / relative
        if source.is_file():
            policy.File_Copy(source, template_root / relative)
            copied.append(relative.as_posix())
        else:
            missing.append(relative.as_posix())
    required = {
        ".eide/eide.yml",
        ".eide/files.options.yml",
        "Flight_Controller0.5.code-workspace",
        ".vscode/tasks.json",
    }
    if not required.issubset(copied):
        raise RuntimeError(
            "Reference development-environment templates are incomplete: "
            + ", ".join(sorted(required.difference(copied)))
        )
    policy.Text_AtomicWrite(
        template_root / "inventory.json",
        json.dumps(
            {"copied": copied, "missing_in_reference": missing},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )


def _ImportedDocumentation_Adapt(
    staged_builtin: Path, policy: WorkspacePolicy
) -> None:
    """Apply FCCG output-layout overlays to copied reference documentation."""
    replacements = (
        ("build/SilverStar_F407/", "build/FCCG/SilverStar_F407/"),
        ("build/EIDE/SilverStar_F407/Debug/", "build/FCCG/SilverStar_F407/EIDE/"),
        ("build/EIDE/SilverStar_F407/Debug", "build/FCCG/SilverStar_F407/EIDE"),
        ("build/EIDE/", "build/FCCG/SilverStar_F407/EIDE/"),
        ("build/Host/Tests/", "build/FCCG/Host/Tests/"),
        ("build/Host/Tests", "build/FCCG/Host/Tests"),
        ("build/<Target>/<Debug|Release>", "build/FCCG/<Target>/<Debug|Release>"),
    )
    for path in staged_builtin.glob("*/docs/*.md"):
        content = path.read_text(encoding="utf-8")
        adapted = content
        for old, new in replacements:
            adapted = adapted.replace(old, new)
        if adapted != content:
            policy.Text_AtomicWrite(path, adapted)


def Components_Import(reference: Path, *, force: bool = False) -> dict[str, Any]:
    reference = reference.resolve()
    provenance = ReferenceProvenance_Get(reference)
    if provenance["working_tree"] != "clean":
        raise RuntimeError(
            "Reference import requires a clean read-only firmware working tree"
        )
    audit = ReferenceAudit_Get(reference)
    if audit["missing_required_files"]:
        raise RuntimeError(
            "Reference is missing required latest-firmware files: "
            + ", ".join(audit["missing_required_files"])
        )
    provenance["audit"] = audit
    policy = WorkspacePolicy(WORKSPACE_ROOT)
    builtin_root = policy.Path_Resolve(BUILTIN_ROOT, allow_root=False)
    if builtin_root.exists() and not force:
        raise RuntimeError(f"Builtin plugin directory already exists: {builtin_root}")
    stage = policy.StagingDirectory_Create("builtin-import-")
    staged_builtin = stage / "builtin"
    staged_builtin.mkdir(parents=True)
    backup = stage / "previous-builtin"
    try:
        for component in _Components_Get(reference, provenance):
            manifest = component["manifest"]
            slug = manifest["id"].replace(".", "_")
            package_root = staged_builtin / slug
            payload_root = package_root / "payload"
            package_root.mkdir(parents=True)
            for relative_text in manifest["payload"]["roots"]:
                relative = Path(*relative_text.split("/"))
                _Tree_Copy(policy, reference / relative, payload_root / relative)
            for doc_text in component["docs"]:
                source = reference / Path(*doc_text.split("/"))
                if source.is_file():
                    policy.File_Copy(source, package_root / "docs" / source.name)
            policy.Text_AtomicWrite(
                package_root / "plugin.json",
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            )
            readme = (
                f"# {manifest['name']}\n\n"
                f"Declarative SilverStar_FCCG builtin `{manifest['type']}` plugin.\n\n"
                f"Imported read-only from `{provenance['branch']}` at "
                f"`{provenance['commit']}`. Plugin payload is data and is never executed.\n"
            )
            policy.Text_AtomicWrite(package_root / "README.md", readme)
        _ArchitectureChecker_Adapt(
            staged_builtin
            / "silverstar_core_0_0_9"
            / "payload"
            / "Tools"
            / "check_architecture.ps1",
            policy,
        )
        _HostTestRunner_Adapt(
            staged_builtin
            / "silverstar_core_0_0_9"
            / "payload"
            / "Tests"
            / "Host"
            / "run_tests.ps1",
            policy,
        )
        policy.File_Copy(
            REFERENCE_OVERLAY_ROOT / "generate_golden_sample.c",
            staged_builtin
            / "silverstar_core_0_0_9"
            / "payload"
            / "Tests"
            / "Host"
            / "generate_golden_sample.c",
        )
        _ArtifactChecker_Adapt(
            staged_builtin
            / "silverstar_core_0_0_9"
            / "payload"
            / "Tools"
            / "check_firmware_artifact.ps1",
            policy,
        )
        _PowerTenChecker_Adapt(
            staged_builtin
            / "silverstar_core_0_0_9"
            / "payload"
            / "Tools"
            / "check_power_of_ten.ps1",
            policy,
        )
        _BoardUserVisibleNames_Adapt(staged_builtin, policy)
        _BoardLogicalDevices_Adapt(staged_builtin, policy)
        _ImportedDocumentation_Adapt(staged_builtin, policy)
        _EnvironmentTemplates_Copy(reference, staged_builtin, policy)
        _GeneratedFacadeTemplates_Copy(reference, staged_builtin, policy)
        _ProtocolProfileMetadata_Write(staged_builtin, policy)
        _ProtocolMetadata_Adapt(
            staged_builtin
            / "silverstar_protocol_reference_v0"
            / "payload"
            / "Protocol"
            / "SSLOG"
            / "schema"
            / "sslog_parser_metadata.json",
            REFERENCE_OVERLAY_ROOT / "sslog_fccg_metadata.json",
            policy,
        )
        policy.Text_AtomicWrite(
            staged_builtin
            / "silverstar_board_silverstar_0_5"
            / "connections.json",
            json.dumps(_BoardConnections_Get(), ensure_ascii=False, indent=2) + "\n",
        )
        policy.Text_AtomicWrite(
            staged_builtin / "reference_provenance.json",
            json.dumps(provenance, ensure_ascii=False, indent=2) + "\n",
        )
        PluginCatalog(staged_builtin, stage / "installed-empty").Scan()
        if builtin_root.exists():
            policy.Path_Replace(builtin_root, backup)
        try:
            policy.Path_Replace(staged_builtin, builtin_root)
        except Exception:
            if backup.exists():
                policy.Path_Replace(backup, builtin_root)
            raise
        if backup.exists():
            policy.Tree_Remove(backup)
        return provenance
    finally:
        if stage.exists():
            policy.Tree_Remove(stage)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import the latest read-only SilverStar reference as declarative builtins"
    )
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--search-root", action="append", type=Path, default=[])
    parser.add_argument("--force", action="store_true")
    options = parser.parse_args()
    reference = ReferencePath_Resolve(options.reference, options.search_root)
    provenance = Components_Import(reference, force=options.force)
    print(
        json.dumps(
            {"builtin_root": str(BUILTIN_ROOT), "reference": provenance},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
