"""Chart widgets for the dashboard tab (section 6.2).

Tries Qt Charts first (nicer rendering, native to Qt/PyQt) and transparently
falls back to a small QPainter-based renderer when the ``QtChart`` module
is not part of the QGIS/PyQt install - the dashboard must keep working
either way, with no extra embedded dependency (section 6.2 requirement).
"""
from __future__ import annotations

from qgis.PyQt.QtCore import QPointF, QRectF, Qt
from qgis.PyQt.QtGui import QColor, QFont, QPainter, QPen
from qgis.PyQt.QtWidgets import QLabel, QSizePolicy, QWidget

try:
    from qgis.PyQt.QtChart import QBarCategoryAxis, QBarSeries, QBarSet, QChart, QChartView, QLineSeries, QPieSeries, QValueAxis

    QTCHART_AVAILABLE = True
except ImportError:
    QTCHART_AVAILABLE = False

PALETTE = ["#1F4E78", "#F4B183", "#93C47D", "#8E7CC3", "#E06666", "#76A5AF", "#FFD966", "#C27BA0"]


def _empty_label(message: str = "Aucune donnée à afficher.") -> QWidget:
    label = QLabel(message)
    label.setAlignment(Qt.AlignCenter)
    label.setStyleSheet("color: #777777; font-style: italic;")
    return label


