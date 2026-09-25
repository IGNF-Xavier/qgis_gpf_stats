# Rapport de tests — 7.2.0

## Résumé

```
76 passed in 3.7s
(pytest 9.1.1, Python 3.12.6, aucune dépendance à QGIS)
```

Suite exécutable indépendamment de QGIS :

```bash
cd qgis_gpf_stats
python -m pytest tests/ -v
```

## Couverture par exigence obligatoire (section 11 du spécification fonctionnelle)

| Exigence | Test(s) |
|---|---|
| Pagination | `test_api_client.py::test_pagination_stops_on_x_total_count`, `::test_pagination_stops_on_short_page_without_total_count` |
| Chargement de plusieurs datastores | `test_catalog_service.py::test_build_catalog_multiple_datastores` |
| Progression | `test_catalog_service.py::test_build_catalog_multiple_datastores` (événements `ProgressEvent`), `test_stats_service.py::test_fetch_many_reports_progress` |
| Annulation | `test_api_client.py::test_cancellation_stops_pagination`, `test_catalog_service.py::test_cancellation_stops_before_second_datastore` |
| Cache | `test_cache_service.py` (5 tests : sauvegarde/relecture, absence, vidage, fraîcheur) |
| Erreurs partielles | `test_catalog_service.py::test_build_catalog_multiple_datastores` (ds-2 échoue, ds-1 reste chargé), `test_stats_service.py::test_fetch_many_isolates_item_failures` |
| Création d'un groupe | `test_group_service.py::test_create_group`, `::test_create_rejects_duplicate_name`, `::test_create_rejects_empty_name` |
| Affectation d'offres | `test_group_service.py::test_set_offering_ids_assigns_offers` |
| Persistance des groupes | `test_group_service.py::test_persistence_round_trip` |
| Groupe vide | `test_group_service.py::test_empty_group_has_no_offerings`, `test_aggregation_service.py::test_group_series_empty_group_has_no_rows` |
| Groupe avec plusieurs datastores | `test_group_service.py::test_group_spanning_multiple_datastores_keeps_all_ids`, `test_aggregation_service.py::test_group_spanning_multiple_datastores` |
| Groupe chevauchant un autre groupe | `test_group_service.py::test_overlapping_pairs_detected`, `test_aggregation_service.py::test_overlapping_groups_are_not_summed_together`, `test_dashboard_service.py::test_group_kpi_warns_on_overlap_when_no_group_selected` |
| Agrégation jour/semaine/mois | `test_coverage_service.py::test_period_bucket_day_week_month`, `test_aggregation_service.py::test_individual_series_buckets_by_day`, `::test_individual_series_raw_grain_keeps_points_separate` |
| Absence de détails | `test_coverage_service.py::test_no_temporal_detail_when_points_missing_but_hits_present`, `test_export_context.py::test_no_temporal_detail_offering_flagged_in_coverage` |
| Absence d'usage | `test_coverage_service.py::test_no_usage` |
| Route non raccordée | `test_stats_service.py::test_fetch_stats_not_connected_on_404`, `test_coverage_service.py::test_not_connected`, `test_export_context.py::test_not_connected_consumer_permission` |
| Couverture partielle | `test_coverage_service.py::test_partial_coverage_when_activity_concentrated`, `::test_complete_coverage_when_activity_spans_full_period` |
| Export CSV | `test_csv_exporter.py` (3 tests) |
| Export XLSX | `test_xlsx_exporter.py` (5 tests) |
| Conservation des UUID | `test_export_context.py::test_summary_rows_keep_business_names_and_uuids`, `test_csv_exporter.py::test_csv_content_has_uuid_and_business_name_columns`, `test_xlsx_exporter.py::test_synthese_sheet_preserves_uuids` |
| Absence de doubles appels sur une même route | `test_catalog_service.py::test_no_duplicate_calls_on_same_route` |
| Absence de doubles comptes dans les KPI | `test_dashboard_service.py::test_kpis_never_mix_offerings_and_endpoints`, `test_export_context.py::test_kpis_isolated_by_level`, `test_xlsx_exporter.py::test_dashboard_sheet_has_kpi_rows_without_mixing_levels` |
| Régression endpoint = liaison datastore/endpoint (7.0.1) | `test_catalog_service.py::test_endpoint_binding_is_unwrapped` |
| Cohérence glossaire plugin ↔ export XLSX (7.1.0) | `test_xlsx_exporter.py::test_glossary_sheet_matches_source` |

