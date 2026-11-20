# Journal — Phase 3 : espace d'exercices

## 2026-11-20 — Étape : API élève, correction côté serveur, règles d'accès aux corrigés

**Fait**
- L'élève ne voit que les exercices **publiés et validés** de son **niveau validé** et de **sa série** (un exercice
  Tle C n'est jamais proposé en Tle A ; un élève sans série ne voit que les exercices sans série).
- Réponses corrigées **par le serveur** : QCM / vrai-faux (réponse partielle possible), numérique (virgule, fraction,
  tolérance), à compléter (plusieurs réponses acceptées séparées par « | », sans tenir compte des accents/majuscules),
  réponses libres enregistrées pour comparaison au corrigé. Délai anti-rafale de 3 s ; le score n'est jamais envoyé
  par le navigateur.
- **Accès au corrigé configurable** (réglage général + règle propre à un exercice) : toujours, après une première
  réponse (défaut), après une bonne réponse ou N essais, jamais. La bonne réponse n'est envoyée qu'à ce moment.
- Consultations de corrigés enregistrées ; une réponse donnée après avoir vu le corrigé est marquée et ne compte pas
  comme réussie (préparation phase 7 : la maîtrise ne se déduit pas de la consultation d'un corrigé).
- Images et captures servies à l'élève uniquement si l'exercice lui est visible.
- Migration `c4d5e6f7a8b9` (réversible, testée dans les deux sens ; sauvegarde `…_avant_phase3.dump`).

**Vérifications** : 29 tests backend (dont 3 nouveaux : séries, correction serveur et triche, règles d'accès).

**Note** : les anciens fichiers non versionnés `routers/exercises.py` et `tests/test_exercises.py` ne sont plus
utilisés (remplacés par `routers/student.py` et `tests/test_student.py`) ; ils ne sont pas supprimés sans votre accord.
