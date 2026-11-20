"""Catalogue des méthodes d'apprentissage repris du cahier des charges (§6), sans autre ajout.

Seuls le nom et la phrase du cahier sont pré-remplis. Le principe, les étapes et les exemples sont rédigés
par l'administrateur, puis la méthode est validée avant d'apparaître chez les élèves (« bibliothèque
méthodologique distincte, approuvée par l'administrateur »).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MemoryMethod

CATALOG: list[tuple[str, str, str, str]] = [
    # (code, catégorie, nom, phrase du cahier)
    ("active_recall", "rappel", "Active Recall", "Rappel actif sans consulter le document."),
    ("spaced_repetition", "rappel", "Spaced Repetition", "Répétition espacée."),
    ("blurting", "rappel", "Blurting Method", "Restitution libre des informations mémorisées."),
    ("practice_testing", "rappel", "Practice Testing", "Apprentissage par les tests."),
    ("retrieval_practice", "rappel", "Retrieval Practice", "Entraînement à la récupération des informations."),
    ("free_recall", "rappel", "Free Recall", "Restitution libre d'un contenu."),
    ("cued_recall", "rappel", "Cued Recall", "Rappel à partir d'indices."),
    ("feynman", "comprehension", "Méthode Feynman", "Expliquer une notion avec des mots simples."),
    ("mind_mapping", "comprehension", "Mind Mapping", "Cartes mentales."),
    ("concept_mapping", "comprehension", "Concept Mapping", "Cartes conceptuelles."),
    ("elaboration", "comprehension", "Elaboration", "Établir des liens et enrichir la compréhension."),
    ("self_explanation", "comprehension", "Self-Explanation", "Auto-explication."),
    ("interleaved_practice", "comprehension", "Interleaved Practice", "Pratique entrelacée."),
    ("chunking", "comprehension", "Chunking", "Regroupement des informations."),
    ("cornell", "comprehension", "Méthode Cornell", "Organisation des notes."),
    ("dual_coding", "comprehension", "Dual Coding", "Association des mots et des représentations visuelles."),
    ("teaching", "comprehension", "Teaching Method", "Apprendre en enseignant."),
    ("loci", "mnemotechnique", "Méthode des loci (palais mental)", ""),
    ("acronymes", "mnemotechnique", "Acronymes et acrostiches", ""),
    ("associations", "mnemotechnique", "Associations visuelles et verbales", ""),
    ("imagerie", "mnemotechnique", "Imagerie mentale", ""),
    ("chainage", "mnemotechnique", "Chaînage des informations", ""),
    ("analogie", "mnemotechnique", "Regroupement et associations par analogie", ""),
    ("pomodoro", "organisation", "Méthode Pomodoro", ""),
    ("planification", "organisation", "Planification des révisions", ""),
    ("cumulative", "organisation", "Révision cumulative", ""),
    ("alternance", "organisation", "Alternance des matières ou unités d'enseignement", ""),
    ("concentration", "organisation", "Séances de concentration", ""),
    ("progressives", "organisation", "Révisions progressives", ""),
]


def ensure_catalog(db: Session) -> None:
    """Ajoute les méthodes manquantes (idempotent ; ne modifie jamais une méthode existante)."""
    existing = set(db.scalars(select(MemoryMethod.code)))
    added = False
    for order, (code, category, name, summary) in enumerate(CATALOG):
        if code not in existing:
            db.add(MemoryMethod(code=code, category=category, name=name, summary=summary, steps=[],
                                status="draft", sort_order=order))
            added = True
    if added:
        db.commit()
