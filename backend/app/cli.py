import argparse
from getpass import getpass

from pydantic import EmailStr, TypeAdapter
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.database import get_engine
from app.models import User
from app.security import hash_password


def create_admin(email_input: str) -> None:
    email = str(TypeAdapter(EmailStr).validate_python(email_input)).lower()
    factory = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    with factory() as db:
        if db.scalar(select(func.count()).select_from(User).where(User.role == "admin")):
            raise SystemExit("Un administrateur existe déjà : création bootstrap refusée.")
        if db.scalar(select(User.id).where(User.email == email)) is not None:
            raise SystemExit("Cette adresse e-mail est déjà utilisée.")
        password = getpass("Mot de passe admin (12 caractères minimum) : ")
        confirmation = getpass("Confirmez le mot de passe : ")
        if len(password) < 12 or password != confirmation:
            raise SystemExit("Mot de passe trop court ou confirmation différente.")
        db.add(User(email=email, password_hash=hash_password(password), role="admin", is_active=True))
        db.commit()
    print(f"Administrateur créé : {email}")


def set_password(email_input: str) -> None:
    email = email_input.strip().lower()
    factory = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    with factory() as db:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            raise SystemExit("Aucun compte avec cette adresse e-mail.")
        password = getpass("Nouveau mot de passe (12 caractères minimum) : ")
        confirmation = getpass("Confirmez le mot de passe : ")
        if len(password) < 12 or password != confirmation:
            raise SystemExit("Mot de passe trop court ou confirmation différente.")
        user.password_hash = hash_password(password)
        db.commit()
    print(f"Mot de passe modifié pour : {email}")


def import_folder_command(args: argparse.Namespace) -> None:
    import csv
    from datetime import datetime
    from pathlib import Path

    from app.importer import import_folder
    from app.storage import storage_root

    root = Path(args.folder)
    if not root.is_dir():
        raise SystemExit(f"Dossier introuvable : {root}")
    factory = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    report = import_folder(
        factory, root, create_referentials=args.create_referentials, extract=args.extract,
        segment=args.segment, dry_run=args.dry_run,
    )
    target = storage_root() / "rapports" / f"import_{datetime.now():%Y%m%d_%H%M%S}.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    columns = ["file", "id", "title", "subject", "grade", "kind", "source", "status", "pages", "exercises",
               "corrections", "segment_error"]
    with target.open("w", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, fieldnames=columns + ["skipped"], extrasaction="ignore")
        writer.writeheader()
        writer.writerows(report.imported)
        writer.writerows({"file": name, "skipped": reason} for name, reason in report.skipped)
    print(f"{len(report.imported)} importé(s), {len(report.skipped)} ignoré(s). Rapport : {target}")


