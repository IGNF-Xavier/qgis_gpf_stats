"""Period & temporality panel (section 4): a thin Qt shell around
``core.period_service`` - every rule (presets, fine-step eligibility, grain
resolution) lives in the pure-Python module and is unit-tested there.
"""
from __future__ import annotations

from datetime import datetime, timezone

from qgis.PyQt.QtCore import QDateTime, Qt
from qgis.PyQt.QtWidgets import QCheckBox, QComboBox, QDateTimeEdit, QGridLayout, QGroupBox, QLabel

from ..core import period_service as ps
from ..core.models import PeriodConfig


def _qdatetime_to_datetime(value: QDateTime) -> datetime:
    utc_value = QDateTime(value)
    utc_value.setTimeSpec(Qt.UTC)
    return utc_value.toPyDateTime().replace(tzinfo=timezone.utc)


def _datetime_to_qdatetime(value: datetime) -> QDateTime:
    parsed = QDateTime.fromString(ps.iso(value), "yyyy-MM-ddTHH:mm:ss.zzzZ")
    parsed.setTimeSpec(Qt.UTC)
    return parsed


class PeriodPanel(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("Période et temporalité", parent)
        layout = QGridLayout(self)

        self.preset = QComboBox()
        for key, label in ps.PRESETS:
            self.preset.addItem(label, key)

        self.start = QDateTimeEdit()
        self.end = QDateTimeEdit()
        for widget in (self.start, self.end):
            widget.setCalendarPopup(True)
            widget.setDisplayFormat("yyyy-MM-dd HH:mm")

        self.details = QCheckBox("Demander les détails temporels")
        self.details.setChecked(True)
        self.fine = QCheckBox("Pas fin API (5 minutes si disponible)")

        self.grain = QComboBox()
        for key, label in ps.GRAIN_CHOICES:
            self.grain.addItem(label, key)

        self.info = QLabel()
        self.info.setWordWrap(True)

        layout.addWidget(QLabel("Préréglage"), 0, 0)
        layout.addWidget(self.preset, 0, 1)
        layout.addWidget(QLabel("Début"), 0, 2)
        layout.addWidget(self.start, 0, 3)
        layout.addWidget(QLabel("Fin"), 0, 4)
        layout.addWidget(self.end, 0, 5)
        layout.addWidget(self.details, 1, 0, 1, 2)
        layout.addWidget(self.fine, 1, 2, 1, 2)
        layout.addWidget(QLabel("Regroupement analytique"), 1, 4)
        layout.addWidget(self.grain, 1, 5)
        layout.addWidget(self.info, 2, 0, 1, 6)

        self.preset.currentIndexChanged.connect(self._apply_preset)
        self.start.dateTimeChanged.connect(self._refresh_info)
        self.end.dateTimeChanged.connect(self._refresh_info)
        self.fine.toggled.connect(self._refresh_info)
        self._apply_preset()

    def _apply_preset(self) -> None:
        key = self.preset.currentData()
        if key == "custom":
            self._refresh_info()
            return
        now = datetime.now(timezone.utc)
        start, end = ps.compute_preset_range(key, now)
        self.start.blockSignals(True)
        self.end.blockSignals(True)
        self.start.setDateTime(_datetime_to_qdatetime(start))
        self.end.setDateTime(_datetime_to_qdatetime(end))
        self.start.blockSignals(False)
        self.end.blockSignals(False)
        self._refresh_info()

    def _refresh_info(self) -> None:
        start = _qdatetime_to_datetime(self.start.dateTime())
        end = _qdatetime_to_datetime(self.end.dateTime())
        duration = ps.duration_days(start, end)
        allowed = ps.fine_step_allowed(duration)
        self.fine.setEnabled(allowed)
        if not allowed and self.fine.isChecked():
            self.fine.setChecked(False)
        message = f"Période demandée : {duration} jour(s). "
        message += (
            "Le pas fin de 5 minutes peut être demandé."
            if allowed
            else f"Le pas fin est désactivé : il est réservé aux {ps.FINE_STEP_MAX_DAYS} jours au plus."
        )
        self.info.setText(message)

    def build_config(self) -> PeriodConfig:
        start = _qdatetime_to_datetime(self.start.dateTime())
        end = _qdatetime_to_datetime(self.end.dateTime())
        return ps.build_period_config(
            preset=self.preset.currentData(),
            start=start,
            end=end,
            details_requested=self.details.isChecked(),
            fine_requested=self.fine.isChecked(),
            grain_choice=self.grain.currentData(),
        )
