"""Non-modal glossary / help panel: definitions of the domain objects
(offering, datastore, endpoint, permission, group, analysis level, coverage
status). Kept open while the user browses the rest of the window.
"""
from __future__ import annotations

from qgis.PyQt.QtWidgets import QDialog, QLabel, QScrollArea, QVBoxLayout, QWidget

from ..core.glossary import GLOSSARY


class GlossaryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Glossaire — Statistiques analytiques Géoplateforme")
        self.setModal(False)
        self.resize(620, 560)

        root = QVBoxLayout(self)
        intro = QLabel(
            "Définitions des objets manipulés par le plugin. Cette fenêtre reste ouverte "
            "pendant que vous utilisez le reste de l'application."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        for term, definition in GLOSSARY:
            title = QLabel(f"<b>{term}</b>")
            body = QLabel(definition)
            body.setWordWrap(True)
            content_layout.addWidget(title)
            content_layout.addWidget(body)
            content_layout.addSpacing(8)
        content_layout.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll, 1)