class _FallbackLineChart(QWidget):
    def __init__(self, series: list[tuple[str, int]], title: str, y_label: str, parent=None):
        super().__init__(parent)
        self._series = series
        self._title = title
        self._y_label = y_label
        self.setMinimumHeight(260)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(50, 30, -20, -40)
        painter.setFont(QFont(self.font().family(), 9, QFont.Bold))
        painter.drawText(self.rect().adjusted(0, 4, 0, 0), Qt.AlignHCenter | Qt.AlignTop, self._title)
        if not self._series:
            painter.drawText(rect, Qt.AlignCenter, "Aucune donnée")
            return
        values = [v for _, v in self._series]
        max_value = max(values) or 1
        painter.setPen(QPen(QColor("#CCCCCC")))
        painter.drawRect(rect)
        step_x = rect.width() / max(1, len(self._series) - 1) if len(self._series) > 1 else 0
        points = []
        for index, (_, value) in enumerate(self._series):
            x = rect.left() + index * step_x
            y = rect.bottom() - (value / max_value) * rect.height()
            points.append(QPointF(x, y))
        painter.setPen(QPen(QColor(PALETTE[0]), 2))
        for a, b in zip(points, points[1:]):
            painter.drawLine(a, b)
        painter.setFont(QFont(self.font().family(), 7))
        painter.setPen(QPen(QColor("#555555")))
        label_stride = max(1, len(self._series) // 8)
        for index, (label, _) in enumerate(self._series):
            if index % label_stride:
                continue
            x = rect.left() + index * step_x
            painter.drawText(QRectF(x - 30, rect.bottom() + 2, 60, 16), Qt.AlignHCenter, str(label))
        painter.drawText(QRectF(2, rect.top() - 4, 46, 16), Qt.AlignRight, str(max_value))


class _FallbackBarChart(QWidget):
    def __init__(self, values: list[tuple[str, int]], title: str, parent=None):
        super().__init__(parent)
        self._values = values
        self._title = title
        self.setMinimumHeight(260)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setFont(QFont(self.font().family(), 9, QFont.Bold))
        painter.drawText(self.rect().adjusted(0, 4, 0, 0), Qt.AlignHCenter | Qt.AlignTop, self._title)
        rect = self.rect().adjusted(10, 30, -10, -70)
        if not self._values:
            painter.drawText(rect, Qt.AlignCenter, "Aucune donnée")
            return
        max_value = max(v for _, v in self._values) or 1
        count = len(self._values)
        gap = 6
        bar_width = max(6.0, (rect.width() - gap * (count + 1)) / count)
        painter.setFont(QFont(self.font().family(), 7))
        for index, (label, value) in enumerate(self._values):
            height = (value / max_value) * rect.height()
            x = rect.left() + gap + index * (bar_width + gap)
            bar_rect = QRectF(x, rect.bottom() - height, bar_width, height)
            painter.fillRect(bar_rect, QColor(PALETTE[index % len(PALETTE)]))
            painter.setPen(QPen(QColor("#333333")))
            painter.drawText(QRectF(x - 20, rect.bottom() + 2, bar_width + 40, 40), Qt.AlignHCenter | Qt.AlignTop, _elide(label))
            painter.drawText(QRectF(x - 20, bar_rect.top() - 14, bar_width + 40, 14), Qt.AlignHCenter, str(value))


class _FallbackPieChart(QWidget):
    def __init__(self, values: list[tuple[str, int]], title: str, parent=None):
        super().__init__(parent)
        self._values = values
        self._title = title
        self.setMinimumHeight(260)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setFont(QFont(self.font().family(), 9, QFont.Bold))
        painter.drawText(self.rect().adjusted(0, 4, 0, 0), Qt.AlignHCenter | Qt.AlignTop, self._title)
        if not self._values:
            painter.drawText(self.rect(), Qt.AlignCenter, "Aucune donnée")
            return
        total = sum(v for _, v in self._values) or 1
        side = min(self.width(), self.height() - 40) - 20
        pie_rect = QRectF(10, 30, side, side)
        start_angle = 0
        for index, (_, value) in enumerate(self._values):
            span = int(360 * 16 * value / total)
            painter.setBrush(QColor(PALETTE[index % len(PALETTE)]))
            painter.drawPie(pie_rect, start_angle, span)
            start_angle += span
        legend_x = pie_rect.right() + 20
        painter.setFont(QFont(self.font().family(), 8))
        for index, (label, value) in enumerate(self._values):
            y = 30 + index * 16
            painter.fillRect(QRectF(legend_x, y, 10, 10), QColor(PALETTE[index % len(PALETTE)]))
            painter.drawText(QRectF(legend_x + 14, y - 2, 220, 16), Qt.AlignLeft, f"{_elide(label)} ({value})")


def _elide(text: str, max_len: int = 18) -> str:
    return text if len(text) <= max_len else text[: max_len - 1] + "…"


def make_line_chart(series: list[tuple[str, int]], title: str, y_label: str = "") -> QWidget:
    if not series:
        return _empty_label()
    if not QTCHART_AVAILABLE:
        return _FallbackLineChart(series, title, y_label)
    chart = QChart()
    chart.setTitle(title)
    line = QLineSeries()
    for index, (_, value) in enumerate(series):
        line.append(index, value)
    chart.addSeries(line)
    axis_x = QBarCategoryAxis()
    axis_x.append([str(label) for label, _ in series])
    chart.addAxis(axis_x, Qt.AlignBottom)
    line.attachAxis(axis_x)
    axis_y = QValueAxis()
    axis_y.setTitleText(y_label)
    chart.addAxis(axis_y, Qt.AlignLeft)
    line.attachAxis(axis_y)
    chart.legend().hide()
    view = QChartView(chart)
    view.setRenderHint(QPainter.Antialiasing)
    return view


def make_bar_chart(values: list[tuple[str, int]], title: str) -> QWidget:
    if not values:
        return _empty_label()
    if not QTCHART_AVAILABLE:
        return _FallbackBarChart(values, title)
    chart = QChart()
    chart.setTitle(title)
    bar_set = QBarSet(title)
    bar_set.append([value for _, value in values])
    series = QBarSeries()
    series.append(bar_set)
    chart.addSeries(series)
    axis_x = QBarCategoryAxis()
    axis_x.append([_elide(label) for label, _ in values])
    chart.addAxis(axis_x, Qt.AlignBottom)
    series.attachAxis(axis_x)
    axis_y = QValueAxis()
    chart.addAxis(axis_y, Qt.AlignLeft)
    series.attachAxis(axis_y)
    chart.legend().hide()
    view = QChartView(chart)
    view.setRenderHint(QPainter.Antialiasing)
    return view


def make_pie_chart(values: list[tuple[str, int]], title: str) -> QWidget:
    if not values:
        return _empty_label()
    if not QTCHART_AVAILABLE:
        return _FallbackPieChart(values, title)
    chart = QChart()
    chart.setTitle(title)
    series = QPieSeries()
    for label, value in values:
        series.append(_elide(label), value)
    chart.addSeries(series)
    view = QChartView(chart)
    view.setRenderHint(QPainter.Antialiasing)
    return view
