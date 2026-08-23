from __future__ import annotations

import ast
import json
from pathlib import Path

from silverstar_fccg.core.i18n import Translator


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
    assert translator.Text_Get("page.board_hardware") == "Board & Hardware"
    assert translator.Text_Get("unknown.stable.code") == "unknown.stable.code"