Toutes les données utilisées par les tests sont synthétiques (fixtures locales et `tests/conftest.py::_synthetic_dataset`), distinctes du fichier réel `stats_geoplateforme_6_1.xlsx` fourni pour l'audit.

## Vérifications effectuées dans une instance QGIS réelle (3.40.4-Bratislava)

Non automatisables par `pytest` (nécessitent `qgis.core`/`qgis.PyQt`) ; exécutées manuellement dans une instance QGIS 3.40 :

- Import sans erreur des 26 modules du plugin (`core`, `net`, `workers`, `exporters`, `charts`, `ui`, `plugin`) dans le Python embarqué de QGIS.
- Construction de `MainDialog(iface)` sans exception.
- Construction et manipulation de `GroupEditor` (case à cocher, filtre « éléments visibles », compteur `N sur M` correct avant/après action groupée).
- Construction de `DashboardWidget` avec un jeu de données synthétique (20 offerings, 3 datastores).
- Détection automatique de l'absence de `PyQt5.QtChart` sur cette installation QGIS et bascule confirmée vers le rendu `QPainter` de repli (`charts/chart_widgets.py`).
- Export XLSX bout en bout depuis l'environnement QGIS lui-même (openpyxl système 3.1.2, différent de la version vendorisée 3.1.5) : les feuilles sont produites et relisibles.
- **Diagnostic sur données de production réelles (7.0.1)** : requêtage direct de l'API d'un compte réel (9 datastores réels), qui a permis d'identifier que `GET /datastores/{id}/endpoints` renvoie une liaison `{"use", "quota", "endpoint": {...}}` et non l'endpoint lui-même — cause du bug de labels vides constaté. Après correctif, vérifié sur les 92 endpoints réels du compte : 0 label vide.
- **Vérification du comportement du dashboard par niveau (7.1.0)** : `DashboardWidget` construit avec un jeu de données couvrant les 5 niveaux (offerings, endpoints, permissions producteur/consommateur, un groupe) ; bascule confirmée entre niveaux — le filtre Groupe passe de désactivé (niveau Offerings) à activé (niveau Groupes utilisateur), les filtres Datastore/Type de service se désactivent au niveau Permissions consommateur, et la légende d'état reflète chaque changement.
- `GlossaryDialog` construit sans exception.

## Performance (volumétrie du fichier réel fourni)

Benchmark ponctuel (hors suite `pytest`) reproduisant l'ordre de grandeur du fichier `stats_geoplateforme_6_1.xlsx` fourni (25 204 lignes `Series_API`) : 200 offerings × 125 points ≈ 25 000 points, répartis sur 10 groupes chevauchants, agrégés en séries individuelles + groupe + datastore + type de service (`core.aggregation_service.build_all_series`, grain jour) :

```
points=25000 series_rows=6076 elapsed=0.183s
```

(Python 3.12.6, machine de développement — indicatif, pas une garantie contractuelle de temps de réponse.)

## Limites connues

- Les tests `pytest` ne couvrent pas les fichiers de `ui/` (ils importent `qgis.PyQt` et n'ont donc pas de sens hors QGIS) ; ces fichiers sont couverts par la vérification manuelle en environnement QGIS réel décrite ci-dessus, pas par une suite automatisée rejouable sans QGIS.
- Le benchmark ci-dessus mesure l'agrégation en mémoire seule ; il n'inclut pas le temps réseau (pagination des routes Stats), qui domine en pratique et dépend de l'API distante.
- **Non-modalité (7.1.1)** : comportement réel à l'écran (fenêtres qui ne bloquent pas le canevas QGIS) à confirmer manuellement après rechargement du plugin, ces réglages Qt n'étant pas couverts par `pytest`.
