import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.api.voice_routes import router as voice_router
from app.api.voice_response_routes import router as voice_response_router
from app.core.config import settings
from app.services.voice_service import (
    VoiceServiceUnavailableError,
    voice_service,
)

from app.api.fan_routes import router as fan_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Starting %s", settings.APP_NAME)
    if settings.VOICE_AUTO_START and settings.VOICE_ENABLED:
        try:
            await asyncio.to_thread(voice_service.start)
        except VoiceServiceUnavailableError:
            logger.exception("Voice listener auto-start failed")
    elif settings.VOICE_AUTO_START:
        logger.warning("VOICE_AUTO_START is true but VOICE_ENABLED is false")

    try:
        yield
    finally:
        try:
            await asyncio.to_thread(voice_service.stop)
        except VoiceServiceUnavailableError:
            logger.exception("Voice listener did not stop cleanly")
        logger.info("Stopping %s", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered English voice-controlled smart home",
    lifespan=lifespan,
)
app.include_router(fan_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    return {"message": "Welcome to VietHome AI", "version": settings.APP_VERSION}


@app.get("/health", tags=["system"])
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": settings.APP_NAME}


app.include_router(router)
app.include_router(voice_router)
app.include_router(voice_response_router)

