# Journal de progression — Phase 1 (Fondations)

Ce fichier est le point de reprise partagé pour les agents qui travaillent sur le dépôt. Ajouter une entrée datée après chaque étape importante : décision, changement de code/configuration, test, installation ou blocage. Ne pas y inscrire de secret ni de donnée réelle d’élève.

## État courant — 2026-11-20

- **Phase/branche :** Phase 1, `phase-1-fondations`.
- **Choix confirmés par l’utilisateur :** Flutter Web + FastAPI; PostgreSQL configurable via `.env`.
- **Commits locaux :** `2a6df0e` — fondations FastAPI; `2757c20` — corrections des messages français et exclusions locales.
- **Backend :** API FastAPI, authentification élève/admin, contrôle d’accès serveur, routes admin de création/liste des cycles, niveaux, classes, matières et chapitres, migration Alembic réversible, commande sécurisée de création du premier admin.
- **Vérifications réussies :** `pytest` — 6 tests; migration `upgrade → downgrade base → upgrade` sur SQLite temporaire; compilation syntaxique de 16 fichiers Python; `git diff --check`.
- **Environnement :** PostgreSQL 18 installé et démarré (Homebrew, `brew services start postgresql@18`). Flutter SDK 3.50.1 installé dans `~/flutter` (clone Git, cask Homebrew bloqué). `psql`, `pg_dump`, `flutter`, `dart` disponibles dans le PATH.
- **Avant de déclarer la Phase 1 terminée :** exécuter les migrations puis un dump/restore sur une base PostgreSQL jetable; exécuter `flutter pub get`, `flutter analyze`, `flutter test`; vérifier l’intégration navigateur/API. La Phase 2 ne commence pas avant validation explicite de l’utilisateur.
- **Dépôt :** aucune poussée distante. Fichiers utilisateur préexistants (cahier, documents, variantes Flutter/prototype) laissés intacts et non indexés. `SPEC.md` et `AGENTS.md` non modifiés.

## Historique

### 2026-11-20 — décisions et démarrage

- L’utilisateur a demandé de reprendre le travail de KILO qui semblait bloqué, en privilégiant l’efficacité et en tenant compte du budget de crédits.
- Choix confirmé : Flutter Web + FastAPI.
- Création initiale du `.gitignore`, branche locale `phase-1-fondations`, puis commit `2a6df0e`.

### 2026-11-20 — fondations API

- Ajout du backend FastAPI avec SQLAlchemy/Alembic, configuration `.env`, tables de comptes et référentiels pédagogiques, inscription élève, connexion JWT, contrôle des rôles côté serveur, endpoints d’administration et commande locale sécurisée de création du premier administrateur.
- Tests backend : 6 réussis. Cycle Alembic vérifié sur SQLite temporaire; ce n’est pas encore le test PostgreSQL/dump-restore demandé.

### 2026-11-20 — vérifications Flutter

