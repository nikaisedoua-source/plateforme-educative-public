# Backend - FastAPI

API de fondation de la plateforme educative. Aucun exercice scolaire fictif ne sera integre au service. Les documents fournis restent la seule source du contenu pedagogique.

## Preparation

Depuis le dossier `backend/` :

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
```

Editez `.env` localement. `DATABASE_URL` doit pointer vers la base PostgreSQL choisie par le proprietaire du projet. Le chemin ne sera jamais code dans le programme. Generez une cle privee neuve :

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Remplacez la valeur exemple de `SECRET_KEY` par cette sortie. Le service refuse la valeur exemple. Ne partagez pas et ne commitez pas `.env`.

## Base et API

```bash
alembic upgrade head
python -m app.cli create-admin --email admin@example.com
uvicorn app.main:app --reload
```

Documentation interactive : `http://127.0.0.1:8000/docs`. Controle de sante : `GET /health`.
Une inscription publique cree toujours un compte `student`. La premiere creation admin se fait en local apres migration, avec saisie masquee du mot de passe. Chaque requete admin verifie le role et le statut du compte en base.

## Routes Phase 1

- `POST /api/v1/auth/register`, `POST /api/v1/auth/login`, `GET /api/v1/auth/me`
- Routes `GET` et `POST` admin pour `/cycles`, `/grades`, `/classes`, `/subjects` et `/chapters`
- Toutes les routes `/api/v1/admin/*` demandent un jeton Bearer associe a un admin actif.

## Migrations et tests

```bash
alembic upgrade head
alembic downgrade -1
alembic upgrade head
pytest
```

La migration `0001_phase1` cree les comptes, profils eleves et references pedagogiques. Son downgrade supprime les tables dans l ordre inverse.

## Sauvegarde et restauration PostgreSQL

Faire le test de restauration uniquement sur une base jetable, jamais sur la base contenant des donnees reelles. Les variables viennent de `.env` :

```bash
pg_dump --format=custom --file=backup.dump "$DATABASE_URL"
pg_restore --clean --if-exists --no-owner --dbname="$DATABASE_URL_TEST" backup.dump
```

Le test reel `pg_dump`/`pg_restore` reste a effectuer sur un poste equipe de PostgreSQL. Ces outils ne sont pas installes ici.

## Portee des tests locaux

Les tests HTTP utilisent une base SQLite en memoire. Ils ne remplacent pas la validation PostgreSQL ni le test de sauvegarde/restauration requis avant la validation finale de la Phase 1.
