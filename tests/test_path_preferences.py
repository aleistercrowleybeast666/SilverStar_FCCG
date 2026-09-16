import json
from pathlib import Path

from silverstar_fccg.core.i18n import Translator
from silverstar_fccg.core.path_preferences import PathPreferences
from silverstar_fccg.core.workspace import WorkspacePolicy
from silverstar_fccg.ui.dialogs.new_project import NewProjectWizard


def test_json_preferences_and_invalid_fallback(tmp_path):
    store = PathPreferences(WorkspacePolicy(tmp_path), tmp_path / ".fccg/path_preferences.json")
    assert store.DefaultProjectRoot_Get() is None
    root = tmp_path / "中文工程 Space"
    root.mkdir()
    store.DefaultProjectRoot_Set(root)
    assert store.DefaultProjectRoot_Get() == root
    assert json.loads(store.path.read_text(encoding="utf-8"))["schema_version"] == 1
    for text in ("{", "[]", '{"schema_version":1,"default_project_root":null}',
                 '{"schema_version":1,"default_project_root":"missing"}'):
        store.path.write_text(text, encoding="utf-8")
        assert store.DefaultProjectRoot_Get() is None


def test_wizard_auto_name_manual_and_browse(qapp, tmp_path, monkeypatch):
    wizard = NewProjectWizard(Translator("zh_CN"), default_root=tmp_path)
    form = wizard.identity_page
    form.name_edit.setText("试验 一")
    assert Path(form.output_edit.text()) == tmp_path / "试验 一"
    form.name_edit.setText("试验 二")
    assert Path(form.output_edit.text()) == tmp_path / "试验 二"
    custom = tmp_path / "自选"
    custom.mkdir()
    form.output_edit.setText(str(custom))
    form.output_edit.textEdited.emit(str(custom))
    form.name_edit.setText("新名称")
    assert Path(form.output_edit.text()) == custom
    calls = []
    def select(*args):
        calls.append(args[2])
        return str(tmp_path)
    monkeypatch.setattr("silverstar_fccg.ui.dialogs.new_project.QFileDialog.getExistingDirectory", select)
    form._Output_Browse()
    form.name_edit.setText("再次修改")
    assert Path(calls[0]) == custom
    assert Path(wizard.WizardData_Get()["output_directory"]) == tmp_path
    wizard.close()
