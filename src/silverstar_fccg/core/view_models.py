from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class ComponentType(StrEnum):
    CORE = "core"
    MCU = "mcu"
    BOARD = "board"
    DEVICE = "device"
    ALGORITHM = "algorithm"
    FLIGHT_LOGIC = "flight_logic"
    OS = "os"
    PROTOCOL_BUNDLE = "protocol_bundle"
    HARDWARE_CONFIGURATION_PROVIDER = "hardware_configuration_provider"
    DEVELOPMENT_ENVIRONMENT = "development_environment"


@dataclass(frozen=True, slots=True)
class ResourceRequirementView:
    kind: str
    name: str
    key: str = ""
    assignment: str = ""
    candidates: tuple[str, ...] = ()
    required: bool = True
    mode: str = "exclusive"


@dataclass(frozen=True, slots=True)
class ComponentView:
    component_id: str
    name: str
    component_type: ComponentType
    version: str
    component_class: str = ""
    description: str = ""
    source: str = ""
    status: str = "available"
    dependencies: tuple[str, ...] = ()
    provides: tuple[str, ...] = ()
    requirements: tuple[ResourceRequirementView, ...] = ()
    options: dict[str, Any] = field(default_factory=dict)
    selection_kind: str = ""
    selection_slot: str = ""
    selection_options: tuple[str, ...] = ()
    selection_default: tuple[str, ...] = ()
    allow_none: bool = False
    allow_multiple: bool = False
    ui_order: int = 100
    board_source_kind: str = ""
    board_verified: bool = False
    compatible_mcus: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class BoardCompatibilityView:
    component_id: str
    name: str
    compatible: bool
    missing_text: str = ""
    detail: str = ""


@dataclass(frozen=True, slots=True)
class ToolchainToolView:
    tool_id: str
    display_name: str
    command: str
    path: str = ""
    version: str = ""
    status: str = "not_checked"


@dataclass(frozen=True, slots=True)
class LoggingStreamView:
    stream_id: str
    name: str
    enabled: bool
    decimation: int = 1
    rate_text: str = ""
    description: str = ""
    policy: str = ""
    period_us: int = 0


@dataclass(frozen=True, slots=True)
class PlanOperationView:
    operation: str
    target: str
    detail: str = ""
    severity: str = "info"


@dataclass(slots=True)
class ProjectDraftView:
    name: str = ""
    output_directory: Path | None = None
    firmware_version: str = "0.0.9"
    core_component_id: str = ""
    selected_component_ids: list[str] = field(default_factory=list)
    resource_assignments: dict[str, str] = field(default_factory=dict)
    logging: dict[str, dict[str, Any]] = field(default_factory=dict)
    toolchain: dict[str, str] = field(default_factory=dict)
    status: str = "not_created"
