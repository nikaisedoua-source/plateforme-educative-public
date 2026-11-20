# AGENTS.md

Dépôt : `codes/` — Flutter web (`frontend/`) + FastAPI (`backend/`) + PostgreSQL local.
Références : `SPEC.md` (architecture, schéma, 8 phases), `RÔLE.docx` (règles processus),
`Cahier_des_charges_plateforme_educative_CE1_BTS.docx` (source de vérité, ne jamais modifier).
Journal d'avancement : `JOURNAL_PHASE1.md`, `JOURNAL_PHASE2.md` (une note après chaque étape).

## Structure du dépôt

```
codes/
├── SPEC.md / AGENTS.md / CLAUDE.md (→ AGENTS.md)
├── demarrer.sh          # lance API (8000) + Flutter web (8080)
├── backend/             # FastAPI, SQLAlchemy 2, Alembic (app/, alembic/, tests/)
├── frontend/            # Flutter web canonique (lib/, test/, web/)
├── documents_organisés/ # documents pédagogiques (jamais commités)
├── lib/, plateforme_educative_flutter*/  # anciens prototypes DEMO, ne pas modifier
└── prototype HTML       # référence visuelle
```

## Commandes

### Installation
```bash
cd backend && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]" && cp .env.example .env
cd frontend && ~/flutter/bin/flutter pub get     # Flutter n'est pas dans le PATH
```

### Lancer
```bash
./demarrer.sh            # puis http://localhost:8080 ; API : http://127.0.0.1:8000/docs
```

### Analyse et tests
```bash
cd backend && .venv/bin/pytest                    # SQLite en mémoire
cd frontend && ~/flutter/bin/flutter analyze && ~/flutter/bin/flutter test
```

### Migrations (Alembic, PostgreSQL)
```bash
cd backend
.venv/bin/alembic upgrade head
.venv/bin/alembic downgrade -1       # réversible (requis)
.venv/bin/alembic check              # modèles == schéma migré
```
Vérifier sur base vierge : `createdb -h localhost <base_jetable>` puis
`DATABASE_URL=postgresql+psycopg://<user>@localhost:5432/<base_jetable> .venv/bin/alembic upgrade head`.

### Comptes administrateur (saisie masquée, jamais de mot de passe dans le dépôt)
```bash
cd backend
.venv/bin/python -m app.cli create-admin --email <email>
.venv/bin/python -m app.cli set-password --email <email>
```

### Sauvegarde / restauration DB
```bash
pg_dump --format=custom --file=backup.dump "$DATABASE_URL"
pg_restore --clean --if-exists --no-owner --dbname="$DATABASE_URL_TEST" backup.dump   # base jetable uniquement
```

## Conventions

- Interface en français ; code, identifiants, noms de tables en anglais.
- Une branche par phase : `phase-N-nom-court`. Une PR par phase. Jamais de push sur `main`.
- Commits petits et clairs. Pas de push avant confirmation que le dépôt GitHub est privé.
- Plan validé par l'utilisateur avant tout code d'une phase ; bilan puis arrêt en fin de phase.

## Règles non négociables

- Ne jamais commiter : secrets, `.env`, mots de passe, bases, documents pédagogiques importés
  (`backend/data/`), données élèves.
- Le chemin PostgreSQL est configurable via `.env`, jamais codé en dur.
- Le frontend ne se connecte jamais directement à la base (tout par le backend).
- Documents fournis = unique source des contenus scolaires (pas d'Internet, pas de connaissances IA).
- Chaque contenu garde sa référence source (document, page, numéro).
- Cinq statuts : original → extrait → transformé → en attente de validation → validé.
- Pas de contenu scolaire fictif (sauf données de test « DEMO », non publiables).
- Une phase ne démarre que si la précédente est terminée et validée par l'utilisateur.
- Aucune suppression de fichiers ni commande destructive sans accord de l'utilisateur.

## Parcours élève (Phase 1)

Niveau → série/spécialité (`tracks`, facultatif) → classe (facultatif). L'élève choisit à
l'inscription ou depuis son profil ; `enrollment_status` passe à `pending` ; l'admin valide ou
refuse (`/api/v1/admin/enrollments`). Le catalogue public `/api/v1/catalog` ne contient aucune
donnée élève.

## Pièges connus

- **Disque exFAT** : macOS crée des fichiers `._*` (AppleDouble) à chaque écriture. Ils cassent
  Python (« null bytes »). `alembic/env.py` les ignore pour `upgrade`/`downgrade` ;
  `demarrer.sh` lance `dot_clean -m`. `alembic history/heads` peut encore échouer : `dot_clean -m backend`.
- L'aperçu navigateur de l'app Claude ne peut pas lancer de serveur sur ce volume (permission
  macOS) : lancer les serveurs depuis le shell puis ouvrir `http://localhost:8080`.
- Code Phases 2-3 (`library.py`, `exercises.py`, migrations `a0a503b1dce8`, `3969043719cd`) écrit
  avant validation de la Phase 1 : gelé, ne pas le commiter sur la branche phase 1.
- Écarts connus signalés par `alembic check` (antérieurs) : FK `exercises.chapter_id`
  (CASCADE vs SET NULL), index `users.email`.
- Fichiers aux noms obscurs dans `documents_organisés/Divers/` : à classifier par l'administrateur.
- `EmailStr` refuse le domaine `.local` : les schémas d'auth utilisent `str`.
