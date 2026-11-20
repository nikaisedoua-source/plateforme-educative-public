# Journal — Phase 4 : mémorisation et révisions

## 2026-11-20 — Cartes mémoire, méthodes, répétition espacée, publication automatique

- Cartes mémoire extraites des documents (définitions, formules, vrai/faux, à compléter, numériques), chacune
  rattachée à son document et à sa page ; méthodes d'apprentissage du cahier (§6) en brouillon, rédigées puis
  validées par l'administrateur ; répétition espacée réglable (premiers intervalles, facilité minimale, intervalle
  maximal, seuil de maîtrise, nouvelles cartes par jour). Les notions ratées reviennent plus souvent ; tout
  l'historique est conservé.
- Publication automatique (décision utilisateur du 2026-11-20) : rien sans niveau, matière et, au lycée, série
  reconnus ; les séries ne sont jamais mélangées (déduites du contenu et des programmes officiels).

## Réécriture des énoncés par un modèle local

- Modèle `qwen2.5vl:7b` (Ollama, sur la machine, aucune donnée envoyée à l'extérieur). L'énoncé est relu sur la
  **zone recadrée** de la page, réécrit en LaTeX, découpé en questions ; les résultats attendus viennent
  **uniquement du corrigé** du document (jamais inventés). Un énoncé douteux reste marqué « doubtful ».
- Commande `python -m app.cli rediger [ids] --documents … [--refaire] [--matieres] [--limite] [--sans-corrige]
  [--corrige-seulement]` ; `--corrige-seulement` relit seulement les corrigés pour remplir les résultats attendus.
- Numéros de questions rapprochés entre énoncé et corrigé (« 2.a » ↔ « a) »).
- Cache des images versionné (`CROP_VERSION`) : un changement de recadrage recalcule les images d'origine.

## Vérification de chaque exercice publié et de chaque document

- Commande `python -m app.cli verifier [--simuler]` : contrôle qualité (énoncé lisible, ni coupé, ni fusionné,
  ni sommaire), niveau, matière, séries du bon niveau, doublons. Un exercice qui échoue est **retiré de la
  publication** (jamais supprimé, raison notée au journal d'audit) ; s'il a déjà été travaillé par un élève, il est
  seulement signalé.
- Rapport par document : pages extraites, exercices trouvés et publiés, raison quand un document n'apporte rien
  (livre de corrigés, cours ou ouvrage de référence, extraction en échec).
- Import du dossier `documents` à la racine (`import-folder … --create-referentials --segment`), doublons écartés
  par empreinte SHA-256, puis `retraiter` et `publier-tout`.
- Détection du type de document : livres de corrigés reconnus au nom ; sujets de lettres et d'histoire-géographie
  découpés en sujets ; examens à plusieurs épreuves découpés par matière, barème rangé en corrigés.
- Hypothèses à confirmer : « Sciences et technologie » rangée en SVT ; l'EDHC n'est pas au catalogue des
  matières (documents ignorés tant que la matière n'existe pas).

## Espace élève

- Style doux, sons à faible volume (coupables), clavier mathématique MathLive embarqué (hors ligne), espace de
  rédaction pour les démonstrations (facultatives), cartes flash et méthodes.
- L'élève voit la **zone recadrée** de l'exercice (plus la page entière avec les exercices voisins), ouverte
  d'office quand l'énoncé renvoie à une figure ; un seul lien « Voir la correction » en bas de l'exercice.
- Questions qui attendent des mots : champ texte ; réponse comparée comme du texte (articles ignorés, anagrammes
  refusées). Questions de calcul : équivalence mathématique (`x\sqrt{2}` = `\sqrt{2}x`).

## Administration

- Écran **Mémorisation** (bouton dans la barre de l'administration) : cartes filtrées par statut et document,
  rattachement au niveau, aux séries, à la matière et au chapitre, validation, publication, rejet, archivage ;
  méthodes à rédiger (principe, étapes) et valider ; réglages de la répétition espacée.
- 505 cartes extraites restent non publiées : sans chapitre, souvent peu lisibles ; à relire dans cet écran.

## Vérifications

- `pytest` (backend) : tous réussis, hors anciens fichiers non versionnés `test_exercises.py`.
- `flutter analyze` sans problème ; tests Flutter `widget_test`, `parcours_test`, `memory_admin_test` réussis
  (lancés en nommant les fichiers).
- Contrôle à l'écran (élève DEMO, CM2) : matières, liste, énoncé LaTeX, figure recadrée, réponses vérifiées,
  correction. L'écran Mémorisation admin est vérifié par test de widget (pas de compte admin de test utilisé).
