from fastapi import FastAPI

from api.routes import router as packets_router
from config.settings import Settings


def create_app() -> FastAPI:
    settings = Settings()
    app = FastAPI(title=settings.app_name)
    app.include_router(packets_router)
    return app


app = create_app()
