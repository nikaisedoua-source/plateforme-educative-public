# SPEC.md — Spécifications techniques

**Référence fonctionnelle** : `Cahier_des_charges_plateforme_educative_CE1_BTS.docx` (v1.1, CE1 au BTS).  
**Référence processus** : `RÔLE.docx` (règles du développeur, 8 phases, règles GitHub).

---

## 1. Périmètre

Plateforme éducative d'exercices, de mémorisation et de révision intelligente, du CE1 au BTS.
Les contenus scolaires proviennent **exclusivement** des documents importés et validés par l'administrateur.

## 2. Architecture technique (suivant §16 du cahier)

| Couche | Technologie | Statut |
|--------|-------------|--------|
| Frontend | Flutter web | Décidé (RÔLE.docx) |
| Backend | FastAPI (Python) | Décidé (option retenue) |
| Base de données | PostgreSQL (sur disque dur de l'utilisateur, chemin configurable via `.env`) | Décidé |
| Stockage documentaire | Dossier dédié sur le disque (documents originaux, fichiers traités, images) | Décidé |

**Contrainte majeure (RÔLE.docx)** : le Flutter ne se connecte **JAMAIS directement** à PostgreSQL. Tout passe par le backend.

## 3. Schéma de base de données (§16.3 du cahier)

Entités principales :
- `users` — utilisateurs (élèves, administrateurs)
- `student_profiles` — profils élèves (niveau, classe, pseudo)
- `schools` — établissements
- `educational_cycles` — cycles (primaire, collège, lycée, BTS)
- `grades` — niveaux (CE1…Terminale, BTS)
- `classes` — classes
- `tracks` — parcours/séries/spécialités
- `subjects` — matières / unités d'enseignement
- `chapters` — chapitres
- `documents` — documents importés par l'admin
- `document_pages` — pages des documents
- `exercises` — exercices extraits
- `exercise_questions` — questions des exercices
- `corrections` — corrections associées
- `content_validation` — statuts (original, extrait, transformé, en attente, validé)
- `flashcards` — cartes mémoire
- `quizzes` — quiz
- `quiz_attempts` — tentatives quiz
- `exercise_attempts` — tentatives exercices
- `memory_methods` — méthodes de mémorisation
- `revision_schedules` — planning répétition espacée
- `student_progress` — progression élève
- `leaderboard_scores` — scores classements
- `weekly_rankings` — classements hebdomadaires
- `notifications`
- `audit_logs` — journal des modifications

Règles : relations cohérentes, identifiants stables, règles d'accès, historique des modifications.

## 4. Découpage en 8 phases (ordre strict, §20 du cahier)

| Phase | Nom | Critère de fin |
|-------|-----|----------------|
| 1 | Fondations | Admin crée niveau/classe/matière/chapitre ; élève s'inscrit ; accès non autorisé refusé côté serveur ; migrations réversibles ; sauvegarde/restauration testée |
| 2 | Bibliothèque documentaire | Document importé → exercices extraits comparables à l'original ; rien publié sans validation ; chaque exercice garde sa référence source |
| 3 | Espace d'exercices | Règles d'accès à la correction configurables ; résultats validés côté serveur ; formules/images/tableaux affichés |
| 4 | Mémorisation et révisions | Notions mal maîtrisées reviennent plus souvent ; historique conservé ; exemples des méthodes issus des documents |
| 5 | Intelligence artificielle | RAG, extraction assistée, génération contrôlée ; IA cite ses sources ; hors-corpus signalé ; rien publié sans validation humaine |
| 6 | Classements | Barème configurable ; clôture hebdomadaire archivée ; tentatives de triche testées ; affichage limité à pseudo/classe/score |
| 7 | Tableaux de bord | Maîtrise ne se déduit pas de la simple consultation d'une correction ; notifications paramétrables |
| 8 | Optimisation et déploiement | Audit sécurité rôles et données mineurs ; sauvegardes testées ; guide de déploiement en français ; plan d'accès élèves validé |

**Règle** : une phase n'est commencée que si la précédente est terminée et validée par l'utilisateur.

## 5. Hypothèses et décisions (validées)

1. **Frontend** : Flutter web (décision prise, contradiction avec le cahier §16.1 levée en faveur du RÔLE.docx).
2. **Backend** : FastAPI (Python), SQLAlchemy 2.0, Alembic (décision prise).
3. **Chemin PostgreSQL** : configurable via `.env`, jamais codé en dur, sur le disque de l'utilisateur.
4. **Dépôt GitHub** : privé, à confirmer avant premier push.
5. **Compte administrateur par défaut** : `admin@plateforme-educative.local` (mot de passe dans `.env`, jamais committé).
6. **Données de test** : marquées « DEMO », non publiables.
7. **Séries et spécialités** (`tracks`) : ajoutées dès la Phase 1, rattachées à un niveau, de type série, spécialité, option ou filière ; intitulés saisis par l'administrateur (décision utilisateur, 2026-11-20).
8. **Parcours élève** : l'élève choisit niveau, puis série/spécialité et classe facultatives, à l'inscription ou depuis son profil ; l'affectation reste « en attente » jusqu'à validation par un administrateur (cahier §13 ; décision utilisateur, 2026-11-20).
9. **Code Phases 2-3 anticipé** : gelé (non modifié, non commité sur la branche Phase 1) jusqu'à validation de la Phase 1.

---

## 6. Règles non négociables (§2, §19, §22 du cahier + RÔLE.docx)

- Documents fournis = **unique source** des contenus scolaires. Rien d'Internet, rien des connaissances générales de l'IA.
- Chaque contenu conserve sa référence source (document, page, numéro).
- Cinq statuts de contenu : original → extrait → transformé → en attente de validation → validé.
- Aucun score modifiable par l'apprenant ; validation serveur uniquement.
- Niveaux, classes, matières, chapitres configurables par l'admin sans modifier le code.
- Données des mineurs : collecte minimale, aucune donnée sensible dans les classements publics.
- Une branche par phase, une PR par phase, jamais de push direct sur `main`.
- Pas de secrets, `.env`, fichiers de base, documents pédagogiques, données élèves sur GitHub.
- `.gitignore` préparé dès le début.
- Pas de contenu scolaire fictif (sauf données de test marquées « DEMO », non publiables).
