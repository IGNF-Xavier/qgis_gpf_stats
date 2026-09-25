# Statistiques analytiques Géoplateforme — 7.2.0 — Guide utilisateur

## 1. Installation

1. Dans QGIS : **Extensions → Installer/Gérer les extensions → Installer depuis un ZIP**.
2. Sélectionnez `geoplateforme_usage_stats_plugin_7.2.0.zip`.
3. Activez l'extension. Un menu **Statistiques analytiques Géoplateforme** apparaît dans **Extensions**.

Prérequis : QGIS 3.40 ou supérieur (testé sur 3.40.4). Aucune dépendance à installer séparément (voir `DEPENDANCES.md`).

La fenêtre principale n'est pas modale : vous pouvez continuer à utiliser QGIS (canevas, autres panneaux, autres extensions) pendant qu'elle est ouverte. La fermer (bouton Fermer ou croix) la cache sans perdre son état — catalogue chargé, groupes, dernière interrogation — elle se réaffiche telle quelle via **Ouvrir…**.

## 2. Configurer l'authentification

**Extensions → Statistiques analytiques Géoplateforme → Configurer OAuth2…**

Sélectionnez la configuration d'authentification OAuth2 QGIS à utiliser pour interroger `data.geopf.fr/api`. Le plugin ne stocke jamais de secret lui-même : il délègue entièrement à la configuration QGIS existante.

**Si le jeton a expiré ou ne fonctionne plus** : un chargement ou une interrogation qui échoue avec une erreur d'authentification (401/403) affiche désormais un bouton **« Configurer OAuth2… »** directement dans le message d'erreur. Choisir la même configuration ne la réautorise pas forcément à elle seule : utilisez l'icône crayon du sélecteur pour éditer/réautoriser la configuration, ou créez-en une nouvelle depuis les paramètres d'authentification de QGIS. Le cache local n'est jamais chargé automatiquement à l'ouverture, précisément pour ne pas masquer un jeton mort derrière un catalogue qui a l'air normal.

## 3. Charger le catalogue

Dans la fenêtre principale (**Ouvrir…**), trois boutons gèrent le catalogue :

- **Actualiser depuis l'API** : relance un chargement complet, avec une fenêtre de progression qui affiche l'étape en cours, le datastore traité, le nombre d'offerings/endpoints/permissions déjà récupérés, le temps écoulé et un bouton **Annuler**.
- **Utiliser le cache** : réutilise le dernier catalogue chargé (stocké localement, horodaté). Un avertissement s'affiche si le cache a plus de 6 heures.
- **Vider le cache** : supprime le cache local.

Si un datastore échoue pendant le chargement, les autres continuent d'être traités ; un récapitulatif des erreurs s'affiche à la fin.

Le chargement tourne en tâche de fond : ni la fenêtre du plugin ni le reste de QGIS (canevas, autres panneaux, autres extensions) ne sont bloqués pendant ce temps. Fermer la fenêtre de progression annule aussi le chargement. Les boutons de chargement/interrogation se désactivent le temps d'une opération, pour éviter d'en lancer deux à la fois.

## 4. Composer des groupes d'offres

Le bouton **Composer les groupes…** n'est actif qu'une fois des offerings chargés (onglet Producteur). La fenêtre de composition propose :

- à gauche, la liste des groupes (Créer / Renommer / Supprimer / Dupliquer) ;
- à droite, une recherche texte, un filtre par datastore, un filtre par type de service, la liste des offerings avec cases à cocher, les boutons Tout cocher / Tout décocher / Cocher-Décocher les éléments visibles, et un compteur « N offre(s) sélectionnée(s) sur M ».

Un offering peut appartenir à plusieurs groupes. Si des groupes se chevauchent, un bandeau d'avertissement l'indique — **n'additionnez pas** les totaux de deux groupes qui partagent des offres sans vérifier ce recouvrement (le dashboard le rappelle aussi).

## 5. Sélectionner les objets à interroger

Deux onglets :

