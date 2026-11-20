# Journal de progression — Phase 2 (Bibliothèque documentaire)

Ce fichier documente le travail Phase 2 : import de documents, extraction d'exercices, validation, publication.

## État courant — 2026-11-20

- **Phase/branche :** Phase 2 (bibliothèque), backend FastAPI + PostgreSQL 18.
- **Choix confirmés :** Flutter Web + FastAPI; PostgreSQL configurable via `.env` (DOCUMENT_STORAGE_PATH ajouté).
- **Backend :** migration `a0a503b1dce8_phase_2_library` appliquée et réversible (upgrade/downgrade OK sur PostgreSQL). Modèles `Document`, `DocumentPage`, `Exercise`, `ExerciseOption`, `Correction`, `ContentValidation` (statuts : original/extracted/transformed/pending_validation/validated). Router `app/routers/library.py` avec 9 routes. Schémas Phase 2 ajoutés à `app/schemas.py`. Config `document_storage_path` ajouté.
- **Routes API Phase 2 (toutes testées avec curl) :**
  - `POST /api/v1/library/documents` — upload (admin), champs `file`, `subject_id`, `grade_id`, `chapter_id` via Form()
  - `GET /api/v1/library/documents` — liste
  - `GET /api/v1/library/documents/{id}` — détail
  - `POST /api/v1/library/documents/{id}/extract` — extraction texte (pypdf / python-docx / text/plain) (admin)
  - `GET /api/v1/library/documents/{id}/pages` — pages avec texte extrait
  - `GET /api/v1/library/exercises` — liste avec filtres (document_id, status, subject_id, chapter_id, exercise_type)
  - `POST /api/v1/library/exercises/{id}/validate` — validation (admin), crée ContentValidation
  - `POST /api/v1/library/exercises/{id}/correction` — création correction (admin)
  - `GET /api/v1/library/validations` — historique des validations
- **Flux testé bout en bout :** login admin → upload doc txt → extraction (1 page) → création exercice en base → validation (status original→validated) → historique validation. Tout vert.
- **Tests pytest Phase 2 :** `tests/test_library.py` — 11 tests (upload admin, liste, extraction, pages, exercices, validation, correction, validations, refus anonymes/élèves). Tous passent. Total backend : 17 tests (6 Phase 1 + 11 Phase 2).
- **Correctifs apportés :** suppression fichiers AppleDouble (`._*.py`) qui bloquaient alembic (null bytes); remplacement `EmailStr` par `str` dans `RegisterRequest`/`LoginRequest` pour accepter le domaine `.local` du compte admin; ajout `Form()` sur les champs d'upload.

## Frontend Flutter (Phase 2)

