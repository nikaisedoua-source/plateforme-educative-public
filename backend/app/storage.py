"""Stockage local des documents : clés relatives au dossier configuré (DOCUMENT_STORAGE_PATH)."""

import hashlib
import re
import shutil
import unicodedata
from pathlib import Path
from typing import BinaryIO

from app.config import get_settings

BACKEND_DIR = Path(__file__).resolve().parents[1]

ALLOWED_EXTENSIONS = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".txt": "text/plain",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}
IMAGE_TYPES = {"image/png", "image/jpeg"}


def storage_root() -> Path:
    root = Path(get_settings().document_storage_path)
    if not root.is_absolute():
        root = BACKEND_DIR / root
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def resolve(key: str) -> Path:
    """Chemin absolu d'une clé ; refuse toute sortie du dossier de stockage."""
    root = storage_root()
    path = (root / key).resolve()
    if root not in path.parents:
        raise ValueError("Clé de stockage invalide")
    return path


def safe_name(filename: str) -> str:
    normalized = unicodedata.normalize("NFKD", filename).encode("ascii", "ignore").decode()
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", normalized).strip("._")
    return cleaned[:120] or "document"


def mime_for(filename: str) -> str | None:
    return ALLOWED_EXTENSIONS.get(Path(filename).suffix.lower())


def save_stream(source: BinaryIO, folder: str, filename: str, max_bytes: int) -> tuple[str, int, str]:
    """Copie le flux par blocs dans un fichier temporaire, calcule l'empreinte SHA-256,
    puis le range sous `folder/<sha>_<nom>`. Retourne (clé, taille, sha256)."""
    root = storage_root()
    tmp_dir = root / "tmp"
    tmp_dir.mkdir(exist_ok=True)
    digest = hashlib.sha256()
    size = 0
    tmp_path = tmp_dir / f"upload_{id(source)}_{safe_name(filename)}"
    try:
        with tmp_path.open("wb") as out:
            while chunk := source.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise OverflowError
                digest.update(chunk)
                out.write(chunk)
        sha = digest.hexdigest()
        key = f"{folder}/{sha[:16]}_{safe_name(filename)}"
        final = resolve(key)
        final.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(tmp_path), final)
        return key, size, sha
    finally:
        tmp_path.unlink(missing_ok=True)


def cache_path(*parts: str) -> Path:
    path = resolve("/".join(("cache", *parts)))
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
