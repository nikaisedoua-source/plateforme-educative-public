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


# ---------------------------------------------------------------------------------------------------------------
# Bibliothèque méthodologique (cahier §6 : « explications générales sur le fonctionnement d'une méthode … dans une
# bibliothèque méthodologique distincte, approuvée par l'administrateur »). Rédigée le 2026-11-20 sur décision du
# propriétaire (« je n'ai rien à approuver, tu as tous les documents à ta disposition »). Ce sont des conseils de
# travail, jamais des contenus scolaires évalués ; les exemples, eux, viennent des documents (voir `attach_examples`).

GUIDE: dict[str, tuple[str, list[str]]] = {
    "active_recall": (
        "Tu apprends mieux en allant chercher l'information dans ta tête qu'en relisant. Chaque effort pour "
        "retrouver une réponse sans regarder le document renforce le souvenir.",
        ["Lis la question ou le titre de la notion, puis cache le document.",
         "Dis ou écris de mémoire tout ce que tu sais.",
         "Compare avec le document et souligne ce qui manquait ou était faux.",
         "Recommence plus tard seulement avec ce que tu avais oublié."]),
    "spaced_repetition": (
        "On oublie vite ce qu'on vient d'apprendre. Revoir une notion juste avant de l'oublier, à des intervalles de "
        "plus en plus longs, la fixe durablement. La plateforme planifie ces retours pour toi dans « Flash ».",
        ["Apprends la notion une première fois.",
         "Revois-la le lendemain, puis après 3 jours, puis après une semaine, puis après un mois.",
         "Si tu te trompes, la notion revient plus tôt ; si tu réussis, l'écart s'allonge.",
         "Fais chaque jour les cartes que la plateforme te propose."]),
    "blurting": (
        "Après avoir étudié une leçon, tu « vides » ta mémoire sur une feuille blanche. Ce que tu n'arrives pas à "
        "écrire, c'est ce qu'il faut retravailler.",
        ["Étudie une partie de leçon pendant 10 à 15 minutes.",
         "Ferme le cahier et écris sur une feuille blanche tout ce dont tu te souviens, sans ordre imposé.",
         "Rouvre le cahier et complète au stylo d'une autre couleur ce qui manquait.",
         "Le lendemain, recommence en visant surtout la couleur ajoutée."]),
    "practice_testing": (
        "Se tester n'est pas seulement mesurer ce qu'on sait : c'est une des façons les plus efficaces d'apprendre. "
        "Les exercices et les quiz servent d'entraînement, pas seulement d'évaluation.",
        ["Choisis des exercices ou des cartes sur la leçon du jour.",
         "Réponds sans aide, comme en devoir.",
         "Corrige-toi avec la correction et note tes erreurs.",
         "Refais plus tard les exercices manqués jusqu'à les réussir seul."]),
    "retrieval_practice": (
        "Retrouver régulièrement une information dans sa mémoire, sous des formes variées (question, exercice, "
        "schéma à refaire), rend cette information plus facile à retrouver le jour du devoir.",
        ["Choisis une notion déjà étudiée.",
         "Retrouve-la sous une forme différente : réponds à une question, refais un schéma ou un exemple.",
         "Vérifie avec le document.",
         "Varie les formes d'une séance à l'autre."]),
    "free_recall": (
        "Tu restitues un contenu entier (une leçon, une démonstration, un texte) de mémoire et dans l'ordre que tu "
        "veux, sans aucune aide.",
        ["Choisis un contenu précis : une leçon ou une partie de leçon.",
         "Écris ou récite tout ce que tu en retiens, sans indice.",
         "Compare avec le document et repère les oublis.",
         "Recommence le lendemain."]),
    "cued_recall": (
        "Un indice (un mot-clé, le début d'une formule, un titre) aide à retrouver le reste. On s'entraîne avec "
        "des indices, puis on les enlève peu à peu.",
        ["Prépare des indices : titres, mots-clés, premiers mots.",
         "À partir de chaque indice, retrouve la suite de mémoire.",
         "Vérifie avec le document.",
         "Retire progressivement les indices jusqu'à ne plus en avoir besoin."]),
    "feynman": (
        "Si tu sais expliquer une notion simplement, comme à un camarade plus jeune, c'est que tu l'as comprise. Les "
        "endroits où tu bloques montrent ce qu'il faut revoir.",
        ["Écris le nom de la notion en haut d'une feuille.",
         "Explique-la avec des mots simples, comme à un plus jeune, avec un exemple du cours.",
         "Repère les passages où tu bloques ou utilises des mots que tu ne sais pas expliquer.",
         "Retourne au document pour ces passages, puis simplifie ton explication."]),
    "mind_mapping": (
        "Une carte mentale place le thème au centre et les idées autour, en branches. Elle montre d'un coup d'œil "
        "l'organisation d'une leçon.",
        ["Écris le titre de la leçon au centre d'une feuille.",
         "Trace une branche par grande partie, avec un mot-clé.",
         "Ajoute des sous-branches pour les détails : définitions, formules, exemples.",
         "Utilise des couleurs et des petits dessins, puis refais la carte de mémoire."]),
    "concept_mapping": (
        "Une carte conceptuelle relie des notions par des flèches qui disent comment elles sont liées (« est un », "
        "« entraîne », « se calcule avec »).",
        ["Liste les notions importantes de la leçon.",
         "Place-les sur la feuille et relie celles qui sont liées.",
         "Écris sur chaque flèche le lien entre les deux notions.",
         "Vérifie chaque lien avec le document."]),
    "elaboration": (
        "On retient mieux une notion quand on la relie à ce qu'on sait déjà en se demandant « pourquoi ? » et "
        "« comment ? ».",
        ["Pour chaque notion, demande-toi pourquoi elle est vraie et comment elle s'applique.",
         "Cherche dans le document la réponse à ces questions.",
         "Relie la notion à une autre leçon ou à un exemple déjà vu.",
         "Écris ces liens en une ou deux phrases."]),
    "self_explanation": (
        "En t'expliquant à toi-même chaque étape d'une correction ou d'un raisonnement, tu comprends pourquoi on "
        "fait ainsi, et tu peux le refaire seul.",
        ["Prends un exercice corrigé.",
         "Pour chaque étape, dis à voix haute ou écris pourquoi elle est faite.",
         "Note les étapes que tu n'arrives pas à justifier et cherche-les dans le cours.",
         "Refais l'exercice sans la correction."]),
    "interleaved_practice": (
        "Mélanger des exercices de types différents oblige à choisir la bonne méthode à chaque fois, comme en "
        "devoir, au lieu d'appliquer la même recette en série.",
        ["Choisis des exercices de deux ou trois chapitres différents de la même matière.",
         "Mélange-les avant de commencer.",
         "Pour chacun, dis d'abord quelle méthode ou quelle notion utiliser.",
         "Résous-le, puis vérifie avec la correction."]),
    "chunking": (
        "La mémoire retient plus facilement quelques groupes d'éléments qu'une longue liste. On découpe donc "
        "l'information en petits paquets qui ont un sens.",
        ["Repère une longue liste ou un long contenu à retenir.",
         "Regroupe les éléments en paquets de 3 à 5 qui vont ensemble.",
         "Donne un nom à chaque paquet.",
         "Apprends paquet par paquet, puis l'ensemble."]),
    "cornell": (
        "La feuille est partagée en trois zones : les notes, une colonne de mots-clés ou de questions, et un résumé "
        "en bas. Elle sert ensuite directement à réviser.",
        ["Trace une colonne étroite à gauche et une bande en bas de la feuille.",
         "Prends tes notes dans la grande zone de droite.",
         "Après le cours, écris dans la colonne de gauche les mots-clés ou les questions.",
         "Écris en bas un résumé de quelques lignes ; pour réviser, cache la droite et réponds aux questions de gauche."]),
    "dual_coding": (
        "Associer les mots à une image (schéma, tableau, figure, frise) donne deux chemins pour retrouver la même "
        "information.",
        ["Choisis une notion de la leçon.",
         "Associe-lui un schéma, une figure, un tableau ou une frise, en t'aidant du document.",
         "Explique le dessin avec tes mots.",
         "Pour réviser, refais le dessin de mémoire et commente-le."]),
    "teaching": (
        "Préparer une explication pour quelqu'un d'autre oblige à organiser ses idées ; les questions de l'autre "
        "montrent ce qui n'est pas clair.",
        ["Choisis une notion et prépare une courte explication avec un exemple du cours.",
         "Explique-la à un camarade, à un parent ou à voix haute.",
         "Note les questions qu'on te pose ou celles où tu hésites.",
         "Retravaille ces points dans le document."]),
    "loci": (
        "Tu associes chaque élément à retenir à un endroit d'un lieu que tu connais très bien (ta maison, le "
        "chemin de l'école). Pour retrouver la liste, tu refais le trajet dans ta tête.",
        ["Choisis un lieu familier et un trajet dans ce lieu avec des étapes précises.",
         "Place chaque élément à retenir à une étape, avec une image frappante.",
         "Parcours le trajet dans ta tête pour retrouver les éléments dans l'ordre.",
         "Refais le parcours plusieurs fois, puis le lendemain."]),
    "acronymes": (
        "Un acronyme forme un mot avec les premières lettres des éléments à retenir ; un acrostiche forme une phrase "
        "dont chaque mot commence par ces lettres.",
        ["Écris la liste des éléments à retenir, dans l'ordre.",
         "Prends la première lettre de chacun.",
         "Forme un mot ou une phrase facile à retenir avec ces lettres.",
         "Vérifie que tu retrouves chaque élément à partir de sa lettre."]),
    "associations": (
        "Relier une information nouvelle à une image ou à un mot qui te parle déjà crée un « crochet » pour la "
        "retrouver.",
        ["Choisis l'information difficile à retenir.",
         "Cherche une image ou un mot connu qui lui ressemble par le son, la forme ou le sens.",
         "Imagine une petite scène qui relie les deux.",
         "Rappelle-toi la scène pour retrouver l'information, puis vérifie avec le document."]),
    "imagerie": (
        "Se représenter mentalement une scène, une expérience ou une figure, avec des détails, aide à s'en souvenir.",
        ["Lis le passage à retenir.",
         "Ferme les yeux et imagine la scène, la figure ou l'expérience avec précision.",
         "Décris à voix haute ce que tu vois.",
         "Compare avec le document et corrige ton image."]),
    "chainage": (
        "Chaque élément d'une liste est relié au suivant par une petite histoire ; en retrouvant le premier, on "
        "tire toute la chaîne.",
        ["Écris les éléments à retenir dans l'ordre.",
         "Invente une histoire courte où chaque élément mène au suivant.",
         "Raconte l'histoire de mémoire et retrouve les éléments.",
         "Vérifie l'ordre avec le document."]),
    "analogie": (
        "Comparer une notion nouvelle à quelque chose de connu qui fonctionne de la même façon aide à la comprendre "
        "et à la retenir. Une analogie ne remplace pas la définition du cours.",
        ["Choisis une notion nouvelle.",
         "Cherche une situation connue qui fonctionne de la même façon.",
         "Note ce qui est pareil et ce qui est différent.",
         "Retiens l'analogie, puis récite la vraie définition du document."]),
    "pomodoro": (
        "On travaille par séances courtes et concentrées, séparées de pauses : 25 minutes de travail, 5 minutes de "
        "pause. Le cerveau reste attentif plus longtemps.",
        ["Choisis une seule tâche et range ce qui peut te distraire (téléphone, télévision).",
         "Travaille 25 minutes sans t'arrêter.",
         "Fais une pause de 5 minutes en te levant.",
         "Après quatre séances, prends une pause plus longue de 15 à 30 minutes."]),
    "planification": (
        "Prévoir à l'avance quoi réviser et quand évite de tout faire la veille et permet de revenir plusieurs fois "
        "sur chaque leçon.",
        ["Note les dates de tes devoirs et examens.",
         "Liste les leçons à réviser pour chacun.",
         "Répartis-les sur les jours disponibles, en prévoyant plusieurs passages par leçon.",
         "Coche ce qui est fait et ajuste le plan chaque semaine."]),
    "cumulative": (
        "À chaque séance, tu révises la nouvelle leçon et tu reprends rapidement les anciennes, pour ne rien laisser "
        "s'effacer.",
        ["Commence la séance par quelques questions sur les leçons précédentes.",
         "Travaille ensuite la nouvelle leçon.",
         "Termine par un mélange de questions anciennes et nouvelles.",
         "Note les anciennes notions oubliées pour la séance suivante."]),
    "alternance": (
        "Alterner les matières ou les unités pendant une séance évite la fatigue et aide à mieux distinguer les "
        "notions.",
        ["Prévois deux ou trois matières pour ta séance.",
         "Travaille chacune pendant un temps limité (par exemple 25 à 40 minutes).",
         "Change de matière à la fin de chaque bloc.",
         "Varie l'ordre d'une séance à l'autre."]),
    "concentration": (
        "Une séance de concentration est un moment protégé, sans distraction, avec un objectif précis et une durée "
        "fixée.",
        ["Fixe un objectif précis et réaliste pour la séance.",
         "Choisis un endroit calme et éloigne téléphone et écrans.",
         "Prépare tout le matériel avant de commencer.",
         "À la fin, vérifie si l'objectif est atteint et note ce qui reste à faire."]),
    "progressives": (
        "On avance du plus simple au plus difficile : d'abord comprendre et retenir l'essentiel, puis s'entraîner "
        "sur des exercices de plus en plus complets.",
        ["Commence par l'essentiel : définitions, propriétés, formules.",
         "Fais ensuite des exercices d'application directe.",
         "Passe à des exercices plus longs qui mélangent plusieurs notions.",
         "Termine par un sujet complet dans les conditions d'un devoir."]),
}

