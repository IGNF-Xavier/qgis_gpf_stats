"""QGIS-backed :class:`Transport`: ``QgsNetworkAccessManager`` + auth manager.

This is the only module in ``net/`` that imports ``qgis``. It intentionally
mirrors QGIS's own network stack (proxy settings, timeouts, the QGIS
authentication manager for OAuth2) instead of using ``requests`` or
``urllib`` directly, so the plugin always respects the user's QGIS network
configuration (section 10 requirement).
"""
from __future__ import annotations

from urllib.parse import urlencode

from qgis.PyQt.QtCore import QEventLoop, QTimer, QUrl, Qt
from qgis.PyQt.QtNetwork import QNetworkReply, QNetworkRequest
from qgis.core import QgsApplication, QgsNetworkAccessManager

from .api_client import TransportResponse

BASE_URL = "https://data.geopf.fr/api"
USER_AGENT = b"QGIS-GeoPF-Stats/7.0"


class QgsTransport:
    def __init__(self, authcfg: str, timeout_seconds: int = 180) -> None:
        self._authcfg = str(authcfg or "")
        self._timeout_ms = max(10, int(timeout_seconds)) * 1000

    def request(self, path: str, params) -> TransportResponse:
        if not self._authcfg:
            return TransportResponse(status=0, headers={}, body=b"", network_error="Aucune configuration OAuth2 sélectionnée.")

        url = QUrl(BASE_URL + path)
        if params:
            url.setQuery(urlencode(list(params)))

        request = QNetworkRequest(url)
        request.setRawHeader(b"Accept", b"application/json")
        request.setRawHeader(b"User-Agent", USER_AGENT)
        try:
            request.setTransferTimeout(self._timeout_ms)
        except AttributeError:
            pass

        if not QgsApplication.authManager().updateNetworkRequest(request, self._authcfg):
            return TransportResponse(status=0, headers={}, body=b"", network_error="Impossible d'appliquer la configuration OAuth2.")

        reply = QgsNetworkAccessManager.instance().get(request)
        loop = QEventLoop()
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(reply.abort)
        reply.finished.connect(loop.quit)
        timer.start(self._timeout_ms)
        loop.exec()
        timer.stop()

        status_attr = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        status = int(status_attr) if status_attr is not None else 0
        body = bytes(reply.readAll())
        network_error = ""
        if reply.error() != QNetworkReply.NoError and not (200 <= status < 300):
            network_error = reply.errorString()
        headers = {
            bytes(name).decode().lower(): bytes(reply.rawHeader(name)).decode()
            for name in reply.rawHeaderList()
        }
        reply.deleteLater()
        return TransportResponse(status=status, headers=headers, body=body, network_error=network_error)