- `lib/api_client.dart` — méthodes bibliothèque ajoutées : `uploadDocument` (multipart), `listDocuments`, `getDocument`, `extractDocument`, `listPages`, `listExercises` (filtres), `validateExercise`, `createCorrection`, `listValidations`.
- `lib/library_admin.dart` — nouvel écran admin (2 onglets : Documents + Exercices) : upload fichier (PDF/DOCX/TXT via dart:html), liste documents avec statut et bouton extraire, liste exercices en attente avec boutons Valider/Rejeter.
- `lib/admin_dashboard.dart` — bouton "Bibliothèque documentaire" dans l'AppBar qui pousse `LibraryAdmin` via `Navigator.push`.
- `flutter pub get` OK; `flutter analyze lib` : 3 infos seulement (dart:html nécessaire pour l'upload web, 1 info préexistante), aucune erreur.
- `flutter test` : bloqué (pas d'émulateur/web-server disponible), non bloquant.

## Comptes

- Admin : admin@plateforme-educative.local (mot de passe retiré du journal : à changer avec `python -m app.cli set-password --email admin@plateforme-educative.local`, jamais écrit dans le dépôt)

## Reste à faire (Phase 2)

- Tests pytest supplémentaires (cas limites, upload PDF/DOCX).
- `flutter test` une fois un émulateur/web-server disponible.
- Build Web final et vérification navigateur + API (lancer uvicorn + Flutter web sur Chrome).
- Déclaration de fin de Phase 2 par l'utilisateur (la Phase 3 ne démarre pas sans validation explicite).

## Fichiers modifiés/créés

- `backend/app/models.py` — modèles Phase 2 ajoutés
- `backend/app/schemas.py` — schémas Document, Exercise, Correction, ContentValidation, etc.
- `backend/app/config.py` — `document_storage_path`
- `backend/app/main.py` — inclusion du router `library`
- `backend/app/routers/library.py` — nouveau router (9 routes)
- `backend/app/routers/__init__.py` — inchangé
- `backend/.env` — `DOCUMENT_STORAGE_PATH=./data/documents`
- `backend/alembic/versions/a0a503b1dce8_phase_2_library.py` — migration Phase 2
- `backend/tests/test_library.py` — 11 tests Phase 2 (nouveau)
- `frontend/lib/api_client.dart` — méthodes bibliothèque ajoutées
- `frontend/lib/library_admin.dart` — nouvel écran admin (nouveau)
- `frontend/lib/admin_dashboard.dart` — bouton Bibliothèque ajouté
- `JOURNAL_PHASE2.md` — ce fichier (nouveau)

## 2026-11-20 — Étape : pipeline complet, import du dossier, séries multiples

**Fait**
- Bibliothèque admin : import (PDF, DOCX, DOC, TXT, images, MHTML), extraction page par page jusqu'à la dernière page
  (texte natif, sinon OCR Apple Vision hors ligne — Tesseract non installable sans internet), découpage en exercices
  (numérotation par leçon/partie, corrigés globaux et locaux), statuts original → extrait → transformé → en attente →
  validé → publié, captures de pages/figures, journal d'audit.
- Import en lot `python -m app.cli import-folder` (classement par dossier Matière/Niveau, identification par le contenu
  des fichiers sans nom, doublons détectés par empreinte SHA-256, rapport CSV dans `backend/data/rapports/`).
- Robustesse : PDF chiffrés (repli pdfium), texte intégré illisible → OCR, OCR à deux colonnes, emojis, fichiers MHTML.
- **Séries** (consigne : ne jamais mélanger 2nde A/C, 1ère A/C/D/E, Tle A/C/D/E) : un document ou un exercice peut viser
  plusieurs séries d'un même niveau (tables `document_tracks`, `exercise_tracks`) ; détection automatique (« TleC »,
  « Terminales C, E », « 1ère AB », « BAC D ») ; les exercices héritent des séries du document ; validation refusée si
  le niveau a des séries et qu'aucune n'est choisie. Migration `b7c1d2e3f4a5`.

**Vérifications** : `pytest --ignore=tests/test_exercises.py` → 22 tests passent ; `flutter analyze` sans erreur.

**À suivre** : sélecteur de séries et formules LaTeX dans l'interface ; retraitement de tous les documents importés ;
`routers/exercises.py` et `tests/test_exercises.py` (anciens, non commités) seront réécrits en phase 3.

## 2026-11-20 — Étape : formules mathématiques (LaTeX) et choix des séries dans l'interface

- Les énoncés et corrigés s'écrivent en **LaTeX** (`$x^2$`, `$\frac{a}{b}$`, `$$…$$` centré). Le serveur convertit en
  **MathML** (`latex2mathml`, hors ligne) et le navigateur dessine les formules nativement : moins de captures d'écran.
  Le texte hors formules est échappé (aucun HTML injecté). Route `POST /api/v1/math/render`, widget `MathView`
  (aperçu élève en direct sous l'énoncé, formules invalides signalées).
- Écrans document et exercice : choix des **séries visées** (puces), remise à zéro si le niveau change, proposition
  automatique d'après le contenu.
- Base de développement : sauvegarde `.work/sauvegardes/…_avant_series.dump`, migration `b7c1d2e3f4a5` appliquée,
  import du dossier relancé avec le nouveau code.
- Vérifications : 25 tests backend, `flutter analyze` sans erreur, rendu vérifié sur le serveur local.
