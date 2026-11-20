# Journal de progression — Phase 1 (Fondations)

Ce fichier est le point de reprise partagé pour les agents qui travaillent sur le dépôt. Ajouter une entrée datée après chaque étape importante : décision, changement de code/configuration, test, installation ou blocage. Ne pas y inscrire de secret ni de donnée réelle d’élève.

## État courant — 2026-11-20

- **Phase/branche :** Phase 1, `phase-1-fondations`.
- **Choix confirmés par l’utilisateur :** Flutter Web + FastAPI; PostgreSQL configurable via `.env`.
- **Commits locaux :** `2a6df0e` — fondations FastAPI; `2757c20` — corrections des messages français et exclusions locales.
- **Backend :** API FastAPI, authentification élève/admin, contrôle d’accès serveur, routes admin de création/liste des cycles, niveaux, classes, matières et chapitres, migration Alembic réversible, commande sécurisée de création du premier admin.
- **Vérifications réussies :** `pytest` — 6 tests; migration `upgrade → downgrade base → upgrade` sur SQLite temporaire; compilation syntaxique de 16 fichiers Python; `git diff --check`.
- **Environnement :** dépendances Python installées dans `backend/.venv` (ignoré par Git). Installation Homebrew de PostgreSQL 18 et Flutter demandée le 2026-11-20; encore en cours à la dernière vérification (01:46 UTC). `flutter`, `dart`, `psql` et `pg_dump` n’étaient pas visibles dans le `PATH`.
- **Avant de déclarer la Phase 1 terminée :** confirmer l’installation; exécuter les migrations puis un dump/restore sur une base PostgreSQL jetable; exécuter `flutter pub get`, `flutter analyze`, `flutter test`; vérifier l’intégration navigateur/API. La Phase 2 ne commence pas avant validation explicite de l’utilisateur.
- **Dépôt :** aucune poussée distante. Fichiers utilisateur préexistants (cahier, documents, variantes Flutter/prototype) laissés intacts et non indexés. `SPEC.md` et `AGENTS.md` non modifiés.

## Historique

### 2026-11-20 — décisions et démarrage

- L’utilisateur a demandé de reprendre le travail de KILO qui semblait bloqué, en privilégiant l’efficacité et en tenant compte du budget de crédits.
- Choix confirmé : Flutter Web + FastAPI.
- Création initiale du `.gitignore`, branche locale `phase-1-fondations`, puis commit `2a6df0e`.

### 2026-11-20 — fondations API

- Ajout du backend FastAPI avec SQLAlchemy/Alembic, configuration `.env`, tables de comptes et référentiels pédagogiques, inscription élève, connexion JWT, contrôle des rôles côté serveur, endpoints d’administration et commande locale sécurisée de création du premier administrateur.
- Tests backend : 6 réussis. Cycle Alembic vérifié sur SQLite temporaire; ce n’est pas encore le test PostgreSQL/dump-restore demandé.

### 2026-11-20 — reprise, qualité et installation

- Vérification que les dépendances FastAPI sont installées et que le dépôt reste sur la branche Phase 1. Les fichiers utilisateur préexistants à la racine restent non suivis et hors staging.
- Correction de messages français tronqués dans l’API/CLI; complétion du `.gitignore` pour bases, sauvegardes SQL, `.work` et métadonnées AppleDouble; commit `2757c20`.
- Retests après corrections : 6 réussis; syntaxe Python valide; migration SQLite réversible.
- Lancement de `brew install postgresql@18` puis `brew install --cask flutter`, cache/logs locaux sous `.work/`, accès Homebrew demandé. Le processus est toujours marqué en cours; ne pas relancer une seconde installation avant d’en connaître l’issue.
- Des métadonnées AppleDouble ont été générées dans `.git/objects/pack` et `backend`. Les fichiers du répertoire Git ont été retirés après avoir causé des erreurs `non-monotonic index`; les `._*` de `backend/.venv` sont des sidecars et non des sources, ne pas les compiler ni supprimer en masse.

### Suivi demandé par l’utilisateur — 2026-11-20

- À partir de maintenant, ajouter ici une note après chaque étape, puis garder le journal à jour dans le dépôt pour que KILO puisse consulter l’avancement.
