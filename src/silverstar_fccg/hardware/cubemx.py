from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from silverstar_fccg.core.workspace import WorkspacePolicy, WorkspacePolicyError
from silverstar_fccg.project.model import HardwareConfiguration, HardwareResource


class CubeMxImportError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class CubeMxImportResult:
    hardware: HardwareConfiguration
    snapshot_root: Path
    peripherals: tuple[str, ...]
    warnings: tuple[str, ...]


class CubeMxImporter:
    """Validate and copy a generated CubeMX project without executing it."""

    MAX_FILE_COUNT = 20_000
    MAX_TOTAL_SIZE = 512 * 1024 * 1024
    _IGNORED_DIRECTORIES = frozenset(
        {".git", ".svn", "build", "debug", "release", "cmake-build-debug"}
    )
    _ALLOWED_SUFFIXES = frozenset(
        {
            ".c",
            ".h",
            ".s",
            ".ioc",
            ".ld",
            ".txt",
            ".md",
            ".xml",
            ".json",
            ".properties",
            ".project",
            ".mxproject",
        }
    )

    def __init__(self, policy: WorkspacePolicy, cache_root: Path | None = None) -> None:
        self.policy = policy
        self.cache_root = self.policy.Path_Resolve(
            cache_root or (self.policy.root / ".fccg" / "hardware_imports")
        )

    def Project_Import(
        self,
        input_path: Path,
        *,
        expected_mcu: str,
        provider_id: str = "silverstar.hardware_provider.stm32_cubemx",
        risk_acknowledged: bool = False,
    ) -> CubeMxImportResult:
        root, ioc_path = self._Input_Resolve(input_path)
        ioc_text = self._Text_Read(ioc_path)
        actual_mcu = self._Mcu_Get(ioc_text)
        if not self._Mcu_Matches(actual_mcu, expected_mcu):
            raise CubeMxImportError(
                f"CubeMX MCU {actual_mcu!r} does not match selected MCU {expected_mcu!r}"
            )
        self._RtosConflict_Validate(root, ioc_text)
        self._GeneratedLayout_Validate(root)
        source_files = self._SourceFiles_Get(root)
        digest = self._SnapshotDigest_Get(root, source_files)
        snapshot_root = self._Snapshot_Store(root, source_files, digest)
        peripherals = self._Peripherals_Get(ioc_text)
        resources = self._Resources_Get(ioc_text, peripherals)
        capabilities = tuple(
            sorted({f"peripheral.{resource.kind}" for resource in resources})
        )
        warnings = self._Warnings_Get(ioc_text, peripherals)
        prefix = "HardwareGenerated/STM32CubeMX"
        core_source_root = root / "Core" / "Src"
        build_sources = tuple(
            f"{prefix}/{path.relative_to(root).as_posix()}"
            for path in sorted(core_source_root.glob("*.c"))
            if path.name.casefold() not in {"freertos.c", "sysmem.c"}
        )
        include_dirs = (f"{prefix}/Core/Inc",)
        hardware = HardwareConfiguration(
            mode="custom",
            source_kind="manual_import",
            provider=provider_id,
            snapshot_id=digest,
            ioc_file=ioc_path.relative_to(root).as_posix(),
            mcu=actual_mcu,
            capabilities=capabilities,
            resources=resources,
            build_sources=build_sources,
            include_dirs=include_dirs,
            source_digest=digest,
            source_label=root.name,
            risk_acknowledged=risk_acknowledged,
        )
        return CubeMxImportResult(
            hardware=hardware,
            snapshot_root=snapshot_root,
            peripherals=peripherals,
            warnings=warnings,
        )

    def SnapshotRoot_Get(self, snapshot_id: str) -> Path:
        if not re.fullmatch(r"[0-9a-f]{64}", snapshot_id):
            raise CubeMxImportError("Invalid CubeMX snapshot id")
        root = self.policy.Path_Resolve(
            self.cache_root / snapshot_id / "STM32CubeMX", allow_root=False
        )
        if not root.is_dir():
            raise CubeMxImportError(f"CubeMX snapshot is unavailable: {snapshot_id}")
        return root

    def _Input_Resolve(self, input_path: Path) -> tuple[Path, Path]:
        selected = input_path.resolve(strict=False)
        if selected.is_symlink():
            raise CubeMxImportError("CubeMX input symlinks are not accepted")
        if selected.is_file():
            if selected.suffix.casefold() != ".ioc":
                raise CubeMxImportError("Select a CubeMX .ioc file or generated project directory")
            root = selected.parent.resolve()
            ioc_path = selected
        elif selected.is_dir():
            root = selected.resolve()
            ioc_files = sorted(root.glob("*.ioc"))
            if len(ioc_files) != 1:
                raise CubeMxImportError(
                    "CubeMX project directory must contain exactly one root .ioc file"
                )
            ioc_path = ioc_files[0]
        else:
            raise CubeMxImportError(f"CubeMX input does not exist: {selected}")
        return root, ioc_path

    @staticmethod
    def _Text_Read(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as error:
            raise CubeMxImportError(f"Cannot read CubeMX .ioc file: {error}") from error

    @staticmethod
    def _Mcu_Get(ioc_text: str) -> str:
        values: dict[str, str] = {}
        for line in ioc_text.splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
        for key in ("Mcu.CPN", "Mcu.Name", "ProjectManager.DeviceId"):
            if values.get(key):
                return values[key]
        raise CubeMxImportError("CubeMX .ioc does not declare an MCU model")

    @staticmethod
    def _Mcu_Matches(actual: str, expected: str) -> bool:
        actual_token = re.sub(r"[^A-Z0-9]", "", actual.upper())
        expected_token = re.sub(r"[^A-Z0-9]", "", expected.upper())
        if actual_token == expected_token:
            return True
        pattern = "".join("[A-Z0-9]" if char == "X" else re.escape(char) for char in actual_token)
        return bool(re.fullmatch(pattern, expected_token)) or (
            len(actual_token) >= 11 and expected_token.startswith(actual_token[:11])
        )

    @staticmethod
    def _RtosConflict_Validate(root: Path, ioc_text: str) -> None:
        if re.search(r"(?i)(FREERTOS|CMSIS[-_ ]?RTOS)", ioc_text):
            raise CubeMxImportError(
                "SilverStar uses its official FreeRTOS component; CubeMX FreeRTOS/CMSIS-RTOS2 cannot be imported"
            )
        conflict_paths = (
            root / "Middlewares" / "Third_Party" / "FreeRTOS",
            root / "Middlewares" / "Third_Party" / "FreeRTOS-Kernel",
            root / "Core" / "Src" / "freertos.c",
        )
        if any(path.exists() for path in conflict_paths):
            raise CubeMxImportError(
                "CubeMX project contains a second FreeRTOS/CMSIS-RTOS2 implementation"
            )

    @staticmethod
    def _GeneratedLayout_Validate(root: Path) -> None:
        required_directories = (
            root / "Core" / "Inc",
            root / "Core" / "Src",
            root / "Drivers" / "CMSIS",
        )
        missing = [path.relative_to(root).as_posix() for path in required_directories if not path.is_dir()]
        hal_candidates = tuple((root / "Drivers").glob("STM32*xx_HAL_Driver"))
        if not hal_candidates:
            missing.append("Drivers/STM32*xx_HAL_Driver")
        if missing:
            raise CubeMxImportError(
                "CubeMX generated project is incomplete: " + ", ".join(missing)
            )
        if not any(root.rglob("startup_*.s")):
            raise CubeMxImportError("CubeMX project has no startup assembler file")
        if not any(root.rglob("*.ld")):
            raise CubeMxImportError("CubeMX project has no linker script")

    def _SourceFiles_Get(self, root: Path) -> tuple[Path, ...]:
        files: list[Path] = []
        total_size = 0
        for path in root.rglob("*"):
            relative = path.relative_to(root)
            if any(part.casefold() in self._IGNORED_DIRECTORIES for part in relative.parts):
                continue
            if path.is_symlink():
                raise CubeMxImportError(f"CubeMX project symlink rejected: {relative.as_posix()}")
            if not path.is_file():
                continue
            if path.suffix.casefold() not in self._ALLOWED_SUFFIXES:
                continue
            try:
                self.policy.RelativePath_Validate(relative.as_posix())
            except WorkspacePolicyError as error:
                raise CubeMxImportError(
                    f"CubeMX project contains an unsafe path: {relative.as_posix()}"
                ) from error
            total_size += path.stat().st_size
            files.append(path)
            if len(files) > self.MAX_FILE_COUNT:
                raise CubeMxImportError("CubeMX project contains too many files")
            if total_size > self.MAX_TOTAL_SIZE:
                raise CubeMxImportError("CubeMX project is too large to import")
        return tuple(sorted(files, key=lambda item: item.relative_to(root).as_posix().casefold()))

    @staticmethod
    def _SnapshotDigest_Get(root: Path, files: tuple[Path, ...]) -> str:
        digest = hashlib.sha256()
        for path in files:
            relative = path.relative_to(root).as_posix()
            digest.update(relative.encode("utf-8"))
            digest.update(b"\0")
            digest.update(hashlib.sha256(path.read_bytes()).digest())
        return digest.hexdigest()

    def _Snapshot_Store(
        self, root: Path, files: tuple[Path, ...], digest: str
    ) -> Path:
        destination = self.policy.Path_Resolve(
            self.cache_root / digest / "STM32CubeMX", allow_root=False
        )
        if destination.is_dir():
            return destination
        stage = self.policy.StagingDirectory_Create("cubemx-")
        staged_snapshot = stage / "STM32CubeMX"
        try:
            for source in files:
                relative = source.relative_to(root)
                target = staged_snapshot / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            readme = (
                "# HardwareGenerated / STM32CubeMX\n\n"
                "This directory comes from STM32CubeMX. It is not SilverStar generic "
                "Platform or Device source. Regenerating hardware may replace this directory.\n\n"
                "After any hardware change, rebuild and repeat clock, DMA, interrupt, GPIO, "
                "electrical-level and power validation. Vendor-generated code is a controlled "
                "Power-of-Ten deviation; SilverStar adapters and generated glue remain in scope.\n"
            )
            (staged_snapshot / "README.md").write_text(readme, encoding="utf-8", newline="\n")
            metadata = {
                "format_version": 0,
                "provider": "stm32_cubemx",
                "source_label": root.name,
                "source_digest": digest,
            }
            (stage / "import.json").write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            destination.parent.parent.mkdir(parents=True, exist_ok=True)
            if destination.parent.exists():
                self.policy.Tree_Remove(destination.parent)
            os.replace(stage, destination.parent)
            return destination
        except Exception:
            if stage.exists():
                self.policy.Tree_Remove(stage)
            raise

    @staticmethod
    def _Peripherals_Get(ioc_text: str) -> tuple[str, ...]:
        values = {
            match.group(1).strip()
            for match in re.finditer(r"(?m)^Mcu\.IP\d+=(.+)$", ioc_text)
        }
        return tuple(sorted(values, key=CubeMxImporter._NaturalKey_Get))

    @staticmethod
    def _NaturalKey_Get(value: str) -> tuple[str, int, str]:
        match = re.search(r"(\d+)$", value)
        return (
            re.sub(r"\d+$", "", value),
            int(match.group(1)) if match else -1,
            value,
        )

    @staticmethod
    def _Resources_Get(
        ioc_text: str, peripherals: tuple[str, ...]
    ) -> tuple[HardwareResource, ...]:
        resources: list[HardwareResource] = []
        groups = (
            ("uart", ("USART", "UART"), "platform_uart.h", "huart", 3),
            ("spi", ("SPI",), "platform_spi.h", "hspi", 1),
            ("adc", ("ADC",), "platform_adc.h", "hadc", 1),
        )
        for kind, prefixes, header, handle_prefix, limit in groups:
            selected = [item for item in peripherals if item.startswith(prefixes)][:limit]
            for index, peripheral in enumerate(selected):
                suffix_match = re.search(r"(\d+)$", peripheral)
                suffix = suffix_match.group(1) if suffix_match else str(index + 1)
                resources.append(
                    HardwareResource(
                        resource_id=peripheral,
                        kind=kind,
                        metadata={
                            "c_id": f"PLATFORM_{kind.upper()}_{index + 1}",
                            "header": header,
                            "handle": f"{handle_prefix}{suffix}",
                            "logical_index": index,
                            "peripheral": peripheral,
                        },
                    )
                )
        values: dict[str, str] = {}
        for line in ioc_text.splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
        gpio_entries: list[tuple[str, str, str]] = []
        for key, signal in values.items():
            if not key.endswith(".Signal") or not signal.startswith("GPIO_"):
                continue
            pin = key[: -len(".Signal")]
            label = values.get(f"{pin}.GPIO_Label", pin).strip() or pin
            label = re.sub(r"[^A-Za-z0-9_.-]", "_", label)
            if signal.startswith("GPIO_EXTI"):
                kind = "gpio_interrupt"
            elif signal == "GPIO_Output":
                kind = "gpio_output"
            else:
                kind = "gpio_input"
            gpio_entries.append((label, pin, kind))
        for index, (label, pin, kind) in enumerate(sorted(gpio_entries)[:9]):
            macro = re.sub(r"[^A-Za-z0-9_]", "_", label)
            resources.append(
                HardwareResource(
                    resource_id=label,
                    kind=kind,
                    metadata={
                        "c_id": f"PLATFORM_GPIO_{index}",
                        "header": "platform_gpio.h",
                        "port": f"{macro}_GPIO_Port",
                        "pin": f"{macro}_Pin",
                        "logical_index": index,
                        "physical_pin": pin,
                        "irq_enabled": 1 if kind == "gpio_interrupt" else 0,
                    },
                )
            )
        if any(item.startswith("SDIO") or item.startswith("SDMMC") for item in peripherals):
            resources.append(HardwareResource("SDIO", "sdio", {}))
        resources.append(HardwareResource("SYSTEM_TIME", "time", {}))
        return tuple(resources)

    @staticmethod
    def _Warnings_Get(ioc_text: str, peripherals: tuple[str, ...]) -> tuple[str, ...]:
        warnings: list[str] = []
        for label, pattern in (
            ("DMA", r"(?i)DMA"),
            ("NVIC", r"(?i)NVIC"),
            ("GPIO", r"(?i)GPIO"),
        ):
            if not re.search(pattern, ioc_text):
                warnings.append(f"CubeMX configuration does not expose {label} settings")
        for family in ("UART", "SPI", "I2C", "ADC"):
            if not any(item.startswith((family, "USART" if family == "UART" else family)) for item in peripherals):
                warnings.append(f"No {family} peripheral is enabled")
        return tuple(warnings)