# Quel support des documents sert d'exemple : une carte mémoire (rappel, mnémotechnie) ou un exercice corrigé.
EXAMPLE_KIND = {code: "flashcard" for code in (
    "active_recall", "spaced_repetition", "blurting", "free_recall", "cued_recall", "loci", "acronymes",
    "associations", "imagerie", "chainage", "analogie", "feynman", "teaching", "elaboration", "dual_coding",
    "mind_mapping", "concept_mapping", "chunking", "cornell")}
EXAMPLE_NOTE = {
    "active_recall": "Lis la question de cette carte, cache la réponse et récite-la de mémoire avant de la retourner.",
    "spaced_repetition": "Note cette carte selon ta réponse : elle reviendra plus tôt si tu l'as manquée, plus tard si tu l'as sue.",
    "blurting": "Écris sur une feuille blanche tout ce que tu sais sur la notion de cette carte, puis compare avec la réponse.",
    "practice_testing": "Fais cet exercice sans aide, comme en devoir, puis corrige-toi avec la correction.",
    "retrieval_practice": "Refais cet exercice quelques jours plus tard sans regarder ta première copie.",
    "free_recall": "Récite toute la réponse de cette carte de mémoire, puis vérifie mot à mot.",
    "cued_recall": "Lis seulement les premiers mots de la réponse et retrouve la suite de mémoire.",
    "feynman": "Explique la notion de cette carte avec des mots simples, comme à un plus jeune.",
    "mind_mapping": "Place la notion de cette carte dans une carte mentale de son chapitre.",
    "concept_mapping": "Relie la notion de cette carte aux autres notions de son chapitre par des flèches légendées.",
    "elaboration": "Demande-toi pourquoi ce qui est écrit sur cette carte est vrai et dans quel exercice on l'utilise.",
    "self_explanation": "Pour chaque étape de la correction de cet exercice, explique pourquoi elle est faite.",
    "interleaved_practice": "Mélange cet exercice avec des exercices d'autres chapitres et dis d'abord quelle méthode il demande.",
    "chunking": "Découpe la réponse de cette carte en 2 ou 3 morceaux et apprends-les un par un.",
    "cornell": "Recopie la question de cette carte dans la colonne de gauche et la réponse à droite.",
    "dual_coding": "Associe à la réponse de cette carte un schéma, une figure ou un tableau.",
    "teaching": "Explique la notion de cette carte à quelqu'un, puis réponds à ses questions avec le document.",
    "loci": "Place les éléments de la réponse de cette carte le long d'un trajet que tu connais.",
    "acronymes": "Forme un mot avec les premières lettres des éléments de la réponse de cette carte.",
    "associations": "Associe la notion de cette carte à une image qui te parle.",
    "imagerie": "Imagine la situation décrite par cette carte, puis décris-la sans regarder.",
    "chainage": "Relie les éléments de la réponse de cette carte par une petite histoire.",
    "analogie": "Compare la notion de cette carte à une situation que tu connais, puis récite la réponse exacte.",
    "pomodoro": "Fais cet exercice pendant une séance de 25 minutes, sans interruption.",
    "planification": "Inscris cet exercice dans ton plan de révision de la semaine.",
    "cumulative": "Refais cet exercice au début d'une séance consacrée à un chapitre plus récent.",
    "alternance": "Fais cet exercice entre deux blocs consacrés à d'autres matières.",
    "concentration": "Fixe-toi un objectif : réussir cet exercice seul en une séance sans écran.",
    "progressives": "Commence par cet exercice d'application, puis passe à un sujet plus complet du même chapitre.",
}
DELEGATION = "Délégation du propriétaire du 2026-11-20 : méthodes rédigées et approuvées pour lui."


def write_and_approve(db: Session, admin_id: int) -> int:
    """Remplit le principe et les étapes laissés vides, puis approuve. Ne réécrit jamais un texte déjà saisi."""
    from datetime import UTC, datetime

    from app.audit import record

    ensure_catalog(db)
    approved = 0
    for method in db.scalars(select(MemoryMethod)):
        principle, steps = GUIDE[method.code] if method.code in GUIDE else (None, [])
        if not (method.principle or "").strip() and principle:
            method.principle = principle
        if not method.steps and steps:
            method.steps = steps
        if method.status != "validated" and (method.principle or "").strip() and method.steps:
            method.status, method.validated_at, method.validated_by = "validated", datetime.now(UTC), admin_id
            record(db, admin_id, "validate", "memory_method", method.id, note=DELEGATION)
            approved += 1
    db.commit()
    return approved
