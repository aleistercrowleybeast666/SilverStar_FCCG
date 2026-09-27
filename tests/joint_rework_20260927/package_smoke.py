"""Offline smoke of the exported source package, with no hardware access."""
from pathlib import Path
import json
import os
import subprocess
import sys
import time

root = Path(__file__).resolve().parents[2]
package = root / "tests/.pkg28"
output = root / "tests/joint_rework_20260927/package_delivery"
environment = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_SCALE_FACTOR="2",
                   PYTHONPATH=str(package / "src"), PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
with (output / "startup.stdout.log").open("w", encoding="utf-8") as stdout, (output / "startup.stderr.log").open("w", encoding="utf-8") as stderr:
    process = subprocess.Popen([sys.executable, str(package / "main.py"), "--lang", "zh_CN", "--theme", "dark"],
                               cwd=package, env=environment, stdout=stdout, stderr=stderr,
                               creationflags=subprocess.CREATE_NO_WINDOW)
    time.sleep(8)
    alive = process.poll() is None
    if alive:
        process.terminate()
    process.wait(timeout=15)
assert alive, "Exported product exited unexpectedly during offline startup"
assert "Traceback" not in (output / "startup.stderr.log").read_text(encoding="utf-8")

os.environ.update(environment)
sys.path.insert(0, str(package / "src"))
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication
from silverstar_fccg.app.service import FccgService
from silverstar_fccg.app.version import __version__
from silverstar_fccg.core.settings import SettingsStore
from silverstar_fccg.project.logging import LoggingProfile_AvailabilityTransitionApply
from silverstar_fccg.ui.main_window import MainWindow
from copy import deepcopy

service = FccgService(package)
plugins = service.catalog.All_Get()
assert len(plugins) == 65
for component in ("silverstar.algorithm.estimator.eskf15", "silverstar.device.imu.bmi088_spi",
                  "silverstar.device.imu.bmi088_sync400", "silverstar.device.imu.bmi088_sync400_spi",
                  "silverstar.device.imu.lsm6dsv320x", "silverstar.device.gnss.neo_f10n"):
    assert service.catalog.Component_Get(component).build.sources
application = QApplication([])
font = QFontDatabase.addApplicationFont("C:/Windows/Fonts/msyh.ttc")
if font >= 0:
    application.setFont(QFont(QFontDatabase.applicationFontFamilies(font)[0], 10))
screenshots = []
for theme in ("light", "dark"):
    for language in ("en_US", "zh_CN"):
        window = MainWindow(SettingsStore(package / ".fccg" / (theme + language + ".ini")),
                            service=service, theme=theme, language=language)
        model = service.ReferenceProject_Create("OfflineESKF15")
        previous = deepcopy(model)
        model.strategies["estimator"] = "silverstar.algorithm.estimator.eskf15"
        LoggingProfile_AvailabilityTransitionApply(previous, model, service.catalog)
        window._model = service.ProjectConfiguration_Reconcile(model).model
        window._Project_Refresh()
        window.resize(1000, 700)
        window.show()
        window.navigation_list.setCurrentRow(2)
        application.processEvents()
        image = window.grab()
        name = f"algorithm_1000x700_200dpi_{theme}_{language}.png"
        assert image.save(str(output / name))
        assert image.width() == 2000 and image.height() == 1400
        screenshots.append(name)
        window.hide()
        window.deleteLater()
        application.processEvents()
(output / "smoke.json").write_text(json.dumps({"version": __version__, "plugins": len(plugins),
    "startup_alive_seconds": 8, "startup_traceback": False, "offline": True,
    "logical_size": [1000, 700], "device_pixel_ratio": 2, "screenshots": screenshots}, indent=2), encoding="utf-8")
print((output / "smoke.json").read_text(encoding="utf-8"))
