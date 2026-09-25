"""Visible progress panel for long operations (sections 2.1, 2.2, 3).

Purely a passive view: it renders ``ProgressEvent`` objects emitted by a
``QgsTask`` worker and forwards ``Annuler`` to ``task.cancel()``. It never
touches the network or the catalog/stats services directly.
"""
from __future__ import annotations

from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QProgressBar,
    QVBoxLayout,
)


def _format_elapsed(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes:02d}:{secs:02d}"


class ProgressDialog(QDialog):
    def __init__(self, title: str, task, parent=None):
        super().__init__(parent)
        self._task = task
        self._counts = {"offerings_count": 0, "endpoints_count": 0, "permissions_count": 0}
        self.setWindowTitle(title)
        self.resize(560, 420)
        # Non-modal: the rest of QGIS (canvas, other panels, other plugins)
        # stays fully usable while this operation runs in the background.
        self.setModal(False)

        layout = QVBoxLayout(self)
        self.stage_label = QLabel("En attente…")
        self.stage_label.setWordWrap(True)
        layout.addWidget(self.stage_label)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        layout.addWidget(self.bar)

        self.counters_label = QLabel()
        layout.addWidget(self.counters_label)
        self.elapsed_label = QLabel("Temps écoulé : 00:00")
        layout.addWidget(self.elapsed_label)

        layout.addWidget(QLabel("Journal :"))
        self.log = QListWidget()
        layout.addWidget(self.log, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        buttons.rejected.connect(self._cancel)
        layout.addWidget(buttons)

        task.stepProgress.connect(self.on_progress)

    def _cancel(self) -> None:
        self._task.cancel()
        self.stage_label.setText("Annulation en cours…")

    def closeEvent(self, event) -> None:
        # Closing the window (native X, or a completed task calling accept()/
        # reject()) always requests cancellation too - harmless if the task
        # already finished, and avoids leaving an orphaned task with no
        # visible way to stop it once its progress window is gone.
        self._task.cancel()
        super().closeEvent(event)

    def on_progress(self, event, elapsed: float) -> None:
        self.stage_label.setText(event.message)
        if event.total:
            self.bar.setRange(0, event.total)
            self.bar.setValue(event.current)
        else:
            self.bar.setRange(0, 0)
        self.elapsed_label.setText(f"Temps écoulé : {_format_elapsed(elapsed)}")

        if event.stage == "datastore_done":
            for key in self._counts:
                self._counts[key] += event.extra.get(key, 0)
            self.counters_label.setText(
                f"Offerings récupérés : {self._counts['offerings_count']} · "
                f"Endpoints récupérés : {self._counts['endpoints_count']} · "
                f"Permissions récupérées : {self._counts['permissions_count']}"
            )

        if event.stage in ("datastore", "datastore_error", "datastore_done", "connect", "build"):
            self.log.addItem(event.message)
            self.log.scrollToBottom()
        if event.stage == "datastore_error":
            self.log.item(self.log.count() - 1).setForeground(QColor("#990000"))
