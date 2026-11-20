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
    args = parser.parse_args()
    if args.command == "create-admin":
        create_admin(args.email)
    elif args.command == "set-password":
        set_password(args.email)
    elif args.command == "import-folder":
        import_folder_command(args)


if __name__ == "__main__":
    main()