- `flutter pub get` OK (25 dépendances résolues).
- `flutter analyze` : 30 "info" uniquement (dépréciations liées à Flutter 3.50 très récent, pas d'erreur ni de warning bloquant). Ces infos concernent `package:flutter/material.dart` déprécié au profit de `material_ui`, `withOpacity` → `withValues`, `value` → `initialValue`. Non bloquant pour Phase 1.
- `flutter test` : aucun dossier `test` présent — pas de tests Flutter écrits encore (non requis par le cahier pour la validation Phase 1).

**Reste à faire avant de déclarer Phase 1 terminée :**
- Créer le premier admin : `cd backend && source .venv/bin/activate && python -m app.cli create-admin --email <email>`
- Vérifier l’intégration navigateur/API (Flutter web qui appelle le backend FastAPI)
- Validation explicite de l’utilisateur pour passer à Phase 2

### Suivi demandé par l’utilisateur — 2026-11-20

- À partir de maintenant, ajouter ici une note après chaque étape, puis garder le journal à jour dans le dépôt pour que KILO puisse consulter l’avancement.


### 2026-11-20 — journal partagé et état de l’installation (01:47 UTC)

- Ajout de ce journal au dépôt par commit `90cca2e`, afin que les agents qui partagent le projet puissent reprendre sur une référence stable.
- Vérification : le projet n’expose pas de tâche KILO distincte dans la liste Manus accessible; le fichier commité à la racine du dépôt est donc le point de passage partagé.
- Homebrew indique toujours l’installation en cours. La liste des formules installées ne montre encore ni PostgreSQL 18 ni Flutter. Les commandes de diagnostic processus sont bloquées par la permission locale (`ps: Operation not permitted`); aucune seconde installation n’a été lancée.


### 2026-11-20 — Flutter et PostgreSQL détectés (01:55 UTC)

- L’utilisateur a confirmé Flutter 3.50.1; vérification réussie par `~/flutter/bin/flutter`. Dart 3.14.0. Le répertoire SDK n’est pas ajouté au `PATH` de cet environnement; préfixer `PATH=~/flutter/bin:$PATH` pour les commandes.
- PostgreSQL `psql` et `pg_dump` 18.7 (Homebrew) sont installés et accessibles. Aucun serveur ne répond sur le port standard 5432; les tests suivants utiliseront un cluster temporaire, jamais une base utilisateur.
- La commande Homebrew démarrée précédemment s’est terminée en échec parce qu’elle attendait une réponse interactive `y/n` avant de commencer l’installation. PostgreSQL étant déjà présent et Flutter confirmé, ne pas relancer Homebrew.
- Prochaine étape : valider `pub get`/analyse/tests Flutter et exécuter les migrations + sauvegarde/restauration sur PostgreSQL temporaire.


### 2026-11-20 — premières validations Flutter/PostgreSQL (01:58 UTC)

- `flutter pub get` a réussi avec Flutter 3.50.1; packages résolus dans `.work/tools/pub-cache`. Le répertoire actif est la racine `lib/`; il n’y a pas encore de dossier `web/` ni de tests `test/` à la racine.
- `flutter analyze` à la racine analysait également deux copies Flutter préexistantes. Analyse ciblée `lib/` : 10 avis de dépréciation uniquement (imports `material.dart`, `withOpacity`, et une propriété de formulaire), sans avertissement de type/lint distinct; la commande retourne néanmoins le code 1. Ne pas masquer les avis sans décision.
- Première tentative de cluster PostgreSQL isolé : l’accès réseau local sur port fixe a été accepté, mais `initdb` s’est arrêté sur les variables de locale système avant de créer la base. Aucun dump ni changement de base utilisateur; relancer avec `--locale=C --encoding=UTF8` et `LANG=C`.


### 2026-11-20 — PostgreSQL validé, état Flutter (02:00 UTC)

- PostgreSQL 18.7 : test effectué sur un cluster temporaire local, avec locale `C`, port 55439 et données exclusivement marquées `DEMO`. Le cycle Alembic `upgrade → downgrade base → upgrade` passe; `pg_dump` custom puis `pg_restore` sur une seconde base restaurent la ligne `DEMO` et la version `0001_phase1`. Le cluster temporaire a été arrêté et supprimé.
- Flutter : `pub get` passe. `flutter analyze lib --no-pub --no-fatal-infos` rapporte 10 avis de dépréciation dans le prototype racine et retourne 1; aucune correction de migration Material n’a été faite, car elle touche largement le prototype existant et mérite un choix de KILO. `flutter test --no-pub` ne peut pas démarrer : le dossier `test/` n’existe pas.
- Le Flutter racine ne contient pas non plus de dossier `web/`; les répertoires Flutter historiques sont des copies présentes à la racine et n’ont pas été déplacés, copiés ou modifiés.
- **Suite recommandée à KILO :** choisir le répertoire Flutter canonique (`frontend/` selon `AGENTS.md` ou conserver le projet racine), ajouter le squelette Web et tests; brancher l’inscription/connexion/admin sur FastAPI. Le backend et les critères de migration/sauvegarde Phase 1 sont prêts; la Phase 1 entière n’est pas déclarée terminée tant que le frontend n’est pas vérifié et que l’utilisateur ne l’a pas validée.
