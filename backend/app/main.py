from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.api.voice_routes import router as voice_router
from app.core.config import settings

from app.api.fan_routes import router as fan_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    print(f"Starting {settings.APP_NAME}...")
    yield
    print(f"Stopping {settings.APP_NAME}...")


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