- **Consommateur** : vos permissions consommateur (`/users/me/permissions`), en liste simple avec recherche des deux côtés.
- **Producteur** : une arborescence à gauche, organisée par catégorie puis par datastore :
  - `👥 Groupes utilisateur` — chaque groupe peut être déplié pour prévisualiser les offres qu'il contient (lecture seule ici ; l'édition se fait dans **Composer les groupes…**) ;
  - `🔌 Endpoints` → par datastore ;
  - `🧩 Offerings` → par datastore ;
  - `🔑 Permissions producteur` → par datastore.

  Double-cliquer un objet le coche (préfixe `✓`, en gras) et l'ajoute à la liste de droite ; double-cliquer à nouveau (dans l'arbre ou dans la liste de droite) le retire. Les boutons `>>>` / `<<<` ne portent que sur ce qui est sélectionné (surligné) dans l'arbre ou la liste ; `>>` / `<<` portent sur tout ce qui est visible. La recherche filtre l'arbre en conservant la structure (une catégorie/datastore reste visible tant qu'au moins un de ses objets correspond). Les UUID restent en info-bulle.

**Pourquoi autant d'endpoints ?** Un datastore peut avoir une dizaine d'endpoints (un par service technique possible : WMTS, WFS, CSW, téléchargement, itinéraire…) même si peu d'offres y sont réellement raccordées — chaque endpoint affiche son usage réel entre parenthèses, par exemple `(4/10 offre(s) raccordée(s))`. La case **« Masquer les endpoints sans offre raccordée (usage = 0) »**, au-dessus des onglets, permet de ne garder que les endpoints réellement utilisés. Voir aussi le **Glossaire** (bouton en bas de fenêtre) pour la définition complète.

## 6. Choisir la période

Préréglages : 7 derniers jours, 30 derniers jours, mois en cours, mois précédent, année en cours, 12 derniers mois, personnalisée. Le pas fin de 5 minutes n'est activable que pour une période de 30 jours au plus.

## 7. Interroger et lire les résultats

**Interroger la sélection** lance la requête en tâche de fond (l'interface reste utilisable), avec la même fenêtre de progression et un bouton Annuler.

L'onglet **Dashboard** se remplit automatiquement : indicateurs et graphiques, toujours calculés pour **un seul niveau d'analyse à la fois** (offerings, endpoints, permissions consommateur, permissions producteur ou groupes) — jamais additionnés entre eux. Le sélecteur « Niveau d'analyse » ne propose que les niveaux réellement interrogés : si vous n'avez sélectionné que des endpoints, seul « Endpoints » y apparaît.

Une ligne d'état au-dessus des graphiques rappelle en permanence les filtres actifs (« Niveau : … · Métrique : … · Regroupement : … · Groupe : … · Datastore : … · Type de service : … »). Les filtres Groupe / Datastore / Type de service se grisent automatiquement et repassent à « Tous » quand ils ne s'appliquent pas au niveau choisi (par exemple, le filtre Groupe n'a de sens qu'au niveau « Groupes utilisateur ») — survolez le filtre grisé pour voir pourquoi. Chaque graphique affiche aussi une légende d'une ligne expliquant précisément ce qu'il représente ; les graphiques « Répartition par datastore » et « Répartition par type de service » sont **toujours** calculés sur les offerings, quel que soit le niveau sélectionné (ils réagissent uniquement au filtre Groupe).

## 8. Exporter

- **Exporter CSV…** : choisissez un dossier et un préfixe ; le plugin écrit un fichier par angle d'analyse (synthèse, séries API brutes, séries analytiques, séries de groupes, contrôle de couverture, composition des groupes) — seuls les fichiers non vides sont écrits.
- **Exporter XLSX analytique…** : classeur à 10 feuilles (Dashboard, Synthese, Series_API, Series_analytiques, Series_groupes, Controle_couverture, Groupes, Periode, Journal_erreurs, **Glossaire**), directement exploitable dans Excel, avec graphiques intégrés. La feuille Dashboard n'affiche un indicateur, un tableau ou un graphique « Top 15 » pour un niveau que si ce niveau fait partie de la sélection interrogée — pas d'offerings sélectionnées, pas de tableau « Top 15 offerings ».

Un exemple généré à partir de données synthétiques est fourni : `samples/stats_geoplateforme_7_0_synthetic.xlsx`.

## Glossaire

Le bouton **« Glossaire / Aide… »**, en bas de la fenêtre principale, ouvre une fenêtre non modale (elle reste ouverte pendant que vous continuez à utiliser le plugin) définissant offering, datastore, endpoint, permission producteur/consommateur, groupe utilisateur, niveau d'analyse, hits, volume transféré et les statuts de couverture. Le même contenu figure dans la feuille **Glossaire** de chaque export XLSX.

## 9. Lire le statut de couverture

Le plugin distingue explicitement :

- la période **demandée** (`requested_start`/`requested_end`) ;
- l'**activité observée** (`first_activity`/`last_activity`, `active_days_count`) — ce n'est pas une limite technique de l'API, seulement ce qui a été constaté ;
- l'**absence d'activité** (`no_usage`).

Statuts possibles : `complete_coverage`, `partial_coverage`, `no_temporal_detail`, `no_usage`, `not_connected`, `error`. Chaque ligne de la feuille `Controle_couverture` porte une interprétation en français (`coverage_interpretation`).

## 10. Migration depuis la version 6.1.0

Vos groupes 6.1.0 sont repris automatiquement au premier chargement (voir `MIGRATION_6.1_VERS_7.0.md`) — aucune action requise.
