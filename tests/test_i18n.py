from __future__ import annotations

import ast
import json
from pathlib import Path

from silverstar_fccg.core.i18n import Translator
from silverstar_fccg.plugins.catalog import PluginCatalog


_KEY_CALLS = {
    "Text_Get": 0,
    "Text_Register": 1,
    "Title_Register": 1,
    "Placeholder_Register": 1,
    "Group_Create": 0,
}


def _LiteralTranslationKeys_Get() -> set[str]:
    keys: set[str] = set()
    source_root = Path("src/silverstar_fccg")
    for path in source_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            argument_index = _KEY_CALLS.get(node.func.attr)
            if argument_index is None or len(node.args) <= argument_index:
                continue
            argument = node.args[argument_index]
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                keys.add(argument.value)
    return keys


def test_translation_catalogs_have_matching_keys() -> None:
    root = Path("src/silverstar_fccg/i18n")
    zh = json.loads((root / "zh_CN.json").read_text(encoding="utf-8"))
    en = json.loads((root / "en_US.json").read_text(encoding="utf-8"))
    assert set(zh) == set(en)
    assert all(isinstance(value, str) and value for value in zh.values())
    assert all(isinstance(value, str) and value for value in en.values())


def test_every_literal_ui_key_is_translated() -> None:
    translated = Translator("en_US").CatalogKeys_Get()
    missing = _LiteralTranslationKeys_Get() - translated
    assert missing == set()


def test_language_fallback_and_formatting() -> None:
    translator = Translator("zh_CN")
    assert translator.Text_Get("status.project_draft_created", name="Demo").endswith("Demo")
    translator.Language_Set("en_US")
    assert translator.Text_Get("page.board_hardware") == "Hardware Connection"
    assert translator.Text_Get("unknown.stable.code") == "unknown.stable.code"


def test_translation_key_does_not_conflict_with_code_format_value() -> None:
    translator = Translator("zh_CN")
    text = translator.Text_Get(
        "validation.issue_summary",
        code="RESOURCE_CONFLICT",
    )
    assert "RESOURCE_CONFLICT" in text


def test_builtin_algorithm_names_and_descriptions_are_localized(
    builtin_catalog: PluginCatalog,
) -> None:
    expected_names = {
        "silverstar.algorithm.ins.coning2_sculling2": "二阶圆锥补偿 / 二阶划桨补偿",
        "silverstar.algorithm.alignment.gravity_known_yaw": "重力 + 已知航向角对准",
        "silverstar.algorithm.alignment.gravity_mag_triad": "重力/磁场双矢量对准",
        "silverstar.algorithm.alignment.hardware_quat_6axis_known_yaw": (
            "六轴硬件四元数 + 已知航向角对准"
        ),
        "silverstar.algorithm.alignment.hardware_quat_9axis": (
            "九轴硬件四元数取样对准"
        ),
        "silverstar.algorithm.estimator.kf6": "六状态卡尔曼滤波（KF6）",
        "silverstar.flight_logic.landing.baro_imu_window": (
            "气压计 + IMU窗口着陆判定"
        ),
    }
    for component_id, expected_name in expected_names.items():
        manifest = builtin_catalog.Component_Get(component_id)
        assert manifest.DisplayName_Get("zh_CN") == expected_name
        assert manifest.DisplayName_Get("en_US") != expected_name
        assert manifest.Description_Get("zh_CN")
        assert manifest.Description_Get("en_US")
        assert manifest.Description_Get("zh_CN") != manifest.Description_Get("en_US")
