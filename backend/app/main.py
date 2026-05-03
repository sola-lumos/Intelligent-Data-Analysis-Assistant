import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes_chat import router as chat_router
from app.api.routes_chat_stream import router as chat_stream_router
from app.api.routes_health import router as health_router
from app.api.routes_sessions import router as sessions_router
from app.core.config import settings


def configure_logging() -> None:
    level = logging.DEBUG if settings.app_env == "dev" else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


@asynccontextmanager
async def lifespan(application: FastAPI):
    """启动时初始化会话库表与 ChatService。"""
    from app.db import bootstrap
    from app.services.chat_service import ChatService

    bootstrap.init_db()
    application.state.chat_service = ChatService()
    yield


def create_app() -> FastAPI:
    application = FastAPI(
        title="Data Analytics API",
        version="0.1.0",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(health_router, prefix="/api")
    application.include_router(sessions_router, prefix="/api")
    application.include_router(chat_router, prefix="/api")
    application.include_router(chat_stream_router, prefix="/api")

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": exc.errors()})

    return application


configure_logging()

app = create_app()
