# Routes de l'API Géoplateforme utilisées

Base : `https://data.geopf.fr/api`. Toutes les requêtes passent par le gestionnaire d'authentification QGIS (OAuth2) et `QgsNetworkAccessManager` (proxy/paramètres réseau QGIS respectés).

## Catalogue — consommateur

| Route | Usage |
|---|---|
| `GET /users/me/permissions` | Liste des permissions consommateur (paginé) |
| `GET /users/me/permissions/{permission}/stats` | Statistiques d'une permission consommateur |

## Catalogue — producteur

| Route | Usage |
|---|---|
| `GET /users/me` | Liste des datastores accessibles (`communities_member[].community.datastore`) |
| `GET /datastores/{datastore}/offerings` | Liste des offerings du datastore (paginé) |
| `GET /datastores/{datastore}/offerings/{offering}` | Détail d'un offering (nom métier, type, endpoint associé) |
| `GET /datastores/{datastore}/permissions` | Liste des permissions producteur (paginé) |
| `GET /datastores/{datastore}/endpoints` | Liste des endpoints du datastore (paginé) |

## Onglet Datastores (détail par datastore)

| Route | Usage |
|---|---|
| `GET /users/me` | Liste rapide des datastores accessibles, réutilisée pour peupler la liste à cocher (`net/catalog_service.py::list_datastore_refs`) |
| `GET /datastores/{datastore}` | Détail complet d'un datastore : stockage utilisé/quota par backend (`storages.data`/`uploads`/`annexes`) et endpoints provisionnés avec leur usage (`endpoints[].use`/`quota`), qu'ils aient ou non une offre raccordée (`net/datastore_info_service.py`) |

Cette route est nettement plus lente que les autres (10 à 30 secondes observées en production), probablement parce que le serveur agrège l'usage de stockage à la volée ; il n'existe pas de variante allégée. Chaque appel est donc déclenché explicitement, datastore par datastore, et jamais en boucle automatique sur l'ensemble du compte.

## Statistiques

| Route | Usage |
|---|---|
| `GET /datastores/{datastore}/permissions/{permission}/stats` | Statistiques d'une permission producteur |
| `GET /datastores/{datastore}/offerings/{offering}/stats` | Statistiques d'un offering |
| `GET /datastores/{datastore}/endpoints/{endpoint}/stats` | Statistiques d'un endpoint |

Chaque route Stats est appelée avec les paramètres `start`, `end`, `details` (`true`/`false`), `page`, `limit=50`, jusqu'à épuisement de la pagination (`x-total-count` si présent, sinon page incomplète).

## Correction apportée par rapport à la version 6.1.0

La 6.1.0 ne déduisait les endpoints que depuis le champ `endpoint` embarqué dans le détail de chaque offering — un endpoint sans offering associé (ou temporairement absent du lot d'offerings parcouru) pouvait donc ne jamais apparaître. La 7.0.0 appelle explicitement `GET /datastores/{datastore}/endpoints` pour chaque datastore, comme demandé, et construit les objets endpoint à partir de cette route dédiée (`net/catalog_service.py::_datastore_endpoints`) — la relation offering → endpoint fournie par l'API reste conservée séparément sur chaque offering (`endpoint_id`/`endpoint_name`), sans être inventée.

## Gestion des erreurs HTTP

| Code | Traitement |
|---|---|
| 401 | Erreur explicite « authentification OAuth2 expirée ou invalide », non retentée |
| 403 | Erreur explicite « accès refusé », non retentée |
| 404 | Statut `not_connected` (objet non raccordé à Stats), non retentée |
| 408, 429, 502, 503, 504 | Retentée avec backoff exponentiel (jusqu'à 3 tentatives) |
| Autre | Erreur générique avec le code HTTP, non retentée |

Voir `net/api_client.py` (`RETRYABLE_STATUSES`, `ERROR_MESSAGES`).
