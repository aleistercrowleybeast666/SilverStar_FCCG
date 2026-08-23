# Changelog

## Unreleased — 2026-08-23

- Reimported the latest clean SilverStar 0.0.9 reference at `b8c90e997c3113dd23074302682c5560dae18926` into 23 declarative builtins with path/commit/branch/status/digest provenance.
- Replaced fixed Algorithm/Flight lists with generic manifest-driven Strategy and Mode slots; added four Alignment strategies and real Estimator=None source exclusion.
- Added formal MCU/Board/Device resource responsibilities, Board defaults/candidates/fixed/reserved/conflicts, compatibility filtering, and device-first auto-assignment.
- Added the trusted STM32CubeMX hardware provider: `.ioc`/directory validation, MCU/RTOS/layout/peripheral checks, isolated `HardwareGenerated/STM32CubeMX/` snapshots, risk state, dangerous reimport, and local Board `.ssplugin` export/reuse.
- Added the DevelopmentEnvironment plugin and one resolved source graph for Make, native non-empty EIDE, and VS Code workspace/tasks.
- Reduced the normal GUI from ten pages/wizard steps to six pages plus a one-step identity dialog; merged Algorithm/Flight/Mode/Logging configuration and removed the standalone Generate page/mandatory Preview workflow.
- Expanded Simplified Chinese/English catalogs and added six-page Chinese GUI coverage.
- Updated generated Make with forced includes, source exclusions, first-party/vendor warning boundaries, Power of Ten, static analysis, and artifact tasks.
- Added acceptance fixtures/tests for two Boards on one MCU, Estimator=None, environment graph equivalence, CubeMX import/RTOS rejection, custom project generation, and Board export/install/reuse.

## 0.0.1 — 2026-08-21

- Created the independent PySide6 FCCG application, strict project/plugin models, secure installer, staged assembler, project-owned component preservation, thin generated glue, editor metadata, toolchain front end, and initial F407 acceptance project.
