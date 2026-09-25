from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout
from qgis.gui import QgsAuthConfigSelect

from . import settings_store


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Window-modal, not application-modal: blocks only its own parent
        # window (this plugin's window, or QGIS's main window if opened
        # directly from the menu) - never the rest of QGIS.
        self.setWindowModality(Qt.WindowModal)
        self.setWindowTitle("Configurer l'authentification OAuth2")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Sélectionnez la configuration d'authentification OAuth2 QGIS à utiliser pour "
            "interroger les API Entrepôt et Stats de la Géoplateforme."
        ))
        self.auth = QgsAuthConfigSelect(self)
        self.auth.setConfigId(settings_store.get_authcfg())
        layout.addWidget(self.auth)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self):
        settings_store.set_authcfg(self.auth.configId())
        super().accept()
