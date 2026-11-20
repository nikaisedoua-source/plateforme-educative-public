"""Envoi des images d'exercice (figure recadrée ou capture de page), partagé admin / élève."""

from fastapi import HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app import extraction, storage
from app.models import Document, ExerciseAsset


def asset_response(db: Session, asset: ExerciseAsset) -> FileResponse:
    if asset.kind == "image" and asset.storage_key:
        return FileResponse(storage.resolve(asset.storage_key), media_type="image/png")
    document = db.get(Document, asset.exercise.document_id)
    cached = storage.cache_path("pages", str(document.id), f"{asset.page_number}.png")
    if not cached.exists():
        try:
            png = extraction.render_page(storage.resolve(document.storage_key), document.mime_type, asset.page_number)
        except extraction.ExtractionError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None
        cached.write_bytes(png)
    return FileResponse(cached, media_type="image/png")
