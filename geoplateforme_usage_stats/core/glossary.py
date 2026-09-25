"""Shared glossary text: one source used by the in-app help dialog
(``ui/glossary_dialog.py``) and the XLSX export's ``Glossaire`` sheet, so
the two never drift apart.
"""
from __future__ import annotations

GLOSSARY = [
    (
        "Datastore",
        "Espace de stockage et de diffusion rattaché à une communauté sur la Géoplateforme. "
        "Chaque datastore accessible à votre compte producteur regroupe ses propres offerings, "
        "endpoints et permissions.",
    ),
    (
        "Offering (offre)",
        "Une donnée publiée et prête à être diffusée (une couche WFS, une pyramide WMTS, etc.). "
        "C'est l'unité de base sur laquelle portent les statistiques d'usage : chaque offering a "
        "sa propre route Stats, contextualisée par son datastore.",
    ),
    (
        "Endpoint",
        "Un canal de diffusion technique provisionné pour un datastore (WMTS/TMS, WFS, CSW, "
        "téléchargement, calcul d'itinéraire, altimétrie…). Un datastore peut avoir une dizaine "
        "d'endpoints même si peu d'offres y sont réellement raccordées : chaque type de service "
        "possible est une ressource distincte, avec son propre quota (« N offre(s) raccordée(s) "
        "sur un quota de M »), indépendamment de son utilisation réelle. Un endpoint avec un usage "
        "de 0 est provisionné mais vide — c'est pour cela que la liste des endpoints peut sembler "
        "beaucoup plus longue que celle des offres effectivement diffusées.",
    ),
    (
        "Permission producteur",
        "Autorisation, définie côté producteur, donnant accès à un ensemble d'offerings d'un "
        "datastore (à un tiers, à un service interne, etc.). Sa route Stats agrège l'usage de "
        "toutes les offres qu'elle couvre.",
    ),
    (
        "Permission consommateur",
        "Autorisation dont vous bénéficiez, en tant que consommateur, pour accéder à des offres "
        "publiées par un autre producteur. Distincte des permissions producteur : elle ne provient "
        "pas de vos propres datastores.",
    ),
    (
        "Groupe utilisateur",
        "Regroupement local d'offerings, créé et géré uniquement dans ce plugin (jamais dans "
        "l'API). Un groupe est une simple liste d'offering_id ; une offre peut appartenir à "
        "plusieurs groupes à la fois. Deux groupes qui partagent une offre se chevauchent : leurs "
        "totaux ne doivent alors pas être additionnés sans vérifier ce recouvrement.",
    ),
    (
        "Niveau d'analyse",
        "Chaque indicateur ou graphique du dashboard porte sur un seul niveau à la fois : "
        "offerings, endpoints, permissions consommateur, permissions producteur, ou groupes "
        "utilisateur. Ces niveaux se recouvrent (un endpoint sert plusieurs offerings, un groupe "
        "est fait d'offerings, etc.) : on ne les additionne jamais entre eux.",
    ),
    (
        "Hits",
        "Nombre de requêtes comptabilisées par l'API Stats pour l'objet et la période concernés.",
    ),
    (
        "Volume transféré (data_transfer)",
        "Volume de données, en octets, renvoyé par l'API Stats pour l'objet et la période "
        "concernés ; affiché en Ko/Mo/Go/To dans les indicateurs et les exports.",
    ),
    (
        "Statut de couverture",
        "complete_coverage : l'activité observée couvre toute la période demandée. "
        "partial_coverage : l'activité observée n'en couvre qu'une partie (cela ne signifie pas "
        "que des données manquent, seulement que l'usage réel est concentré sur une partie de la "
        "période). no_temporal_detail : un total existe mais l'API n'a renvoyé aucun point "
        "temporel exploitable. no_usage : aucune requête sur la période. not_connected : cet "
        "objet n'est pas raccordé à la route Stats (HTTP 404). error : l'appel a échoué.",
    ),
]
