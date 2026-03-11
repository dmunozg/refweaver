"""FastAPI application entrypoint."""

import uvicorn
from fastapi import FastAPI

from refweaver.api.middleware import RequestSizeLimitMiddleware
from refweaver.api.routes.analyze import router as analyze_router
from refweaver.api.routes.enrich import router as enrich_router
from refweaver.api.routes.health import router as health_router
from refweaver.api.routes.jobs import router as jobs_router
from refweaver.api.routes.report import router as report_router
from refweaver.api.routes.runs import router as runs_router
from refweaver.api.routes.search import router as search_router
from refweaver.api.settings import SETTINGS
from refweaver.db.session import get_engine
from refweaver.http_identity import validate_http_identity_config


def create_app() -> FastAPI:
    """Create the FastAPI application."""
    app = FastAPI(title=SETTINGS.api_title, version=SETTINGS.api_version)

    @app.on_event("startup")
    def _startup() -> None:
        validate_http_identity_config()
        app.state.engine = get_engine(SETTINGS.database_url)

    @app.on_event("shutdown")
    def _shutdown() -> None:
        engine = getattr(app.state, "engine", None)
        if engine is not None:
            engine.dispose()

    app.add_middleware(RequestSizeLimitMiddleware)
    app.include_router(health_router)
    app.include_router(analyze_router)
    app.include_router(enrich_router)
    app.include_router(jobs_router)
    app.include_router(search_router)
    app.include_router(report_router)
    app.include_router(runs_router)
    return app


app = create_app()


def main(host: str = "0.0.0.0", port: int = 8000, reload: bool = False) -> None:
    """Run the FastAPI app with Uvicorn.

    This is the console-script entrypoint referenced in `pyproject.toml`.
    """
    uvicorn.run(app, host=host, port=port, reload=reload)


if __name__ == "__main__":
    main()
