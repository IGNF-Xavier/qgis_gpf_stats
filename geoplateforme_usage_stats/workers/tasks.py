"""Background ``QgsTask`` workers: the UI thread is never blocked on network
I/O (section 2.2). Each task only reads/writes its own attributes in
``run()`` (executed on a worker thread) and communicates results back to the
main thread exclusively through Qt signals, emitted from ``finished()``
which QGIS's task manager always calls back on the thread that scheduled
the task.
"""
from __future__ import annotations

from typing import Callable, Iterable, Optional

from qgis.core import QgsTask
from qgis.PyQt.QtCore import QElapsedTimer, pyqtSignal

from ..core.models import Catalog, CatalogItem, DatastoreRef, StatsResult
from ..net.api_client import ApiClient, ApiError
from ..net.catalog_service import build_catalog, list_datastore_refs
from ..net.datastore_info_service import fetch_many_datastore_info
from ..net.progress import OperationCancelled, ProgressEvent
from ..net.stats_service import fetch_many


class CatalogLoadTask(QgsTask):
    stepProgress = pyqtSignal(object, float)
    loaded = pyqtSignal(object)
    failed = pyqtSignal(str, int)  # message, http_status (0 if not an HTTP error)

    def __init__(
        self,
        client: ApiClient,
        description: str = "Chargement du catalogue Géoplateforme",
        datastore_filter: "set[str] | None" = None,
    ) -> None:
        super().__init__(description, QgsTask.CanCancel)
        self._client = client
        self._datastore_filter = datastore_filter
        self._catalog: Optional[Catalog] = None
        self._error: str = ""
        self._error_status: int = 0
        self._timer = QElapsedTimer()

    def run(self) -> bool:
        self._timer.start()
        try:
            self._catalog = build_catalog(
                self._client,
                progress_callback=self._on_progress,
                is_cancelled=self.isCanceled,
                datastore_filter=self._datastore_filter,
            )
            return True
        except OperationCancelled:
            return False
        except ApiError as exc:
            self._error = exc.message
            self._error_status = exc.status
            return False
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI via `failed`
            self._error = str(exc)
            return False

    def _on_progress(self, event: ProgressEvent) -> None:
        elapsed = self._timer.elapsed() / 1000.0
        if event.total:
            self.setProgress(min(100.0, 100.0 * event.current / event.total))
        self.stepProgress.emit(event, elapsed)

    def finished(self, result: bool) -> None:
        if result and self._catalog is not None:
            self.loaded.emit(self._catalog)
        elif self._error:
            self.failed.emit(self._error, self._error_status)
        else:
            self.failed.emit("Chargement annulé par l'utilisateur.", 0)


class StatsQueryTask(QgsTask):
    stepProgress = pyqtSignal(object, float)
    finishedWithResults = pyqtSignal(list)
    failed = pyqtSignal(str, int)

    def __init__(
        self,
        client: ApiClient,
        items: Iterable[CatalogItem],
        requested_start: str,
        requested_end: str,
        details_requested: bool,
        description: str = "Interrogation des statistiques d'usage",
    ) -> None:
        super().__init__(description, QgsTask.CanCancel)
        self._client = client
        self._items = list(items)
        self._requested_start = requested_start
        self._requested_end = requested_end
        self._details_requested = details_requested
        self._results: list[StatsResult] = []
        self._error: str = ""
        self._error_status: int = 0
        self._timer = QElapsedTimer()

    def run(self) -> bool:
        self._timer.start()
        try:
            self._results = fetch_many(
                self._client,
                self._items,
                self._requested_start,
                self._requested_end,
                self._details_requested,
                progress_callback=self._on_progress,
                is_cancelled=self.isCanceled,
            )
            return True
        except OperationCancelled:
            return False
        except ApiError as exc:
            self._error = exc.message
            self._error_status = exc.status
            return False
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc)
            return False

    def _on_progress(self, event: ProgressEvent) -> None:
        elapsed = self._timer.elapsed() / 1000.0
        if event.total:
            self.setProgress(min(100.0, 100.0 * event.current / event.total))
        self.stepProgress.emit(event, elapsed)

    def finished(self, result: bool) -> None:
        if result:
            self.finishedWithResults.emit(self._results)
        elif self._error:
            self.failed.emit(self._error, self._error_status)
        else:
            self.failed.emit("Interrogation annulée par l'utilisateur.", 0)


class DatastoreListTask(QgsTask):
    """Single, fast ``GET /users/me`` call - lets the user pick which
    datastores to load/inspect before running the much slower per-datastore
    routes (catalog load, or the Datastores tab's detail)."""

    stepProgress = pyqtSignal(object, float)
    loaded = pyqtSignal(list)
    failed = pyqtSignal(str, int)

    def __init__(self, client: ApiClient, description: str = "Liste des datastores accessibles") -> None:
        super().__init__(description, QgsTask.CanCancel)
        self._client = client
        self._refs: list[DatastoreRef] = []
        self._error: str = ""
        self._error_status: int = 0
        self._timer = QElapsedTimer()

    def run(self) -> bool:
        self._timer.start()
        self.stepProgress.emit(ProgressEvent("connect", "Récupération de la liste des datastores accessibles…"), 0.0)
        try:
            self._refs = list_datastore_refs(self._client, is_cancelled=self.isCanceled)
            return True
        except OperationCancelled:
            return False
        except ApiError as exc:
            self._error = exc.message
            self._error_status = exc.status
            return False
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc)
            return False

    def finished(self, result: bool) -> None:
        if result:
            self.loaded.emit(self._refs)
        elif self._error:
            self.failed.emit(self._error, self._error_status)
        else:
            self.failed.emit("Annulé par l'utilisateur.", 0)


class DatastoreInfoTask(QgsTask):
    """Fetches storage usage + endpoint detail for a chosen subset of
    datastores. Each datastore's failure (this route can be slow enough to
    time out) is isolated and never discards the others."""

    stepProgress = pyqtSignal(object, float)
    loaded = pyqtSignal(list, list)  # list[DatastoreInfo], list[DatastoreLoadError]
    failed = pyqtSignal(str, int)

    def __init__(
        self,
        client: ApiClient,
        refs: Iterable[DatastoreRef],
        description: str = "Détail des datastores",
    ) -> None:
        super().__init__(description, QgsTask.CanCancel)
        self._client = client
        self._refs = list(refs)
        self._infos = []
        self._errors = []
        self._error: str = ""
        self._error_status: int = 0
        self._timer = QElapsedTimer()

    def run(self) -> bool:
        self._timer.start()
        try:
            self._infos, self._errors = fetch_many_datastore_info(
                self._client,
                self._refs,
                progress_callback=self._on_progress,
                is_cancelled=self.isCanceled,
            )
            return True
        except OperationCancelled:
            return False
        except ApiError as exc:
            self._error = exc.message
            self._error_status = exc.status
            return False
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc)
            return False

    def _on_progress(self, event: ProgressEvent) -> None:
        elapsed = self._timer.elapsed() / 1000.0
        if event.total:
            self.setProgress(min(100.0, 100.0 * event.current / event.total))
        self.stepProgress.emit(event, elapsed)

    def finished(self, result: bool) -> None:
        if result:
            self.loaded.emit(self._infos, self._errors)
        elif self._error:
            self.failed.emit(self._error, self._error_status)
        else:
            self.failed.emit("Annulé par l'utilisateur.", 0)
