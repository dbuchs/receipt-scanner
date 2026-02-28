from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.routers import analytics, ingestion, receipts, rules, ynab


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables if not using alembic in dev
    settings = get_settings()
    if settings.DEBUG:
        from app.database import Base, engine
        import app.models  # noqa: F401 – ensure all models are registered

        Base.metadata.create_all(bind=engine)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        debug=settings.DEBUG,
        lifespan=lifespan,
    )

    # Routers
    app.include_router(ingestion.router)
    app.include_router(receipts.router)
    app.include_router(ynab.router)
    app.include_router(rules.router)
    app.include_router(analytics.router)

    # Templates (HTML UI)
    templates = Jinja2Templates(directory="app/templates")

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def index(request: Request):
        return templates.TemplateResponse("receipts_list.html", {"request": request})

    @app.get("/ui/inbox", response_class=HTMLResponse, include_in_schema=False)
    async def ui_inbox(request: Request):
        return templates.TemplateResponse("inbox.html", {"request": request})

    @app.get("/ui/receipts/{receipt_id}", response_class=HTMLResponse, include_in_schema=False)
    async def ui_receipt_detail(request: Request, receipt_id: str):
        return templates.TemplateResponse(
            "receipt_detail.html", {"request": request, "receipt_id": receipt_id}
        )

    @app.get("/ui/rules", response_class=HTMLResponse, include_in_schema=False)
    async def ui_rules(request: Request):
        return templates.TemplateResponse("rules.html", {"request": request})

    @app.get("/ui/analytics", response_class=HTMLResponse, include_in_schema=False)
    async def ui_analytics(request: Request):
        return templates.TemplateResponse("analytics.html", {"request": request})

    @app.get("/ui/ynab/match/{receipt_id}", response_class=HTMLResponse, include_in_schema=False)
    async def ui_ynab_match(request: Request, receipt_id: str):
        return templates.TemplateResponse(
            "ynab_match.html", {"request": request, "receipt_id": receipt_id}
        )

    @app.get(
        "/ui/ynab/split/{receipt_id}/confirm",
        response_class=HTMLResponse,
        include_in_schema=False,
    )
    async def ui_confirm_split(request: Request, receipt_id: str):
        return templates.TemplateResponse(
            "confirm_split.html", {"request": request, "receipt_id": receipt_id}
        )

    return app


app = create_app()
