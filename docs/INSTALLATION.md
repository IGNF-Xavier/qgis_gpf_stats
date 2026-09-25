# Procédure d'installation

## Depuis le ZIP (utilisateur final)

1. QGIS → **Extensions → Installer/Gérer les extensions → Installer depuis un ZIP**.
2. Choisir `geoplateforme_usage_stats_plugin_7.2.0.zip`.
3. Cliquer **Installer le plugin**. QGIS décompresse l'archive dans le dossier `python/plugins/geoplateforme_usage_stats` du profil actif.
4. Activer la case de l'extension dans l'onglet **Extensions installées** si elle n'est pas déjà cochée.
5. Le menu **Extensions → Statistiques analytiques Géoplateforme** apparaît avec deux entrées : **Ouvrir…** et **Configurer OAuth2…**.

## Installation manuelle (sans passer par le gestionnaire)

1. Fermer QGIS.
2. Décompresser `geoplateforme_usage_stats_plugin_7.2.0.zip` de façon à obtenir un dossier `geoplateforme_usage_stats/` (contenant directement `__init__.py`, `metadata.txt`, etc. — pas de dossier intermédiaire).
3. Copier ce dossier dans `python/plugins/` du profil QGIS actif :
   - Windows : `%APPDATA%\QGIS\QGIS3\profiles\<profil>\python\plugins\`
   - Linux/macOS : `~/.local/share/QGIS/QGIS3/profiles/<profil>/python/plugins/`
4. Relancer QGIS, puis activer l'extension dans **Extensions → Installer/Gérer les extensions → Installées**.

## Vérification après installation

- `Extensions → Statistiques analytiques Géoplateforme → Configurer OAuth2…` doit ouvrir une fenêtre de sélection de configuration OAuth2 QGIS.
- `Extensions → Statistiques analytiques Géoplateforme → Ouvrir…` doit ouvrir la fenêtre principale (3 onglets : Consommateur, Producteur, Dashboard) sans message d'erreur dans le panneau **Journal des messages** de QGIS (onglet Python).

## Désinstallation

**Extensions → Installer/Gérer les extensions → Installées → Statistiques analytiques Géoplateforme → Désinstaller le plugin.** Le cache local et les groupes enregistrés (dans `QgsSettings`, indépendants du dossier du plugin) ne sont pas supprimés par une désinstallation — voir `MIGRATION_6.1_VERS_7.0.md` pour leur emplacement.
