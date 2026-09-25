# qgis_gpf_stats

Extension QGIS pour consulter et analyser les **statistiques d'usage de la Géoplateforme** (API Entrepôt et API Stats) : chargement du catalogue de données, interrogation par période, tableau de bord intégré et exports CSV / XLSX.

![Licence GPL v3](https://img.shields.io/badge/licence-GPL%20v3-blue) ![QGIS 3.40+](https://img.shields.io/badge/QGIS-3.40%2B-green)

## Fonctionnalités

- **Deux périmètres strictement séparés**
  - *Consommateur* : les permissions dont vous bénéficiez (`/users/me/permissions`).
  - *Producteur* : les datastores auxquels vous avez accès, avec leurs offerings, endpoints et permissions.
- **Catalogue navigable** : arborescence catégorie → datastore, recherche, double liste de sélection, UUID en info-bulle. Chaque endpoint indique son usage réel (`X/Y offres raccordées`).
- **Groupes d'offres personnalisés** : composés localement, jamais figés dans le code ; une offre peut appartenir à plusieurs groupes, avec signalement des chevauchements.
- **Traitements en tâche de fond** (`QgsTask`) : barre de progression, annulation, erreurs isolées par datastore ; le reste de QGIS reste utilisable pendant un chargement ou une interrogation.
- **Période explicite** : préréglages (7 jours, 30 jours, mois, année…) ou dates personnalisées, pas fin de 5 minutes lorsque la période le permet, regroupement jour / semaine / mois.
- **Contrôle de couverture temporelle** : la période demandée, l'activité observée et l'absence d'activité sont distinguées (`complete_coverage`, `partial_coverage`, `no_temporal_detail`, `no_usage`, `not_connected`, `error`).
- **Tableau de bord** : indicateurs et graphiques calculés sur **un seul niveau d'analyse à la fois** (offerings, endpoints, permissions ou groupes), pour ne jamais additionner des vues qui se recouvrent.
- **Exports** : six fichiers CSV nommés et un classeur XLSX analytique (tableaux structurés, graphiques, glossaire) qui reste exploitable sans le plugin. Noms métier et UUID sont toujours conservés.
- **Authentification QGIS** : utilise le gestionnaire d'authentification OAuth2 de QGIS et son réseau (proxy inclus) ; aucun secret n'est stocké par le plugin.

## Installation

Prérequis : QGIS 3.40 ou supérieur.

1. Téléchargez `geoplateforme_usage_stats_plugin_<version>.zip` depuis la [dernière release](https://github.com/IGNF-Xavier/qgis_gpf_stats/releases/latest).
2. Dans QGIS : **Extensions → Installer/Gérer les extensions → Installer depuis un ZIP**.
3. Activez l'extension. Le menu **Extensions → Statistiques analytiques Géoplateforme** apparaît.

Aucune dépendance à installer : `openpyxl` est embarqué (utilisé uniquement s'il est absent de l'environnement Python de QGIS). Détails dans [docs/INSTALLATION.md](docs/INSTALLATION.md).

## Authentification (recommandé)

Le plus simple est de **passer par l'extension officielle « Géoplateforme » pour QGIS** :

1. Installez l'extension *Géoplateforme* depuis le gestionnaire d'extensions de QGIS.
2. Configurez votre authentification dans cette extension (elle crée une configuration OAuth2 dans le gestionnaire d'authentification de QGIS, nommée par exemple `geoplateforme_cfg`).
3. Dans *Statistiques analytiques Géoplateforme*, ouvrez **Configurer OAuth2…** et sélectionnez cette même configuration.

Le jeton est alors géré et renouvelé par QGIS, sans rien saisir dans ce plugin. Si un jeton expire, l'erreur 401/403 propose un accès direct à la configuration.

## Prise en main

1. **Configurer OAuth2…** : choisissez la configuration d'authentification créée par l'extension *Géoplateforme* (voir ci-dessus).
2. **Actualiser depuis l'API** pour charger le catalogue (ou **Utiliser le cache** hors connexion).
3. Sélectionnez des objets dans les onglets *Consommateur* / *Producteur*, éventuellement via **Composer les groupes…**.
4. Choisissez la période puis **Interroger la sélection**.
5. Consultez l'onglet **Dashboard**, puis exportez en CSV ou XLSX.

Le bouton **Glossaire / Aide…** définit offering, datastore, endpoint, permission, groupe et niveau d'analyse. Guide complet : [docs/README_utilisateur.md](docs/README_utilisateur.md).

## Organisation du dépôt

```
geoplateforme_usage_stats/   plugin QGIS (dossier à installer)
├── core/        logique métier en Python pur, sans dépendance à QGIS
├── net/         client d'API, catalogue, statistiques, transport QGIS
├── workers/     tâches de fond QgsTask
├── exporters/   exports CSV et XLSX
├── charts/      graphiques (Qt Charts ou rendu QPainter de repli)
├── ui/          fenêtres et widgets
└── vendor/      openpyxl embarqué (repli)
tests/           tests unitaires pytest
docs/            documentation utilisateur, développeur, architecture, routes API
samples/         exemple de classeur XLSX généré à partir de données synthétiques
tools/           génération de l'exemple et empaquetage du ZIP
```

## Développement

```bash
python -m pip install pytest openpyxl
python -m pytest              # tests de core/ et net/, sans QGIS
python tools/package.py       # construit dist/geoplateforme_usage_stats_plugin_<version>.zip
python tools/generate_sample.py
```

L'architecture est décrite dans [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), les routes appelées dans [docs/ROUTES_API.md](docs/ROUTES_API.md), les conventions de contribution dans [docs/README_developpeur.md](docs/README_developpeur.md).

## Migration depuis la version 6.1.0

Les groupes créés avec la 6.1.0 sont repris automatiquement au premier lancement (voir [docs/MIGRATION_6.1_VERS_7.0.md](docs/MIGRATION_6.1_VERS_7.0.md)).

## Statut

Extension marquée *expérimentale* dans `metadata.txt`. Les retours et signalements sont les bienvenus via les [issues](https://github.com/IGNF-Xavier/qgis_gpf_stats/issues).

## Licence

[GNU GPL v3](LICENSE).
