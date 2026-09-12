from copy import deepcopy
import hashlib
from io import BytesIO
import json
from pathlib import Path
import struct
import zipfile

import pytest

from algorithm_parameters_support import Trajectory_Run
from silverstar_fccg.app.service import FccgService
from silverstar_fccg.core.settings import SettingsStore
from silverstar_fccg.core.workspace import WorkspacePolicy
from silverstar_fccg.generator.log_decoder_profile import LogDecoderPackage_Verify, _AlgorithmParameters_Validate
from silverstar_fccg.generator.render import LogDecoderProfile_Render
from silverstar_fccg.plugins.algorithm_parameters import AlgorithmParameters_Parse
from silverstar_fccg.project.algorithm_parameters import AlgorithmParameters_Resolve, AlgorithmParametersHeader_Render
from silverstar_fccg.project.configuration import ProjectConfiguration_Reconcile
from silverstar_fccg.project.generation_state import ProjectGenerationFingerprint_Get
from silverstar_fccg.project.model import ProjectModel_Parse
from silverstar_fccg.project.reference import ReferenceProject_Create
from silverstar_fccg.project.validation import Project_Validate
from silverstar_fccg.ui.main_window import MainWindow
from silverstar_fccg.ui.widgets import CollapsibleSection

INS = 'silverstar.algorithm.ins.coning2_sculling2'
KF = 'silverstar.algorithm.estimator.kf6'


def test_actual_defaults_roundtrip_and_decoder(builtin_catalog):
    model = ReferenceProject_Create(catalog=builtin_catalog)
    assert model.format_version == 12
    assert model.algorithm_parameters[INS] == {'gravity_mps2':9.78}
    values = model.algorithm_parameters[KF]
    assert values['p0_position_u'] == 9.0
    assert values['process_accel_std_u'] == 2.0
    assert values['gnss_velocity_std'] == 0.15
    assert values['baro_std_m'] == 5.0
    assert len(values) == 21
    assert ProjectModel_Parse(model.Dictionary_Get()).algorithm_parameters == model.algorithm_parameters
    sets = AlgorithmParameters_Resolve(model, builtin_catalog)
    assert {p['component'] for p in sets} == {INS,KF}
    gravity = sets[0]['parameters'][0]
    assert gravity['value'] == struct.unpack('<f',struct.pack('<f',9.78))[0]
    package = LogDecoderProfile_Render(model, builtin_catalog)
    assert LogDecoderPackage_Verify(package.content)['package_schema']['minor'] == 2
    with zipfile.ZipFile(BytesIO(package.content)) as archive:
        semantics = json.loads(archive.read('project_semantics.json'))
    assert semantics['schema_id'] == 'silverstar.project-semantics/1.2'
    assert semantics['firmware_algorithm_parameters'] == sets
    assert all(p['representation'] == 'sigma' for p in sets[1]['parameters'] if '_std' in p['id'])


@pytest.mark.parametrize('value',[float('nan'),float('inf'),-1.,0.,10000001.,True,'5'])
def test_invalid_actual_value_blocks_strict_generation(builtin_catalog,value):
    model=ReferenceProject_Create(catalog=builtin_catalog)
    model.algorithm_parameters[KF]['baro_std_m']=value
    assert not Project_Validate(model,builtin_catalog).valid
    with pytest.raises((ValueError,TypeError)):
        AlgorithmParametersHeader_Render(model,builtin_catalog)


def test_selection_lifecycle_unknown_ids_and_nis_order(builtin_catalog):
    model=ReferenceProject_Create(catalog=builtin_catalog)
    model.algorithm_parameters[KF]['unknown']=5.
    reconciled=ProjectConfiguration_Reconcile(model,builtin_catalog).model
    assert 'unknown' in reconciled.algorithm_parameters[KF]
    assert not Project_Validate(reconciled,builtin_catalog).valid
    slot=next(slot for slot,value in model.strategies.items() if value==KF)
    model.strategies[slot]=None
    model=ProjectConfiguration_Reconcile(model,builtin_catalog).model
    assert KF not in model.algorithm_parameters
    assert KF not in {s['component'] for s in AlgorithmParameters_Resolve(model,builtin_catalog)}
    model.strategies[slot]=KF
    model=ProjectConfiguration_Reconcile(model,builtin_catalog).model
    assert model.algorithm_parameters[KF]['baro_std_m']==5.
    model.algorithm_parameters[KF]['nis_1d_hard']=model.algorithm_parameters[KF]['nis_1d_soft']
    with pytest.raises(ValueError,match='must exceed'):
        AlgorithmParameters_Resolve(model,builtin_catalog)


@pytest.mark.parametrize('mutation',[
    lambda p:p.update(extra=True),lambda p:p.update(default=0),
    lambda p:p.update(default=float('nan')),lambda p:p.update(default=True),
    lambda p:p.update(representation='multiplier'),lambda p:p.update(step=0),
    lambda p:p.update(precision=-1),lambda p:p.update(greater_than='missing'),
    lambda p:p.update(generated_symbol='bad;symbol'),
])
def test_parameter_schema_rejects_invalid_declarations(builtin_catalog,mutation):
    manifest=builtin_catalog.Component_Get(INS)
    document=json.loads(manifest.manifest_path.read_text(encoding='utf-8'))['algorithm_parameters']
    mutation(document['parameters'][0])
    with pytest.raises(ValueError): AlgorithmParameters_Parse(document)


