# SilverStar_FCCG GUI style guide

The normative, domain-agnostic specification copied read-only from the reference GUI is [`CXYL_Python_GUI_STYLE_GUIDE.md`](CXYL_Python_GUI_STYLE_GUIDE.md). This file defines FCCG-specific product/workflow invariants only.

- The native product title remains `SilverStar_FCCG`; the current project summary belongs in the header/status area.
- The deep-blue header/left navigation, restrained engineering tables, custom tabs/controls, Light/Dark themes, Simplified Chinese/English catalogs, and bottom task status/progress remain stable.
- Left navigation has exactly four normal pages, in configuration order: Devices, Flight Configuration, Hardware Connection, Build.
- File contains New/Open/Save/Save As/Exit. The one-step New Project dialog asks only for name/output; MCU selection belongs on Devices.
- Plugins contains Manager/Install/Refresh. Technical IDs, digest, provenance, manifest, and ownership details stay in the manager dialog rather than normal navigation.
- Devices shows STM32 MCU and physical `DeviceInstance` combos. Add controls appear only when a real manifest declares `project_max` above the current count. Other Sensors is always visible and uses `StandardCheckBox` for boolean selections.
- Devices displays automatically derived consumed/unused capabilities and ambiguity-only provider choices; it never exposes per-capability enable switches or exclusive/shared resource controls.
- Hardware Connection auto-assigns first and initially shows only Board plus valid/invalid status. Advanced resources and custom CubeMX controls are progressive disclosure. Fixed mappings are labels with physical details; only selectable mappings are combos.
- Flight Configuration renders Strategy/Mode slots dynamically, with Logging directly visible and enabled. Future slots appear only when real manifests exist.
- Build initially shows Build/Clean and tool status; paths and the five advanced checks remain collapsed. A flash action appears only after both the selected Board and Environment declare a validated capability and its required tool is detected; the current plugins expose none.
- There is no Generate page or separate normal Generate/Apply action. Save materializes and verifies the project; Build auto-saves dirty/incomplete projects.
- Ordinary changes do not require Preview. Only dangerous operations show a concise diff and Continue/Cancel decision.
- Resource incompatibility, validation failure, custom-hardware risk, tool absence, and unavailable provider states always have textual explanations in addition to color/icons.
- Advanced resources and advanced build use `CollapsibleSection`; toggling changes body visibility only and never child enabled state. Boolean/multiple controls use `StandardCheckBox` with a visible empty border and blue/white checked state in both themes. Required logs use enabled-looking `LockedCheckBox`; log enables are cell widgets, not item check-state flags.
- Header language/theme controls use `HeaderComboBox`; both the field and popup list retain readable deep-blue header colors in Light and Dark themes.
- Message text, file filters, statuses, tool/configuration labels, and standard dialog buttons use the current translation catalog. Technical diagnostics belong in expandable details rather than the primary localized error message.
- Concrete Device names and Strategy/Mode slots are not branched on in page code. Widgets consume localized view models derived from manifests.
- Every user-visible nontechnical phrase uses a translation key. Technical proper names such as STM32F407, JY901B, KF6, FreeRTOS, SSLOG, GCC, Debug, and Release may remain unchanged.
- GUI classes signal requests or call application services. They do not extract archives, copy payloads, render build files, import hardware directly, or invoke tools.
- Long scans, installs, generation, tool detection, builds, and checks use QRunnable/QThreadPool plus the shared bottom progress state.
- Development/test settings stay repository-local; no user/global GUI settings location is modified.
