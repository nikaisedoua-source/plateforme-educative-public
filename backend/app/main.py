from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import admin, auth, catalog, library, mathtext


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title=settings.app_name, version="0.1.0")
    if settings.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type"],
        )
    application.include_router(auth.router, prefix="/api/v1")
    application.include_router(catalog.router, prefix="/api/v1")
    application.include_router(admin.router, prefix="/api/v1")
    application.include_router(library.router, prefix="/api/v1")
    application.include_router(mathtext.router, prefix="/api/v1")

    @application.get("/health", tags=["santé"])
    def health():
        return {"status": "ok"}

    return application


app = create_app()
