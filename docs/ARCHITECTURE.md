# Architecture — 7.2.0

## Objectif de la réécriture

La version 6.1.0 tenait dans 3 fichiers (`main.py` 236 lignes, `plugin.py`, `xlsx_export.py`) écrits dans un style très dense, tout synchrone (chaque appel réseau bloque l'UI via une boucle d'événements locale), sans progression, sans dashboard, avec un éditeur de groupes minimal. La logique elle-même (pagination, retries, construction du catalogue, classification de couverture, agrégation, structure des exports) était correcte et a été **conservée** ; elle a été extraite dans des modules purs, puis enrichie et connectée à une couche asynchrone et à une UI plus complète.

## Découpage en modules

```
geoplateforme_usage_stats/
├── core/            pur Python, sans Qt ni QGIS — testable avec pytest seul
│   ├── models.py            dataclasses (CatalogItem, Group, StatsResult, PeriodConfig, SeriesRow, ...)
│   ├── period_service.py    préréglages de période, ISO, éligibilité du pas fin
│   ├── group_service.py     CRUD groupes, persistance (via un GroupStore injecté), migration 6.1.0
│   ├── cache_service.py     cache catalogue horodaté (via un CacheStore injecté)
│   ├── coverage_service.py  classification de couverture temporelle (section 4)
│   ├── aggregation_service.py  reclassement jour/semaine/mois, séries par groupe/datastore/type
│   ├── dashboard_service.py    KPI et données de graphiques, isolés par niveau d'analyse
│   └── export_context.py       assemble tout ce qui précède en lignes prêtes à exporter
│
├── net/             logique réseau, Transport injecté (seul qgis_transport.py importe qgis)
│   ├── api_client.py        pagination, retry/backoff, mapping des codes HTTP
│   ├── catalog_service.py   construit le catalogue (routes Entrepôt), isole les erreurs par datastore
│   ├── stats_service.py     interroge les routes Stats, isole les erreurs par objet
│   ├── qgis_transport.py    QgsNetworkAccessManager + gestionnaire d'authentification QGIS
│   └── progress.py          vocabulaire d'événements de progression partagé
│
├── workers/
│   └── tasks.py       QgsTask (CatalogLoadTask, StatsQueryTask) : tout le réseau tourne hors thread UI
│
├── exporters/
│   ├── csv_exporter.py      6 exports CSV nommés
│   └── xlsx_exporter.py     classeur à 10 feuilles avec graphiques (openpyxl)
│
├── charts/
│   └── chart_widgets.py     Qt Charts si disponible, sinon rendu QPainter de repli
│
├── ui/               Qt/QGIS uniquement — orchestration, aucune logique métier propre
│   ├── main_dialog.py, group_editor.py, dual_selector.py (onglet Consommateur),
│   │   producer_tree_selector.py (onglet Producteur : arborescence catégorie → datastore),
│   │   period_panel.py, progress_dialog.py, dashboard_widget.py, glossary_dialog.py,
│   │   settings_dialog.py, settings_store.py
│
├── vendor/           openpyxl + et_xmlfile vendorisés (repli si openpyxl absent du système)
├── plugin.py, __init__.py, metadata.txt
```

## Pourquoi cette séparation

- **`core/` ne dépend jamais de Qt.** Toute règle métier (couverture, agrégation, KPI, groupes, période, cache) est donc testable avec `pytest` seul, sans QGIS installé — c'est ce qui a permis d'écrire les 76 tests unitaires du dépôt sans environnement QGIS.
- **`net/` isole le seul point de contact avec le réseau** derrière un protocole `Transport` (une méthode `request(path, params) -> TransportResponse`). Les tests utilisent un `FakeTransport` ; l'exécution réelle utilise `QgsTransport` (QgsNetworkAccessManager + gestionnaire d'authentification QGIS, proxys et paramètres réseau QGIS respectés).
- **`workers/` est la seule couche qui touche aux threads.** `QgsTask` exécute `core`/`net` en tâche de fond et ne communique avec l'UI que par signaux Qt (`stepProgress`, `loaded`/`failed`, `finishedWithResults`) — jamais d'appel direct à un widget depuis le thread de travail.
- **`ui/` ne fait qu'assembler.** `main_dialog.py` ne recalcule rien lui-même : il appelle `core.group_service`, `core.export_context`, `net.catalog_service`/`stats_service` via les workers, et reflète le résultat dans les widgets.

## Flux de chargement du catalogue (section 3)

`MainDialog._load_from_api` → crée un `ApiClient(QgsTransport(authcfg))` → `CatalogLoadTask` → `net.catalog_service.build_catalog()` (thread de travail) → progression émise à chaque étape (connexion, permissions consommateur, par datastore : offerings, détail des offerings, endpoints, permissions producteur) → `ProgressDialog` (UI) affiche l'étape courante, le datastore, les compteurs cumulés et le temps écoulé → `Catalog` renvoyé par le signal `loaded`, mis en cache (`core.cache_service`), puis reflété dans les deux sélecteurs.

Un échec sur un datastore est capturé (`DatastoreLoadError`), n'interrompt pas le chargement des autres, et alimente la feuille `Journal_erreurs` des exports.

## Flux de requête de statistiques

`MainDialog._run_query` construit la liste dédupliquée des objets sélectionnés (les groupes utilisateur sont développés en leurs offerings membres à cette étape), lance `StatsQueryTask` → `net.stats_service.fetch_many()` (une erreur par objet n'interrompt pas le lot) → les `StatsResult` bruts (avec leurs points temporels non agrégés) sont conservés tels quels dans `MainDialog.results`.

## Dashboard et exports : une seule source de vérité

`core.export_context.build_export_context()` est appelé à la fois par les exports CSV/XLSX et (indirectement, via les mêmes fonctions `core.aggregation_service`/`core.dashboard_service`) par l'onglet Dashboard. Les deux ne peuvent donc pas diverger. La règle centrale — ne jamais mélanger deux niveaux d'analyse dans un même total — est appliquée une seule fois, dans `core.dashboard_service`, et respectée partout ailleurs.

## Pourquoi les groupes ne sont pas de simples filtres

Un groupe est une liste d'`offering_id` choisie par l'utilisateur, indépendante de l'API. `core.aggregation_service.group_series()` reclasse les points bruts de chaque offering membre dans le grain d'analyse choisi **avant** de les sommer (jamais par égalité stricte de `period_start`, les offerings n'ayant aucune garantie de renvoyer des bornes identiques), et deux groupes qui partagent une offre restent calculés indépendamment (`core.group_service.overlapping_pairs` sert uniquement à avertir l'utilisateur).
