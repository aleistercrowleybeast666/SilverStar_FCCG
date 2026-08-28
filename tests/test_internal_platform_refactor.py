from __future__ import annotations

import hashlib
import io
import inspect
import json
import shutil
import zipfile
from dataclasses import replace
from pathlib import Path

import pytest

from silverstar_fccg.generator.log_decoder_profile import LogDecoderPackage_Verify
from silverstar_fccg.generator.render import (
    LogDecoderProfile_Render,
    _PlatformBinding_Render,
    _PlatformResources_Render,
)
from silverstar_fccg.generator.source_graph import SourceGraph_Resolve
from silverstar_fccg.core.workspace import WorkspacePolicy
from silverstar_fccg.hardware.cubemx import CubeMxImporter
from silverstar_fccg.hardware.inventory import CubeMxInventory_Parse
from silverstar_fccg.hardware.platform import (
    DetectedMcuFacts,
    PlatformMatchError,
    PlatformMatch_Resolve,
)
from silverstar_fccg.plugins.catalog import PluginCatalog
from silverstar_fccg.plugins.manifest import (
    PlatformResourceBinding,
    PluginManifestError,
    PluginManifest_Load,
)
from silverstar_fccg.project.configuration import ProjectConfiguration_Reconcile
from silverstar_fccg.project.model import DeviceInstance, HardwareConfiguration
from silverstar_fccg.project.reference import ReferenceProject_Create
from silverstar_fccg.project.resources import ResourceAssignments_Resolve
from silverstar_fccg.project.validation import Project_Validate


