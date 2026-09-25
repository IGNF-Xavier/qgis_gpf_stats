from qgis.PyQt.QtWidgets import QAction

from .ui.main_dialog import MainDialog
from .ui.settings_dialog import SettingsDialog

MENU = "Statistiques analytiques Géoplateforme"


class Plugin:
    def __init__(self, iface):
        self.iface = iface
        self.actions = []
        self._main_dialog = None

    def initGui(self):
        for label, slot in (
            ("Ouvrir…", self._open_main_dialog),
            ("Configurer OAuth2…", lambda: SettingsDialog(self.iface.mainWindow()).exec()),
        ):
            action = QAction(label, self.iface.mainWindow())
            action.triggered.connect(slot)
            self.iface.addPluginToMenu(MENU, action)
            self.actions.append(action)

    def _open_main_dialog(self) -> None:
        # Non-modal and kept alive on the plugin instance: the window stays
        # open (and its catalog/results in memory) while the rest of QGIS
        # remains fully usable, instead of blocking it behind a modal exec().
        if self._main_dialog is None:
            self._main_dialog = MainDialog(self.iface, self.iface.mainWindow())
        self._main_dialog.show()
        self._main_dialog.raise_()
        self._main_dialog.activateWindow()

    def unload(self):
        for action in self.actions:
            try:
                self.iface.removePluginMenu(MENU, action)
                action.deleteLater()
            except RuntimeError:
                pass
        self.actions = []
        if self._main_dialog is not None:
            self._main_dialog.close()
            self._main_dialog.deleteLater()
            self._main_dialog = None
