# SilverStar_FCCG GUI style guide

The normative, domain-agnostic specification copied read-only from the reference GUI is [`CXYL_Python_GUI_STYLE_GUIDE.md`](CXYL_Python_GUI_STYLE_GUIDE.md). This file defines FCCG-specific product/workflow invariants only.

- The native product title remains `SilverStar_FCCG`; project name/path belong in Project and status areas.
- The deep-blue header/left navigation, restrained engineering tables, custom tabs/controls, Light/Dark themes, Simplified Chinese/English catalogs, and bottom task status/progress remain stable.
- Left navigation has exactly six normal pages, in device-first order: Project, Devices, Board & Hardware, Flight Configuration, Build, Plugins.
- The one-step New Project dialog asks only for identity/output/version/MCU. It does not duplicate the six-page configuration flow.
- Project shows only project identity, output, version, MCU, automatic Core/OS/Protocol/Environment summary, and concise validity state.
- Devices uses one simple combo per manifest class. It may summarize requirements but never asks for concrete peripheral/pin assignment.
- Board & Hardware auto-assigns first and initially shows only Board plus valid/invalid status. Advanced resources and custom CubeMX controls are progressive disclosure.
- Flight Configuration renders Strategy/Mode slots dynamically, with Logging collapsed by default. Future slots appear only when real manifests exist.
- Build initially shows Build/Clean/Flash and tool status; paths and advanced checks remain collapsed.
- Plugins initially shows installed packages and Install. IDs, source graph, digest, provenance, manifest internals, and ownership data remain details/development information.
- There is no Generate page. A stable global action says Generate Project for a new project and Apply Configuration for an existing one.
- Ordinary changes do not require Preview. Only dangerous operations show a concise diff and Continue/Cancel decision.
- Resource incompatibility, validation failure, custom-hardware risk, tool absence, and unavailable provider states always have textual explanations in addition to color/icons.
- Concrete Device names and Strategy/Mode slots are not branched on in page code. Widgets consume localized view models derived from manifests.
- Every user-visible nontechnical phrase uses a translation key. Technical proper names such as STM32F407, JY901B, KF6, FreeRTOS, SSLOG, GCC, Debug, and Release may remain unchanged.
- GUI classes signal requests or call application services. They do not extract archives, copy payloads, render build files, import hardware directly, or invoke tools.
- Long scans, installs, generation, tool detection, builds, and checks use QRunnable/QThreadPool plus the shared bottom progress state.
- Development/test settings stay repository-local; no user/global GUI settings location is modified.