def reprocess_command(args: argparse.Namespace) -> None:
    import csv
    from datetime import datetime

    from app.reprocess import reprocess
    from app.storage import storage_root

    factory = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    report = reprocess(factory, document_ids=args.ids or None, pair=not args.no_pairing)
    folder = storage_root() / "rapports"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = f"{datetime.now():%Y%m%d_%H%M%S}"
    columns = ["id", "title", "file", "status", "pages", "reextract", "grade", "series", "kind", "exercises",
               "corrections", "error"]
    with (folder / f"retraitement_{stamp}.csv").open("w", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(report.rows)
    with (folder / f"appariement_corriges_{stamp}.csv").open("w", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, fieldnames=["corrige_id", "corrige", "exercise_id", "exercises", "common_words",
                                                 "matching_numbers", "linked", "result"], extrasaction="ignore")
        writer.writeheader()
        writer.writerows(report.pairs)
    total = sum(row.get("exercises") or 0 for row in report.rows)
    print(f"{len(report.rows)} document(s) retraité(s), {total} exercice(s). Rapports : {folder}/*_{stamp}.csv")


def publish_command() -> None:
    """Publie tout le contenu extrait pour chaque classe (niveau et séries du document)."""
    from app.flashcards import create_proposals
    from app.models import Document
    from app.publication import publish_all
    from app.reprocess import infer_series

    factory = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    with factory() as db:
        cards = 0
        for document in db.scalars(select(Document).where(Document.status == "extracted")):
            series = infer_series(db, document)
            if series:
                print(f"[{document.id}] {document.title} : séries {', '.join(series)}")
            cards += create_proposals(db, document)[1]
            db.commit()
        print(f"{cards} carte(s) mémoire ajoutée(s) depuis les documents.")
        total = publish_all(db)
    for key, value in sorted(total.items()):
        print(f"{key} : {value}")


def verify_command(args: argparse.Namespace) -> None:
    """Vérifie chaque exercice publié et l'exploitation de chaque document ; rapports CSV."""
    import csv
    from datetime import datetime

    from app.storage import storage_root
    from app.verification import verify

    factory = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    with factory() as db:
        report = verify(db, apply=not args.simuler)
    folder = storage_root() / "rapports"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = f"{datetime.now():%Y%m%d_%H%M%S}"
    for name, rows in (("verification_exercices", report.exercises), ("verification_documents", report.documents)):
        with (folder / f"{name}_{stamp}.csv").open("w", newline="", encoding="utf-8") as out:
            if rows:
                writer = csv.DictWriter(out, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
    print(f"Rapports : {folder}/verification_*_{stamp}.csv")


def rewrite_command(args: argparse.Namespace) -> None:
    """Réécrit les énoncés (et les corrigés) en LaTeX avec le modèle local, matières à formules d'abord."""
    import time

    from sqlalchemy import case

    from app import storage
    from app.models import Exercise, Subject
    from app.rewrite import RewriteUnavailable, _PageCache, rewrite_correction, rewrite_exercise

    factory = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    priority = case((Subject.name == "Mathématiques", 0), (Subject.name == "Physique-Chimie", 1),
                    (Subject.name == "SVT", 2), else_=3)
    with factory() as db:
        query = select(Exercise.id).outerjoin(Subject, Subject.id == Exercise.subject_id).where(
            Exercise.is_archived.is_(False))
        if args.ids:
            query = query.where(Exercise.id.in_(args.ids))
        if args.documents:
            query = query.where(Exercise.document_id.in_(args.documents))
        if args.matieres:
            query = query.where(Subject.name.in_(args.matieres))
        if args.corrige_seulement:
            query = query.where(Exercise.rewrite_status.in_(("ok", "doubtful")), Exercise.correction.has())
        elif not args.refaire:
            query = query.where(Exercise.rewrite_status == "none")
        ids = list(db.scalars(query.order_by(Exercise.is_published.desc(), priority, Exercise.document_id,
                                             Exercise.sort_order, Exercise.id).limit(args.limite)))
    print(f"{len(ids)} exercice(s) à réécrire.", flush=True)
    caches: dict[int, _PageCache] = {}
    counts: dict[str, int] = {}
    for number, exercise_id in enumerate(ids, start=1):
        started = time.monotonic()
        with factory() as db:
            exercise = db.get(Exercise, exercise_id)
            if exercise is None:  # supprimé entre-temps (document retraité) : on passe
                print(f"[{number}/{len(ids)}] exercice {exercise_id} : disparu (document retraité)", flush=True)
                continue
            cache = caches.setdefault(exercise.document_id, _PageCache(storage.resolve(exercise.document.storage_key)))
            try:
                status = exercise.rewrite_status if args.corrige_seulement else rewrite_exercise(db, exercise, cache)
                corrected = "—"
                if not args.sans_corrige and status != "failed" and exercise.correction is not None:
                    corrected = rewrite_correction(db, exercise)
                db.commit()
            except RewriteUnavailable as error:
                print(error, flush=True)
                return
            except Exception as error:  # un exercice illisible n'arrête pas la série
                db.rollback()
                exercise = db.get(Exercise, exercise_id)
                if exercise is None:
                    print(f"[{number}/{len(ids)}] exercice {exercise_id} : disparu (document retraité)", flush=True)
                    continue
                exercise.rewrite_status = "failed"
                db.commit()
                status, corrected = "failed", f"erreur : {str(error)[:80]}"
            counts[status] = counts.get(status, 0) + 1
            print(f"[{number}/{len(ids)}] exercice {exercise_id} : {status} ({len(exercise.questions)} question(s), "
                  f"corrigé {corrected}) en {time.monotonic() - started:.0f} s", flush=True)
    print("Bilan :", ", ".join(f"{key} {value}" for key, value in sorted(counts.items())) or "rien à faire")


def approve_methods_command() -> None:
    """Rédige (si vide) et approuve les méthodes du laboratoire de mémorisation (délégation du propriétaire)."""
    from app.methods_catalog import write_and_approve

    factory = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    with factory() as db:
        admin = db.scalar(select(User.id).where(User.role == "admin").order_by(User.id))
        if admin is None:
            raise SystemExit("Aucun administrateur : lancez d'abord create-admin.")
        print(f"{write_and_approve(db, admin)} méthode(s) approuvée(s).")


def precise_cards_command(args: argparse.Namespace) -> None:
    """Nomme la notion des cartes à la question imprécise (modèle local, mots vérifiés dans le document)."""
    from app.flashcard_questions import precise_all
    from app.rewrite import RewriteUnavailable

    factory = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    with factory() as db:
        try:
            totals = precise_all(db, args.ids or None, log=lambda line: print(line, flush=True))
        except RewriteUnavailable as error:
            raise SystemExit(str(error)) from None
    print("Bilan :", ", ".join(f"{key} {value}" for key, value in sorted(totals.items())) or "rien à faire")


def preview_command(args: argparse.Namespace) -> None:
    """Rend des pages avec une règle et liste les exercices découpés sur ces pages (pour la sélection)."""
    from pathlib import Path

    from app.models import Document, Exercise
    from app.selection import decisions, preview_page

    factory = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with factory() as db:
        document = db.get(Document, args.document)
        for page in args.pages:
            (out / f"d{document.id}-p{page}.png").write_bytes(preview_page(document, page))
            rows = db.scalars(select(Exercise).where(Exercise.document_id == document.id,
                                                     Exercise.page_start <= page, Exercise.page_end >= page)
                              .order_by(Exercise.page_start, Exercise.sort_order, Exercise.id)).all()
            done = decisions(db, [e.id for e in rows])
            print(f"--- document {document.id} « {document.title} », page {page}")
            for e in rows:
                first = (e.original_text or e.statement).strip().splitlines()[0][:70] if (e.original_text or e.statement).strip() else ""
                verdict = done[e.id].details.get("verdict") if e.id in done else "-"
                print(f"  {e.id} p{e.page_start}-{e.page_end} [{verdict}] {e.title[:50]} | {first}")


def select_command(args: argparse.Namespace) -> None:
    """Applique les décisions de sélection d'un fichier JSON (exercice retenu ou écarté, raison, zone)."""
    from app.selection import apply_file, unpublish_unselected

    factory = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    with factory() as db:
        if args.retirer_non_selectionnes:
            print(f"{unpublish_unselected(db)} exercice(s) non sélectionné(s) retiré(s) de la publication.")
            db.commit()
        for path in args.fichiers:
            totals = apply_file(db, path)
            print("Bilan :", ", ".join(f"{k} {v}" for k, v in sorted(totals.items())) or "rien")


def main() -> None:
    parser = argparse.ArgumentParser(description="Commandes d’administration locale de l’API")
    commands = parser.add_subparsers(dest="command", required=True)
    admin = commands.add_parser("create-admin", help="Créer le premier compte administrateur")
    admin.add_argument("--email", required=True)
    reset = commands.add_parser("set-password", help="Changer le mot de passe d’un compte (saisie masquée)")
    reset.add_argument("--email", required=True)
    folder = commands.add_parser("import-folder", help="Importer un dossier rangé Matière/Niveau/fichier")
    folder.add_argument("folder")
    folder.add_argument("--create-referentials", action="store_true",
                        help="Créer les matières et niveaux absents (d'après les noms de dossiers)")
    folder.add_argument("--extract", action="store_true", help="Extraire le texte (OCR si besoin)")
    folder.add_argument("--segment", action="store_true", help="Extraire puis découper en exercices")
    folder.add_argument("--dry-run", action="store_true", help="Simuler sans rien écrire")
    again = commands.add_parser("retraiter", help="Retraiter toute la bibliothèque jusqu'à la dernière page")
    again.add_argument("ids", nargs="*", type=int, help="Numéros de documents (par défaut : tous)")
    again.add_argument("--no-pairing", action="store_true", help="Ne pas associer les livres de corrigés")
    commands.add_parser("publier-tout", help="Publier tout le contenu extrait pour chaque classe et série")
    check = commands.add_parser("verifier", help="Vérifier chaque exercice publié et chaque document")
    check.add_argument("--simuler", action="store_true", help="Rapport seulement, sans rien retirer")
    cards = commands.add_parser("preciser-cartes", help="Nommer la notion des cartes à la question imprécise")
    cards.add_argument("ids", nargs="*", type=int, help="Numéros de cartes (par défaut : toutes)")
    commands.add_parser("approuver-methodes", help="Rédiger et approuver les méthodes de mémorisation")
    write = commands.add_parser("rediger", help="Réécrire les énoncés en LaTeX avec le modèle local (Ollama)")
    write.add_argument("ids", nargs="*", type=int, help="Numéros d'exercices (par défaut : tous)")
    write.add_argument("--documents", nargs="*", type=int, help="Seulement ces documents")
    write.add_argument("--matieres", nargs="*", help="Seulement ces matières (ex. Mathématiques)")
    write.add_argument("--limite", type=int, default=None, help="Nombre maximal d'exercices")
    write.add_argument("--refaire", action="store_true", help="Refaire aussi les exercices déjà réécrits")
    write.add_argument("--sans-corrige", action="store_true", help="Ne pas réécrire les corrigés")
    write.add_argument("--corrige-seulement", action="store_true",
                       help="Relire seulement les corrigés des exercices déjà réécrits (résultats attendus)")
    look = commands.add_parser("apercu", help="Pages rendues avec une règle et exercices découpés (sélection)")
    look.add_argument("document", type=int)
    look.add_argument("pages", nargs="+", type=int)
    look.add_argument("--out", required=True)
    choose = commands.add_parser("selectionner", help="Appliquer des décisions de sélection (fichiers JSON)")
    choose.add_argument("fichiers", nargs="*")
    choose.add_argument("--retirer-non-selectionnes", action="store_true",
                        help="Retirer de la publication tout exercice qui n'a pas été retenu")
    args = parser.parse_args()
    if args.command == "create-admin":
        create_admin(args.email)
    elif args.command == "set-password":
        set_password(args.email)
    elif args.command == "import-folder":
        import_folder_command(args)
    elif args.command == "retraiter":
        reprocess_command(args)
    elif args.command == "publier-tout":
        publish_command()
    elif args.command == "verifier":
        verify_command(args)
    elif args.command == "preciser-cartes":
        precise_cards_command(args)
    elif args.command == "approuver-methodes":
        approve_methods_command()
    elif args.command == "apercu":
        preview_command(args)
    elif args.command == "selectionner":
        select_command(args)
    elif args.command == "rediger":
        rewrite_command(args)


if __name__ == "__main__":
    main()
