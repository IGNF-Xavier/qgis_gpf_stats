# Journal des modifications

Le format suit [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/).

## [7.2.1] - 2026-09-25

### Corrigé
- Onglet Producteur : sélection multiple avec Maj et Ctrl.
- Onglet Producteur : sélectionner une catégorie ou un datastore ajoute tout son contenu visible.
- Chargement du catalogue : chaque étape d'un datastore (offerings, endpoints, permissions) est isolée ; une erreur serveur sur l'une d'elles ne fait plus perdre les autres.
- Le statut est mis à jour avant l'alerte de chargement partiel, qui indique désormais l'étape en erreur.

### Documentation
- Authentification : la méthode recommandée est d'installer l'extension *Géoplateforme* et de réutiliser sa configuration OAuth2.

## [7.2.0] - 2026-09-22

### Ajouté
- Onglet **Producteur** en arborescence : catégorie (groupes, endpoints, offerings, permissions producteur) puis datastore. Un groupe se déplie pour afficher les offres qu'il contient.
- Le sélecteur « Niveau d'analyse » du dashboard ne propose que les niveaux réellement interrogés.

### Modifié
- L'export XLSX n'affiche un indicateur, un tableau ou un graphique « Top 15 » que pour les niveaux présents dans la sélection.
- Le cache local n'est plus chargé automatiquement à l'ouverture de la fenêtre : il faut choisir explicitement « Utiliser le cache » ou « Actualiser depuis l'API ».

### Corrigé
- Les erreurs d'authentification (HTTP 401/403) affichent un bouton « Configurer OAuth2… » directement dans le message d'erreur. Le code HTTP est désormais transmis des tâches de fond à l'interface.

## [7.1.1] - 2026-09-22

### Corrigé
- La fenêtre principale et les fenêtres de progression sont non modales : le reste de QGIS (canevas, panneaux, autres extensions) reste utilisable pendant un chargement ou une interrogation. L'éditeur de groupes et la configuration OAuth2 restent modaux, mais seulement vis-à-vis de la fenêtre du plugin.
- Garde-fou contre le lancement de deux opérations réseau simultanées.

## [7.1.0] - 2026-09-22

### Ajouté
- Glossaire intégré (fenêtre d'aide et feuille `Glossaire` de l'export XLSX).
- Affichage de l'usage réel des endpoints (`X/Y offre(s) raccordée(s)`) et case pour masquer les endpoints sans offre raccordée.
- Préfixe de type (offre, endpoint, permission, groupe) dans les listes ; signalement `[aussi dans : …]` des offres appartenant à plusieurs groupes dans l'éditeur de groupes.
- Classements « Top 15 » des permissions producteur et consommateur dans l'export XLSX, avec une légende sous chaque tableau.

### Corrigé
- Dashboard : les filtres groupe, datastore et type de service sont grisés et remis à « Tous » lorsqu'ils ne s'appliquent pas au niveau d'analyse choisi ; légende d'état et description sous chaque graphique.

## [7.0.1] - 2026-09-22

### Corrigé
- Libellés d'endpoints vides : `GET /datastores/{id}/endpoints` renvoie une liaison `{use, quota, endpoint}` et non l'endpoint lui-même.

## [7.0.0] - 2026-09-22

Réécriture structurée de la version 6.1.0.

### Ajouté
- Architecture modulaire : `core/` (logique pure Python testable sans QGIS), `net/`, `workers/`, `exporters/`, `charts/`, `ui/`.
- Chargement du catalogue et interrogation des statistiques en tâches de fond (`QgsTask`) avec progression et annulation.
- Cache local horodaté du catalogue.
- Éditeur de groupes d'offres (recherche, filtres datastore/type de service, compteur), avec migration automatique des groupes de la 6.1.0.
- Onglet Dashboard (indicateurs et graphiques, un seul niveau d'analyse à la fois).
- Exports CSV nommés et export XLSX analytique.
- 76 tests unitaires.

### Modifié
- Contrôle de couverture temporelle explicite : période demandée, activité observée, absence d'activité.
- Agrégation jour/semaine/mois tolérante aux périodes non alignées entre offerings.
- Les endpoints sont récupérés via `GET /datastores/{id}/endpoints`.

## [6.1.0]

Version initiale reprise, voir [docs/historique_6.1.0.md](docs/historique_6.1.0.md).

[7.2.1]: https://github.com/IGNF-Xavier/qgis_gpf_stats/releases/tag/v7.2.1
[7.2.0]: https://github.com/IGNF-Xavier/qgis_gpf_stats/releases/tag/v7.2.0
