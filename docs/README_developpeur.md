# Guide développeur — 7.2.0

## Arborescence des sources

Voir `ARCHITECTURE.md` pour le découpage complet. En bref : `core/` et la majeure partie de `net/` sont du Python pur (aucun `import qgis`), `workers/`, `charts/` et `ui/` sont Qt/QGIS.

## Lancer les tests

```bash
python -m pip install pytest openpyxl   # openpyxl sert aussi de secours si le système n'en a pas
python -m pytest tests/ -v
```

Aucune installation de QGIS n'est nécessaire pour la suite `pytest` (73 tests). Les fichiers sous `ui/` ne sont pas testés par `pytest` (ils importent `qgis.PyQt`) ; pour les vérifier, un environnement QGIS avec accès à `qgis.utils.iface` est nécessaire (voir `RAPPORT_TESTS.md`, section vérifications QGIS).

## Ajouter une règle métier

1. Elle va dans `core/` (ou `net/` si elle implique un appel réseau), jamais dans `ui/`.
2. Écrire le test `pytest` correspondant dans `tests/` avant de brancher l'UI.
3. Ne câbler l'UI qu'une fois le test vert.

## Ajouter un champ à un export

Un seul endroit à modifier : `core/export_context.py` (fonction `build_export_context`). Les deux exporteurs (`csv_exporter.py`, `xlsx_exporter.py`) et le dashboard (`ui/dashboard_widget.py`) lisent tous les trois les mêmes structures (`ExportContext.summary_rows`, `.series_analytiques_rows`, etc.) — un champ ajouté là apparaît automatiquement dans les CSV nommés en colonne, il faut en revanche l'ajouter explicitement aux `headers` d'une feuille XLSX si elle a des `headers` figés.

## Ajouter une route API

1. `net/api_client.py` ne change pas (générique).
2. La route se construit dans `net/catalog_service.py` (catalogue) ou `net/stats_service.py` (statistiques).
3. Écrire d'abord un test avec `FakeTransport` (`tests/conftest.py`) simulant la nouvelle route.

## Régénérer l'exemple XLSX synthétique

```bash
python tools/generate_sample.py
```

Écrit `samples/stats_geoplateforme_7_0_synthetic.xlsx` et les CSV correspondants à partir de données entièrement fabriquées (seed fixe `20260922`, aucune donnée réelle).

## Style de code

Pas de docstring multi-lignes hors modules/fonctions publiques citées ci-dessus ; les commentaires expliquent un « pourquoi » non évident (ex. pourquoi les points ne sont jamais sommés par égalité stricte de `period_start`), jamais un « quoi » déjà lisible dans le nom des identifiants.

## Compatibilité QGIS

Testé sur QGIS 3.40.4-Bratislava (Windows). `metadata.txt` déclare `qgisMinimumVersion=3.40` et `qgisMaximumVersion=3.99`. Le seul point d'API QGIS un peu récent utilisé est `QNetworkRequest.setTransferTimeout` (protégé par un `try/except AttributeError` pour les builds Qt plus anciens) et `QgsTask` avec signaux personnalisés (stable depuis QGIS 3.x).
