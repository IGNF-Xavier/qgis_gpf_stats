# Dépendances embarquées

## Runtime (dans le ZIP installable)

| Dépendance | Version vendorisée | Rôle | Remarque |
|---|---|---|---|
| `openpyxl` | 3.1.5 (repris tel quel de la 6.1.0, sous `vendor/openpyxl`) | Génération du classeur XLSX analytique | Utilisé **seulement si** `openpyxl` n'est pas déjà installé dans l'environnement Python de QGIS (`exporters/xlsx_exporter.py` essaie d'abord l'import système). Sur QGIS 3.40.4 testé, `openpyxl` 3.1.2 est déjà présent nativement : le repli vendorisé n'est alors pas utilisé. |
| `et_xmlfile` | reprise de la 6.1.0, sous `vendor/et_xmlfile` | Dépendance transitive d'`openpyxl` (écriture XML en flux) | Idem : uniquement si le système n'a pas déjà `openpyxl`/`et_xmlfile`. |

Aucune autre dépendance tierce. Tout le reste (réseau, dates, Qt) utilise exclusivement les modules déjà fournis par QGIS :

- `qgis.core` (`QgsApplication`, `QgsNetworkAccessManager`, `QgsSettings`, `QgsTask`)
- `qgis.gui` (`QgsAuthConfigSelect`)
- `qgis.PyQt.QtCore` / `QtGui` / `QtWidgets`
- `qgis.PyQt.QtChart` **si disponible** (`PyQt5.QtChart` n'est pas toujours packagé) : le dashboard bascule automatiquement sur un rendu de graphiques en `QPainter` pur écrit dans `charts/chart_widgets.py` (`_FallbackLineChart`, `_FallbackBarChart`, `_FallbackPieChart`) si `QtChart` est absent — c'est le cas sur l'installation QGIS 3.40.4 utilisée pour les vérifications de ce dépôt.

## Développement / tests uniquement (non embarqué dans le ZIP installable)

| Outil | Rôle |
|---|---|
| `pytest` | Exécution des 76 tests unitaires de `core/` et `net/` (aucune dépendance à QGIS) |
| Python ≥ 3.9 avec `openpyxl` système (optionnel) | Utilisé pour lancer les tests et le générateur `tools/generate_sample.py` en dehors de QGIS |

Ces outils ne font pas partie du ZIP installable (`geoplateforme_usage_stats_plugin_7.2.0.zip`) ; ils sont fournis dans l'archive « sources » (`le dépôt Git`) pour permettre de rejouer les tests.