def test_duplicate_schema_parameters_rejected(builtin_catalog):
    manifest=builtin_catalog.Component_Get(INS)
    document=json.loads(manifest.manifest_path.read_text(encoding='utf-8'))['algorithm_parameters']
    document['parameters'].append(deepcopy(document['parameters'][0]))
    with pytest.raises(ValueError,match='Duplicate'): AlgorithmParameters_Parse(document)


def test_decoder_rejects_11_and_invalid_resolved_metadata(builtin_catalog):
    model=ReferenceProject_Create(catalog=builtin_catalog)
    package=LogDecoderProfile_Render(model,builtin_catalog)
    with zipfile.ZipFile(BytesIO(package.content)) as archive:
        files={n:archive.read(n) for n in archive.namelist()}
    semantics=json.loads(files['project_semantics.json'])
    bad=deepcopy(semantics)
    bad['firmware_algorithm_parameters'][0]['parameters'][0]['value']=9.78
    with pytest.raises(ValueError,match='resolved float32'): _AlgorithmParameters_Validate(bad)
    bad=deepcopy(semantics)
    bad['firmware_algorithm_parameters'][0]['component']='offline.unselected'
    with pytest.raises(ValueError): _AlgorithmParameters_Validate(bad)
    bad=deepcopy(semantics)
    bad['component_locks']=[]
    bad['firmware_algorithm_parameters'][0]['manifest_sha256']=None
    with pytest.raises(ValueError): _AlgorithmParameters_Validate(bad)
    manifest=json.loads(files['manifest.json'])
    manifest['package_schema']={'id':'silverstar.ssdecoder.package-schema/1.1','major':1,'minor':1}
    files['manifest.json']=(json.dumps(manifest,sort_keys=True,separators=(',',':'))+'\n').encode()
    files['checksums.sha256']=''.join(f'{hashlib.sha256(value).hexdigest()}  {key}\n' for key,value in sorted(files.items()) if key!='checksums.sha256').encode()
    out=BytesIO()
    with zipfile.ZipFile(out,'w') as archive:
        for name,value in files.items():archive.writestr(name,value)
    with pytest.raises(ValueError): LogDecoderPackage_Verify(out.getvalue())


def test_gui_page_edit_reset_dirty_and_readonly_display(tmp_path,qapp,monkeypatch):
    window=MainWindow(SettingsStore(tmp_path/'parameters.ini'))
    monkeypatch.setattr(window,'_Error_Show',lambda *args:pytest.fail(str(args)))
    try:
        assert window.PAGE_CODES.index('page.algorithm_parameters')+1 == window.PAGE_CODES.index('page.board_hardware')
        assert window.pages.count()==5
        old=window._model.Dictionary_Get()
        window._Project_Refresh()
        assert window._model.Dictionary_Get()==old
        editor=window.algorithm_parameters_page.editors[(INS,'gravity_mps2')]
        editor.setValue(9.81)
        qapp.processEvents()
        assert window._model.algorithm_parameters[INS]['gravity_mps2']==9.81
        assert 'dirty' in window._project_state.value.lower()
        sections = window.algorithm_parameters_page._content.findChildren(CollapsibleSection)
        advanced = next(section for section in sections if not section.Expanded_Is())
        advanced.toggle_button.setChecked(True)
        window._Project_Refresh()
        assert all(section.Expanded_Is() for section in window.algorithm_parameters_page._content.findChildren(CollapsibleSection))
        window._AlgorithmDefaults_Reset(INS)
        assert window._model.algorithm_parameters[INS]['gravity_mps2']==9.78
    finally:
        window._project_state=type(window._project_state).DRAFT
        window.close()


def test_generated_defaults_numerically_identical_and_changed_values_consumed(tmp_path,workspace_root):
    if not Path(r'D:\msys64\ucrt64\bin\gcc.exe').is_file():
        pytest.skip('Reference golden compiler unavailable')
    service=FccgService(workspace_root)
    model=service.ReferenceProject_Create('AlgorithmGolden')
    project=tmp_path/'generated'
    service.Project_Save(model,project,confirm_dangerous=True)
    baseline=Trajectory_Run(project,workspace_root)
    expected=json.loads((workspace_root/'tests/fixtures/algorithm_parameters_golden.json').read_text())
    assert hashlib.sha256(baseline).hexdigest()==expected['trajectory_sha256']
    old_fingerprint=ProjectGenerationFingerprint_Get(model)
    model.algorithm_parameters[INS]['gravity_mps2']=9.81
    model.algorithm_parameters[KF]['p0_position_e']=8.
    model.algorithm_parameters[KF]['process_accel_std_u']=3.
    model.algorithm_parameters[KF]['gnss_velocity_std']=.3
    model.algorithm_parameters[KF]['baro_std_m']=6.
    assert ProjectGenerationFingerprint_Get(model)!=old_fingerprint
    service.Project_Save(model,project,confirm_dangerous=True)
    changed=Trajectory_Run(project,workspace_root)
    assert changed!=baseline
    saved=service.Project_Open(project/'SilverStar.ssproject')
    assert saved.algorithm_parameters==model.algorithm_parameters
    destination=tmp_path/'saved-as'
    service.Project_SaveAs(saved,project,destination,confirm_dangerous=True)
    copied=service.Project_Open(destination/'SilverStar.ssproject')
    assert copied.algorithm_parameters==model.algorithm_parameters