def _Device_Write(
    installed_root: Path,
    component_id: str,
    kind: str,
    constraints: dict,
    platform_capabilities: list[str],
) -> None:
    package = installed_root / component_id / "1.0.0"
    (package / "payload" / "Fixture").mkdir(parents=True)
    manifest = {
        "schema_version": 0,
        "id": component_id,
        "name": component_id.rsplit(".", 1)[-1],
        "type": "device",
        "class": "fixture_sensor",
        "instance_policy": {
            "plugin_max": 4,
            "class_max": 8,
            "same_plugin_multiple": True,
            "multi_instance_ready": True,
        },
        "physical_device": {
            "vendor": "Fixture",
            "model": component_id,
            "chipset": "fixture",
            "driver": "fixture",
        },
        "version": "1.0.0",
        "description": "Test-only declarative platform resource consumer.",
        "requires": {
            "components": [
                {"id": "silverstar.core.0_0_9", "optional": False}
            ],
            "resources": [
                {
                    "name": "bus",
                    "kind": kind,
                    "required": True,
                    "mode": "shared",
                    "platform_capabilities": platform_capabilities,
                    "constraints": constraints,
                    "display_names": {"en_US": "Fixture bus"},
                }
            ],
            "capabilities": [],
        },
        "resources": {"provides": [], "roles": [], "conflicts": []},
        "provides": [],
        "build": {
            "sources": [],
            "asm_sources": [],
            "include_dirs": [],
            "defines": [],
        },
        "payload": {"roots": ["Fixture"]},
        "metadata": {
            "declarative": True,
            "device_category": "sensor.temperature",
        },
    }
    (package / "plugin.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _Catalog_Create(workspace_root: Path, installed_root: Path) -> PluginCatalog:
    catalog = PluginCatalog(workspace_root / "plugins" / "builtin", installed_root)
    catalog.Scan()
    return catalog


def _Inventory_Create() -> object:
    return CubeMxInventory_Parse(
        "\n".join(
            (
                "Mcu.CPN=STM32F407VET6",
                "Mcu.Family=STM32F4",
                "Mcu.Package=LQFP100",
                "Mcu.Core=ARM Cortex-M4",
                "Mcu.IP0=I2C1",
                "Mcu.IP1=CAN1",
                "Mcu.IP2=TIM3",
                "PB6.Signal=I2C1_SCL",
                "PB6.GPIO_PuPd=GPIO_PULLUP",
                "PB6.GPIO_OutputType=GPIO_MODE_AF_OD",
                "PB7.Signal=I2C1_SDA",
                "PB7.GPIO_PuPd=GPIO_PULLUP",
                "PB7.GPIO_OutputType=GPIO_MODE_AF_OD",
                "PB8.Signal=CAN1_RX",
                "PB9.Signal=CAN1_TX",
                "PA6.Signal=TIM3_CH1",
                "PA7.Signal=TIM3_CH2",
                "I2C1.ClockSpeed=400000",
                "I2C1.AddressingMode=I2C_ADDRESSINGMODE_7BIT",
                "CAN1.Prescaler=6",
                "CAN1.TimeSeg1=CAN_BS1_11TQ",
                "CAN1.TimeSeg2=CAN_BS2_2TQ",
                "CAN1.Mode=CAN_MODE_NORMAL",
                "TIM3.Prescaler=83",
                "TIM3.Period=19999",
                "RCC.APB1Freq_Value=42000000",
            )
        )
    )


def _CustomModel_Create(catalog: PluginCatalog, devices: list[DeviceInstance]):
    inventory = _Inventory_Create()
    model = ReferenceProject_Create("OptionalPlatform", catalog=catalog)
    model.board = ""
    model.device_instances = devices
    model.resource_assignments = {}
    model.hardware = HardwareConfiguration(
        mode="custom",
        source_kind="manual_import",
        provider="silverstar.hardware_provider.stm32_cubemx",
        snapshot_id="a" * 64,
        mcu="STM32F407VET6",
        capabilities=tuple(
            sorted(
                {
                    f"peripheral.{resource.kind}"
                    for resource in inventory.HardwareResources_Get()
                }
            )
        ),
        inventory=inventory.Dictionary_Get(),
        resources=inventory.HardwareResources_Get(),
        build_sources=(
            "HardwareGenerated/STM32CubeMX/Core/Src/main.c",
            "HardwareGenerated/STM32CubeMX/Drivers/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_i2c.c",
            "HardwareGenerated/STM32CubeMX/Drivers/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_i2c_ex.c",
            "HardwareGenerated/STM32CubeMX/Drivers/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_can.c",
        ),
        include_dirs=(
            "HardwareGenerated/STM32CubeMX/Core/Inc",
            "HardwareGenerated/STM32CubeMX/Drivers/STM32F4xx_HAL_Driver/Inc",
        ),
    )
    return model


def test_default_reference_does_not_select_optional_platform_backends(
    builtin_catalog: PluginCatalog,
) -> None:
    graph = SourceGraph_Resolve(
        ReferenceProject_Create("DefaultNoOptional", catalog=builtin_catalog),
        builtin_catalog,
    )
    optional_tokens = (
        "platform_i2c_stm32f4.c",
        "platform_can_stm32f4.c",
        "platform_pwm_stm32f4.c",
        "stm32f4xx_hal_i2c.c",
        "stm32f4xx_hal_i2c_ex.c",
        "stm32f4xx_hal_can.c",
    )
    assert not any(
        source.endswith(optional_tokens) for source in graph.sources
    )


def test_hardware_inventory_json_has_case_insensitive_unique_keys(
    builtin_catalog: PluginCatalog,
) -> None:
    inventory = ReferenceProject_Create(
        "PowerShellCompatibleInventory", catalog=builtin_catalog
    ).hardware.inventory

    def keys_validate(value: object) -> None:
        if isinstance(value, dict):
            folded = [str(key).casefold() for key in value]
            assert len(folded) == len(set(folded))
            for child in value.values():
                keys_validate(child)
        elif isinstance(value, list):
            for child in value:
                keys_validate(child)

    keys_validate(inventory)
    spi_settings = inventory["spis"][0]["settings"]
    assert spi_settings["mode"] == "master"
    assert spi_settings["cubemx_Mode"] == "SPI_MODE_MASTER"


def test_i2c_inventory_assignment_glue_and_conditional_sources(
    tmp_path: Path, workspace_root: Path
) -> None:
    installed = tmp_path / "installed"
    _Device_Write(
        installed,
        "fixture.device.i2c_temperature",
        "i2c",
        {
            "i2c": {
                "maximum_bus_frequency_hz": 400000,
                "address_mode": "7bit",
                "address_7bit": 0x48,
                "required_pullup": True,
            }
        },
        ["i2c.master_blocking"],
    )
    catalog = _Catalog_Create(workspace_root, installed)
    model = _CustomModel_Create(
        catalog,
        [DeviceInstance("temperature0", "fixture.device.i2c_temperature")],
    )
    model.resource_assignments["temperature0:bus"] = "I2C1"
    assert ResourceAssignments_Resolve(model, catalog).valid
    graph = SourceGraph_Resolve(model, catalog)
    assert "Platform/STM32F4/Src/platform_i2c_stm32f4.c" in graph.sources
    assert any(source.endswith("stm32f4xx_hal_i2c.c") for source in graph.sources)
    assert any(source.endswith("stm32f4xx_hal_i2c_ex.c") for source in graph.sources)
    assert not any(source.endswith("stm32f4xx_hal_can.c") for source in graph.sources)
    glue = _PlatformResources_Render(model, catalog)
    assert '#include "i2c.h"' in glue
    assert "&hi2c1" in glue


def test_i2c_address_conflict_and_repeated_start_capability_fail_early(
    tmp_path: Path, workspace_root: Path
) -> None:
    installed = tmp_path / "installed"
    _Device_Write(
        installed,
        "fixture.device.i2c_shared",
        "i2c",
        {"i2c": {"address_7bit": 0x68, "address_mode": "7bit"}},
        ["i2c.master_blocking"],
    )
    catalog = _Catalog_Create(workspace_root, installed)
    model = _CustomModel_Create(
        catalog,
        [
            DeviceInstance("sensor0", "fixture.device.i2c_shared"),
            DeviceInstance("sensor1", "fixture.device.i2c_shared"),
        ],
    )
    model.resource_assignments.update(
        {"sensor0:bus": "I2C1", "sensor1:bus": "I2C1"}
    )
    result = ResourceAssignments_Resolve(model, catalog)
    assert any("I2C address conflict" in error for error in result.errors)

    repeated_root = tmp_path / "repeated"
    _Device_Write(
        repeated_root,
        "fixture.device.i2c_repeated",
        "i2c",
        {
            "i2c": {
                "address_7bit": 0x69,
                "address_mode": "7bit",
                "requires_repeated_start": True,
            }
        },
        ["i2c.master_blocking"],
    )
    repeated_catalog = _Catalog_Create(workspace_root, repeated_root)
    repeated_model = _CustomModel_Create(
        repeated_catalog,
        [DeviceInstance("sensor0", "fixture.device.i2c_repeated")],
    )
    repeated_model.resource_assignments["sensor0:bus"] = "I2C1"
    repeated = ResourceAssignments_Resolve(repeated_model, repeated_catalog)
    assert any("i2c.repeated_start" in error for error in repeated.errors)


def test_i2c_shared_address_requires_one_explicit_composite_device(
    tmp_path: Path, workspace_root: Path
) -> None:
    installed = tmp_path / "installed"
    component_id = "fixture.device.i2c_composite"
    _Device_Write(
        installed,
        component_id,
        "i2c",
        {"i2c": {"address_7bit": 0x68, "address_mode": "7bit"}},
        ["i2c.master_blocking"],
    )
    manifest_path = installed / component_id / "1.0.0" / "plugin.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    second = json.loads(json.dumps(data["requires"]["resources"][0]))
    second["name"] = "auxiliary"
    data["requires"]["resources"].append(second)
    manifest_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    catalog = _Catalog_Create(workspace_root, installed)
    model = _CustomModel_Create(
        catalog, [DeviceInstance("sensor0", component_id)]
    )
    model.resource_assignments.update(
        {"sensor0:bus": "I2C1", "sensor0:auxiliary": "I2C1"}
    )
    conflict = ResourceAssignments_Resolve(model, catalog)
    assert any("matching composite_device" in error for error in conflict.errors)

    for requirement in data["requires"]["resources"]:
        requirement["constraints"]["i2c"]["composite_device"] = "imu.package"
    manifest_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    catalog = _Catalog_Create(workspace_root, installed)
    model = _CustomModel_Create(
        catalog, [DeviceInstance("sensor0", component_id)]
    )
    model.resource_assignments.update(
        {"sensor0:bus": "I2C1", "sensor0:auxiliary": "I2C1"}
    )
    assert ResourceAssignments_Resolve(model, catalog).valid


def test_typed_optional_backend_requires_declared_platform_capability(
    tmp_path: Path
) -> None:
    installed = tmp_path / "installed"
    component_id = "fixture.device.i2c_without_backend_contract"
    _Device_Write(
        installed,
        component_id,
        "i2c",
        {"i2c": {"address_7bit": 0x69}},
        [],
    )
    manifest_path = installed / component_id / "1.0.0" / "plugin.json"
    with pytest.raises(PluginManifestError, match="platform_capabilities"):
        PluginManifest_Load(manifest_path, source="installed")


def test_protocol_extensions_require_namespaced_object_values(
    tmp_path: Path, workspace_root: Path
) -> None:
    source = (
        workspace_root
        / "plugins"
        / "builtin"
        / "silverstar_protocol_telemetry_air_m0"
    )
    package = tmp_path / "protocol"
    shutil.copytree(source, package)
    manifest_path = package / "plugin.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["protocol"]["extensions"] = {"example.vendor": ["unsafe-shape"]}
    manifest_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with pytest.raises(PluginManifestError, match="object values"):
        PluginManifest_Load(manifest_path, source="installed")


def test_classic_can_single_owner_and_fdcan_do_not_cross_match(
    tmp_path: Path, workspace_root: Path
) -> None:
    installed = tmp_path / "installed"
    _Device_Write(
        installed,
        "fixture.device.classic_can",
        "can_classic",
        {
            "can": {
                "allowed_nominal_bitrates": [500000],
                "frame_format": "classic",
                "mode": "normal",
            }
        },
        ["can.classic_bxcan"],
    )
    catalog = _Catalog_Create(workspace_root, installed)
    model = _CustomModel_Create(
        catalog,
        [DeviceInstance("can0", "fixture.device.classic_can")],
    )
    model.resource_assignments["can0:bus"] = "CAN1"
    assert ResourceAssignments_Resolve(model, catalog).valid
    graph = SourceGraph_Resolve(model, catalog)
    assert "Platform/STM32F4/Src/platform_can_stm32f4.c" in graph.sources
    assert any(source.endswith("stm32f4xx_hal_can.c") for source in graph.sources)
    assert "&hcan1" in _PlatformResources_Render(model, catalog)

    model.device_instances.append(
        DeviceInstance("can1", "fixture.device.classic_can")
    )
    model.resource_assignments["can1:bus"] = "CAN1"
    conflict = ResourceAssignments_Resolve(model, catalog)
    assert any("ownership conflict" in error for error in conflict.errors)

    fdcan = CubeMxInventory_Parse(
        "\n".join(
            (
                "Mcu.CPN=STM32H743ZIT6",
                "Mcu.Family=STM32H7",
                "Mcu.IP0=FDCAN1",
                "PB8.Signal=FDCAN1_RX",
                "PB9.Signal=FDCAN1_TX",
            )
        )
    )
    assert fdcan.cans[0].kind == "can_fd"
    assert all(resource.kind != "can_classic" for resource in fdcan.HardwareResources_Get())


def test_pwm_channel_identity_shared_timer_and_frequency_conflict(
    tmp_path: Path, workspace_root: Path
) -> None:
    installed = tmp_path / "installed"
    _Device_Write(
        installed,
        "fixture.device.pwm_50hz",
        "pwm",
        {
            "pwm": {
                "frequency_hz": 50,
                "minimum_resolution_bits": 12,
                "polarity": "active_high",
                "safe_state": "inactive",
            }
        },
        ["pwm.output_fixed_frequency"],
    )
    catalog = _Catalog_Create(workspace_root, installed)
    model = _CustomModel_Create(
        catalog,
        [
            DeviceInstance("pwm0", "fixture.device.pwm_50hz"),
            DeviceInstance("pwm1", "fixture.device.pwm_50hz"),
        ],
    )
    model.resource_assignments.update(
        {"pwm0:bus": "TIM3_CH1", "pwm1:bus": "TIM3_CH2"}
    )
    assert ResourceAssignments_Resolve(model, catalog).valid
    glue = _PlatformResources_Render(model, catalog)
    assert "&htim3, TIM_CHANNEL_1" in glue
    assert "&htim3, TIM_CHANNEL_2" in glue
    assert "Platform/STM32F4/Src/platform_pwm_stm32f4.c" in SourceGraph_Resolve(
        model, catalog
    ).sources

    _Device_Write(
        installed,
        "fixture.device.pwm_100hz",
        "pwm",
        {"pwm": {"frequency_hz": 100}},
        ["pwm.output_fixed_frequency"],
    )
    catalog = _Catalog_Create(workspace_root, installed)
    model.device_instances[1] = DeviceInstance(
        "pwm1", "fixture.device.pwm_100hz"
    )
    conflict = ResourceAssignments_Resolve(model, catalog)
    assert any("shared-timer frequency conflict" in error for error in conflict.errors)


def test_platform_matching_reports_zero_and_tied_candidates(
    builtin_catalog: PluginCatalog,
) -> None:
    with pytest.raises(PlatformMatchError, match="no compatible"):
        PlatformMatch_Resolve(
            DetectedMcuFacts(
                vendor="STM32",
                part="STM32H743ZIT6",
                family="STM32H7",
                package="LQFP144",
                core="ARM Cortex-M7",
                provider="stm32_cubemx",
            ),
            builtin_catalog,
        )
    official = builtin_catalog.Component_Get("silverstar.mcu.stm32f407vet6")
    assert official.platform is not None

    class MatchCatalog:
        def __init__(self, manifests):
            self.manifests = manifests

        def Type_Get(self, component_type: str):
            return self.manifests if component_type == "mcu" else ()

    duplicate = replace(
        official,
        component_id="fixture.mcu.stm32f407vet6_duplicate",
        name="Duplicate F407",
    )
    facts = DetectedMcuFacts(
        vendor="STM32",
        part="STM32F407VET6",
        family="STM32F4",
        package="LQFP100",
        core="ARM Cortex-M4",
        provider="stm32_cubemx",
    )
    with pytest.raises(PlatformMatchError, match="ambiguous"):
        PlatformMatch_Resolve(facts, MatchCatalog((official, duplicate)))

    family_rule = replace(
        official.platform.match_rules[0],
        exact_part="",
        priority=9999,
        specificity=9999,
    )
    family = replace(
        official,
        component_id="fixture.mcu.stm32f4_family",
        name="Generic F4",
        platform=replace(official.platform, match_rules=(family_rule,)),
    )
    matched = PlatformMatch_Resolve(facts, MatchCatalog((family, official)))
    assert matched.selected.component_id == official.component_id


def test_renderer_uses_virtual_non_f4_platform_binding_without_fixed_symbols() -> None:
    binding = PlatformResourceBinding(
        kind="uart",
        collection="uarts",
        include_header="fixture_h7_uart.h",
        entry_kind="handle",
        id_type="FixtureH7UartId",
        count_symbol="FIXTURE_H7_UART_COUNT",
        table_symbol="s_fixture_h7_uart_handles",
        getter="FixtureH7Resource_UartHandleGet",
    )
    rendered = _PlatformBinding_Render(
        binding,
        [{"c_id": "FIXTURE_H7_UART_4", "handle": "huart4"}],
    )
    assert "FixtureH7Resource_UartHandleGet" in rendered
    assert "FixtureH7UartId" in rendered
    assert "&huart4" in rendered
    assert "Stm32f4" not in rendered
    assert "stm32f4" not in inspect.getsource(_PlatformResources_Render).casefold()


def test_cubemx_import_retains_conditional_hal_source_candidates(
    tmp_path: Path, workspace_root: Path
) -> None:
    fixture = tmp_path / "cubemx_optional_backends"
    shutil.copytree(workspace_root / "tests" / "fixtures" / "cubemx_minimal", fixture)
    ioc = fixture / "MockFlightController.ioc"
    ioc.write_text(
        ioc.read_text(encoding="utf-8")
        + "\n".join(
            (
                "",
                "Mcu.IP8=I2C1",
                "Mcu.IP9=CAN1",
                "Mcu.IP10=TIM3",
                "PB6.Signal=I2C1_SCL",
                "PB7.Signal=I2C1_SDA",
                "PB8.Signal=CAN1_RX",
                "PB9.Signal=CAN1_TX",
                "PC6.Signal=TIM3_CH1",
                "I2C1.ClockSpeed=400000",
                "CAN1.Mode=CAN_MODE_NORMAL",
                "TIM3.Prescaler=83",
                "TIM3.Period=19999",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    hal_source = fixture / "Drivers" / "STM32F4xx_HAL_Driver" / "Src"
    hal_source.mkdir(parents=True)
    for name in (
        "stm32f4xx_hal_i2c.c",
        "stm32f4xx_hal_i2c_ex.c",
        "stm32f4xx_hal_can.c",
        "stm32f4xx_hal_tim.c",
    ):
        (hal_source / name).write_text("/* CubeMX fixture. */\n", encoding="utf-8")

    imported = CubeMxImporter(WorkspacePolicy(tmp_path)).Project_Import(fixture)
    assert {item.kind for item in imported.inventory.i2cs} == {"i2c"}
    assert {item.kind for item in imported.inventory.cans} == {"can_classic"}
    assert imported.inventory.pwms[0].instance == "TIM3_CH1"
    assert any(
        source.endswith("stm32f4xx_hal_i2c.c")
        for source in imported.hardware.build_sources
    )
    assert any(
        source.endswith("stm32f4xx_hal_can.c")
        for source in imported.hardware.build_sources
    )
    assert any(
        path.endswith("STM32F4xx_HAL_Driver/Inc")
        for path in imported.hardware.include_dirs
    )


def test_platform_lock_is_saved_and_legacy_missing_lock_reconciles(
    builtin_catalog: PluginCatalog,
) -> None:
    current = ReferenceProject_Create("PlatformLock", catalog=builtin_catalog)
    platform = builtin_catalog.Component_Get(current.mcu)
    assert current.hardware.platform_component == current.mcu
    assert current.hardware.platform_version == platform.version
    assert current.hardware.platform_manifest_sha256 == platform.ManifestSha256_Get()

    legacy = replace(
        current.hardware,
        platform_component="",
        platform_version="",
        platform_manifest_sha256="",
    )
    current.hardware = legacy
    validation = Project_Validate(current, builtin_catalog)
    assert validation.valid
    assert any(issue.code == "platform_lock" for issue in validation.issues)
    reconciled = ProjectConfiguration_Reconcile(current, builtin_catalog).model
    assert reconciled.hardware.platform_component == reconciled.mcu
    assert reconciled.hardware.platform_manifest_sha256 == (
        builtin_catalog.Component_Get(reconciled.mcu).ManifestSha256_Get()
    )


def test_protocol_split_preserves_reference_source_hashes(
    workspace_root: Path,
) -> None:
    provenance = json.loads(
        (workspace_root / "plugins" / "builtin" / "reference_provenance.json").read_text(
            encoding="utf-8"
        )
    )
    targets = {
        "Protocol/Src/air_protocol.c": (
            "silverstar_protocol_telemetry_air_m0/payload/Protocol/Src/air_protocol.c"
        ),
        "System/Src/system_console.c": (
            "silverstar_core_0_0_9/payload/System/Src/system_console.c"
        ),
        "Protocol/SSLOG/Src/sslog_protocol.c": (
            "silverstar_protocol_logging_sslog_0_0/payload/Protocol/SSLOG/Src/sslog_protocol.c"
        ),
        "Protocol/SSLOG/Src/sslog_records.c": (
            "silverstar_protocol_logging_sslog_0_0/payload/Protocol/SSLOG/Src/sslog_records.c"
        ),
    }
    for source, target in targets.items():
        actual = hashlib.sha256(
            (workspace_root / "plugins" / "builtin" / target).read_bytes()
        ).hexdigest()
        assert actual == provenance["protocol_source_sha256"][source]


def test_decoder_profile_records_hardware_resources_and_three_protocol_locks(
    builtin_catalog: PluginCatalog,
) -> None:
    model = ReferenceProject_Create("DecoderHardware", catalog=builtin_catalog)
    package = LogDecoderProfile_Render(model, builtin_catalog).content
    manifest = LogDecoderPackage_Verify(package)
    with zipfile.ZipFile(io.BytesIO(package)) as archive:
        semantics = json.loads(archive.read("project_semantics.json"))
    assert set(manifest["protocols"]) == {"telemetry", "maintenance", "logging"}
    assert semantics["protocols"] == manifest["protocols"]
    assert semantics["hardware"]["matched_mcu_platform"] == model.mcu
    assert semantics["hardware"]["detected_mcu"] == "STM32F407VET6"
    assert semantics["algorithms"]
    assert any(
        assignment["requirement"] == "imu0:data"
        and assignment["logical_resource"] == "PLATFORM_UART_1"
        for assignment in semantics["resource_assignments"]
    )
