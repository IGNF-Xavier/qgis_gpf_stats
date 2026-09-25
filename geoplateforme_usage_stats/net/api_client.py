"""Transport-agnostic Geoplateforme API client: pagination, retry/backoff
and HTTP status mapping (section 10).

``Transport`` is the only seam that touches the network. The real runtime
plugs in :class:`~geoplateforme_usage_stats.net.qgis_transport.QgsTransport`
(``QgsNetworkAccessManager`` + the QGIS auth manager); tests plug in a fake
that returns canned responses, so pagination/retry/error-mapping logic is
fully unit-testable without QGIS.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable, Iterable, Optional, Protocol

from .progress import CancelCheck, OperationCancelled, never_cancelled

RETRYABLE_STATUSES = {408, 429, 502, 503, 504}
ERROR_MESSAGES = {
    401: "Authentification OAuth2 expirée ou invalide.",
    403: "Accès refusé pour cet objet.",
    404: "Cet objet n'est pas raccordé à la route Stats.",
    408: "Délai d'attente dépassé.",
    429: "Trop de requêtes envoyées à l'API (429).",
    502: "Passerelle amont indisponible (502).",
    503: "Service temporairement indisponible (503).",
    504: "Délai de passerelle dépassé (504).",
}


@dataclass
class TransportResponse:
    status: int
    headers: dict
    body: bytes
    network_error: str = ""


class Transport(Protocol):
    def request(self, path: str, params: Iterable[tuple[str, str]]) -> TransportResponse: ...


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


class ApiClient:
    def __init__(
        self,
        transport: Transport,
        retries: int = 3,
        backoff_base_seconds: float = 1.0,
        sleep: Callable[[float], None] = lambda seconds: None,
    ) -> None:
        self._transport = transport
        self._retries = max(1, retries)
        self._backoff_base = backoff_base_seconds
        self._sleep = sleep

    def get_json(
        self,
        path: str,
        params: Iterable[tuple[str, str]] = (),
        is_cancelled: CancelCheck = never_cancelled,
    ) -> tuple[object, dict, int]:
        last_error: Optional[ApiError] = None
        for attempt in range(1, self._retries + 1):
            if is_cancelled():
                raise OperationCancelled()
            response = self._transport.request(path, params)
            if response.network_error:
                last_error = ApiError(response.status or 0, response.network_error)
            elif 200 <= response.status < 300:
                try:
                    return json.loads(response.body.decode("utf-8") or "null"), response.headers, response.status
                except ValueError as exc:
                    raise ApiError(response.status, f"Réponse JSON invalide : {exc}") from exc
            else:
                last_error = ApiError(response.status, ERROR_MESSAGES.get(response.status, f"Erreur HTTP {response.status}"))

            if response.status in RETRYABLE_STATUSES and attempt < self._retries:
                self._sleep(self._backoff_base * (2 ** (attempt - 1)))
                continue
            raise last_error
        raise last_error or ApiError(0, "Échec de la requête sans détail.")

    def get_all_pages(
        self,
        path: str,
        page_size: int = 50,
        max_pages: int = 1000,
        is_cancelled: CancelCheck = never_cancelled,
    ) -> list:
        output: list = []
        for page in range(1, max_pages + 1):
            if is_cancelled():
                raise OperationCancelled()
            data, headers, _ = self.get_json(
                path, (("page", str(page)), ("limit", str(page_size))), is_cancelled
            )
            items = _extract_list(data)
            output.extend(items)
            total = headers.get("x-total-count")
            if (total and page * page_size >= int(total)) or (not total and len(items) < page_size):
                return output
        return output


def _extract_list(data: object) -> list:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("items", "results", "data"):
            value = data.get(key)
            if isinstance(value, list):
                return value
    return []


def extract_id(value: object) -> str:
    if isinstance(value, dict):
        return str(value.get("_id") or value.get("id") or "")
    return str(value or "")
