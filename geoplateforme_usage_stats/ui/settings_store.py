"""``QgsSettings``-backed adapters for the core services' storage seams."""
from __future__ import annotations

from qgis.core import QgsApplication, QgsSettings

AUTH_KEY = "geoplateforme_usage_stats/authcfg"
DATASTORE_SELECTION_KEY = "geoplateforme_usage_stats/selected_datastore_ids"


class QgsGroupStore:
    """Implements :class:`core.group_service.GroupStore`."""

    def get_raw(self, key: str) -> str:
        return str(QgsSettings().value(key, "") or "")

    def set_raw(self, key: str, value: str) -> None:
        QgsSettings().setValue(key, value)


def get_authcfg() -> str:
    return str(QgsSettings().value(AUTH_KEY, "") or "")


def set_authcfg(authcfg: str) -> None:
    QgsSettings().setValue(AUTH_KEY, authcfg)


def cache_directory() -> str:
    base = QgsApplication.qgisSettingsDirPath()
    return str(base) + "geoplateforme_usage_stats"


def get_selected_datastore_ids() -> set:
    raw = str(QgsSettings().value(DATASTORE_SELECTION_KEY, "") or "")
    return {part for part in raw.split(",") if part}


def set_selected_datastore_ids(datastore_ids) -> None:
    QgsSettings().setValue(DATASTORE_SELECTION_KEY, ",".join(sorted(datastore_ids)))
