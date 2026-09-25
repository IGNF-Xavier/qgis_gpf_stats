# Migration des groupes 6.1.0 → 7.0.0

## Ce qui change de format

La 6.1.0 stockait les groupes sous `QgsSettings["geoplateforme_usage_stats/groups_61"]` comme un simple mapping JSON `{"nom_du_groupe": ["offering_id", ...]}`, sans identifiant stable, sans description, couleur ni horodatage.

La 7.0.0 introduit un modèle `Group` plus riche (`group_id` stable, `name`, `description`, `color`, `offering_ids`, `created_at`, `updated_at`), stocké sous une nouvelle clé `QgsSettings["geoplateforme_usage_stats/groups_v7"]`.

## Migration automatique

Au premier appel de `GroupService.load()` (déclenché à l'ouverture de la fenêtre principale) :

1. si la clé `groups_v7` existe déjà, elle est utilisée telle quelle (pas de re-migration) ;
2. sinon, si l'ancienne clé `groups_61` contient des données, `core.group_service.migrate_from_v61()` les convertit : chaque entrée devient un `Group` avec un nouvel identifiant stable généré (`uuid4`), une description `"Groupe migré depuis la version 6.1.0."`, et la même liste d'`offering_id` (dédupliquée et triée) ;
3. le résultat est immédiatement sauvegardé sous `groups_v7` — la migration ne s'exécute donc qu'une seule fois.

Aucune action manuelle n'est nécessaire. Les noms de groupes et les affectations d'offres sont préservés à l'identique.

## Ce qui n'est pas migré

- L'ancienne clé `groups_61` n'est **pas supprimée** (elle est seulement laissée de côté après la première migration), au cas où l'utilisateur souhaiterait revenir à la 6.1.0.
- La 6.1.0 ne stockait ni description, ni couleur : ces champs sont vides après migration et peuvent être renseignés depuis la fenêtre **Composer les groupes…** (Renommer ne modifie que le nom ; il n'y a pas encore d'édition de la description dans l'UI de cette version — elle est disponible au niveau du modèle `Group` pour un usage futur ou scripté).

## Vérifier la migration

Après mise à jour, ouvrir **Composer les groupes…** : les groupes précédemment créés doivent apparaître avec le même nom et le même nombre d'offres. Le test `tests/test_group_service.py::test_service_loads_and_migrates_legacy_store` couvre ce scénario.
