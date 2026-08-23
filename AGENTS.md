# SilverStar_FCCG agent guidance

SilverStar_FCCG is the SilverStar Flight Controller Code Generator: a graphical project
configurator, declarative component-plugin manager, project assembler, minimal glue generator,
and build/toolchain front end.

## Safety boundary

All writes made while developing or testing FCCG must remain below this repository root.
Codex or other automation working on FCCG may read, but must never modify, rename, delete,
format, commit, or otherwise write to the reference firmware, reference GUI, or any path outside
the FCCG workspace. Tests must place all temporary and generated outputs below `tests/`.

Reference sources are always read-only:

- firmware: `C:\Users\chdxm\Desktop\stm32-1\Flight_Controller0.5`
- GUI: `D:\python_software\SilverStar_FLP`

Do not modify the system/user PATH, registry, global application settings, global Python
environment, or any other repository. Project-local settings and logs belong below `.fccg/`.

## Architecture and ownership

- Plugins are declarative source packages. Installing a plugin must never execute plugin code.
- Component payloads copied into an embedded project become ordinary project-owned source and
  normal Apply Configuration operations must not overwrite them.
- Only a deliberately small `Generated/` glue surface remains FCCG-owned and replaceable.
- `SilverStar.ssproject` is strict JSON and, together with installed manifests, is the single
  source of truth for Make, VS Code, and supported EIDE configuration.
- GUI widgets call application/domain services; they do not copy files, parse plugin archives,
  modify build files, or run toolchains directly.
- All copy, extraction, replacement, and deletion operations pass through the workspace/path
  safety layer and use validation plus staging before apply.
- Configuration follows MCU → Device → Board/Hardware → Flight Configuration. Device manifests
  declare requirements; Board/imported hardware resolves them; the MCU plugin remains PCB-neutral.
- Strategy and Mode slots are generic manifest-declared dictionaries. Do not add hard-coded future
  Guidance/Control/Actuator choices without real plugins and source.
- Imported vendor configuration remains below `HardwareGenerated/STM32CubeMX/`. It is neither
  SilverStar Platform source nor FCCG-generated glue, and replacement always requires a dangerous
  plan confirmation.
- Make and native EIDE must be rendered from the same resolved source graph. VS Code tasks call the
  generated Make project; no environment renderer may independently discover sources.

## GUI standard

All PySide6 UI work follows `docs/GUI_STYLE_GUIDE.md` and the copied normative
`docs/CXYL_Python_GUI_STYLE_GUIDE.md`. Preserve the stable product title, deep-blue header and
left navigation, Light/Dark themes, Simplified Chinese/English catalogs, custom tab/table/control
styling, bottom task status/progress, and QRunnable/QThreadPool background work. Keep exactly the
six normal pages defined in the GUI guide and no standalone Generate page. User-visible strings
use translation keys. Development settings remain repository-local.

## Code and tests

Keep modules focused and typed. Follow the project naming convention for callable interfaces:
noun followed by a capitalized verb phrase, for example `Project_Load` and `Theme_Apply`.
Run focused tests, then the complete suite. Do not claim toolchain, EIDE, flash, or hardware
support unless the corresponding validation actually passed.
