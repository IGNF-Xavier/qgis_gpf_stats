# Journal des modifications

Le format suit [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/).

## [7.4.2] - 2026-09-30

### Corrigé
- **Onglet Producteur : le type de service n'était visible qu'en infobulle**, rendant impossible de distinguer d'un coup d'œil un offering WFS d'un offering DOWNLOAD ou WMS dans l'arborescence (ou la liste sélectionnée). Le type s'affiche désormais entre crochets à côté du nom - par exemple « BAN PLUS · IGN Adresse [WFS] ». Corrige au passage la recherche : le champ annonçait « nom, datastore, type » mais ne filtrait pas réellement sur le type puisqu'il ne figurait pas dans le texte affiché.

## [7.4.1] - 2026-09-30

### Ajouté
- **Évolution des hits/volume par offering** (dashboard et export XLSX) : une ligne par offering, aux côtés des évolutions par groupe et par datastore ajoutées en 7.4.0. Limitée aux 15 offerings avec le plus de hits (comme le classement « Top 15 offerings » déjà existant), pour rester lisible sur un compte avec de nombreux offerings.

## [7.4.0] - 2026-09-30

### Ajouté
- **Dashboard (onglet et export XLSX) : trois graphiques d'évolution temporelle toujours visibles**, pour hits ET volume transféré (6 graphiques), indépendants du niveau d'analyse sélectionné dans les filtres :
  - **Évolution des offerings** : somme agrégée sur l'ensemble des offerings interrogés (comme avant, mais visible en permanence plutôt que seulement quand « Offerings » est sélectionné).
  - **Évolution par groupe** : une ligne par groupe utilisateur.
  - **Évolution par datastore** : une ligne par datastore.
  
  Ces trois graphiques respectent le filtre Groupe (offerings/datastore restreints au groupe sélectionné) mais pas les filtres Datastore/Type de service, pour rester une vue d'ensemble cohérente comme les répartitions déjà existantes.

## [7.3.2] - 2026-09-29

### Ajouté
- **Export dédié à l'onglet Datastores** : bouton « Exporter le détail chargé (CSV)… », qui écrit deux fichiers (stockage, endpoints) couvrant tous les datastores dont le détail a été chargé dans l'onglet - indépendant des exports CSV/XLSX de résultats de requête.

### Modifié
- Les boutons **Exporter CSV…** / **Exporter XLSX analytique…** (qui exportent les résultats d'une interrogation) n'apparaissent plus sur l'onglet Datastores, sans rapport avec eux.

## [7.3.1] - 2026-09-29

### Modifié
- Le bouton **« Interroger la sélection »** est maintenant intégré au panneau « Période et temporalité », agrandi et mis en évidence, plutôt qu'isolé dans une rangée séparée.
- Le panneau « Période et temporalité » (et donc le bouton « Interroger la sélection ») ne s'affiche que sur les onglets Consommateur et Producteur : ni l'onglet Dashboard (qui affiche des résultats déjà obtenus) ni l'onglet Datastores (sans rapport avec une période) n'en ont l'usage.
- Onglet Datastores : les colonnes du tableau (Nom technique, Statut, Stockage, Endpoints) sont maintenant dimensionnées automatiquement à l'ouverture pour éviter qu'un intitulé de colonne ne se retrouve tronqué ou chevauche la ligne du dessous.
- Onglet Datastores : le détail d'un datastore (stockage, endpoints) est désormais présenté en colonnes alignées (Nom, Type, Utilisé, Quota, Détail) plutôt qu'en une seule ligne de texte par élément ; les lignes proches ou au-delà du quota sont mises en évidence en orange/rouge.

## [7.3.0] - 2026-09-29

### Ajouté
- Nouvel onglet **Datastores** : liste des datastores accessibles avec recherche et sélection multiple, puis chargement à la demande (par lot) du détail de chaque datastore coché - stockage utilisé/quota par backend (base de données, dépôts, annexes) et liste des endpoints disponibles (type, visibilité, nombre d'offres raccordées, URLs). Chaque appel de détail peut prendre jusqu'à 30 secondes côté serveur ; l'onglet ne charge donc jamais rien tout seul.
- « Actualiser depuis l'API » demande maintenant, avant le chargement du catalogue, quels datastores recharger (liste rapide puis sélection) au lieu de systématiquement tout recharger - utile pour un compte membre de nombreuses communautés. Le dernier choix est mémorisé pour la prochaine fois.

### Modifié
- Le bouton « Interroger la sélection » est déplacé sous les onglets, à côté de la période, plutôt que dans la barre d'actions du haut.

### Corrigé
- Authentification OAuth2 : un échec d'application de la configuration (jeton absent/rejeté) n'était jamais détecté sur certaines versions de QGIS, à cause d'une différence de signature de l'API interne de QGIS. La requête partait alors sans authentification au lieu d'échouer immédiatement avec un message clair.

## [7.2.3] - 2026-09-28

### Corrigé
- **Export XLSX toujours signalé comme endommagé par Excel après la 7.2.2.** Cause réelle, distincte de celle corrigée en 7.2.2 : la date de création du classeur (`docProps/core.xml`) était mal formée (`...+00:00Z`, un décalage UTC et un suffixe « Z » combinés) à cause d'un bug de sérialisation d'openpyxl 3.1.2 - la version que QGIS 3.40 embarque - avec les dates conscientes du fuseau horaire. Une seule date invalide dans les métadonnées du document suffit à faire échouer la validation d'Excel pour tout le fichier, alors que ses feuilles, tableaux et graphiques sont par ailleurs valides. Reproduit et vérifié avec la version d'openpyxl exacte embarquée par QGIS.

## [7.2.2] - 2026-09-28

### Corrigé
- **Export XLSX : fichier signalé comme endommagé par Excel.** Les graphiques du tableau de bord déclaraient leur axe de catégories (dates, noms d'offerings/endpoints/datastores...) comme une référence numérique alors que les cellules concernées contiennent du texte ; Excel rejette cette incohérence de type et propose de « récupérer le contenu ». Tous les graphiques utilisent désormais une référence de type texte, cohérente avec les cellules réellement écrites.
- **Plantage de QGIS pendant un export XLSX**, avec un plantage natif (« access violation ») à l'intérieur d'`openpyxl`/`lxml`. Force désormais le moteur XML interne d'openpyxl (variable `OPENPYXL_LXML=False`), pour éviter tout conflit avec une éventuelle autre version de lxml installée sur le poste.

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

[7.2.3]: https://github.com/IGNF-Xavier/qgis_gpf_stats/releases/tag/v7.2.3
[7.2.2]: https://github.com/IGNF-Xavier/qgis_gpf_stats/releases/tag/v7.2.2
[7.2.1]: https://github.com/IGNF-Xavier/qgis_gpf_stats/releases/tag/v7.2.1
[7.2.0]: https://github.com/IGNF-Xavier/qgis_gpf_stats/releases/tag/v7.2.0
