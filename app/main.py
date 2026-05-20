"""Entry point FastAPI: monta API + sirve widget estático."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.logging import setup_logging

setup_logging()

app = FastAPI(
    title="scholarly-profile-auditor",
    version="0.3.0",
    description="Auditoría bibliográfica reproducible con identidad autoral verificada.",
)

# CORS — permitir embedding del widget desde cualquier dominio en modo local.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

# Servir widget como estático en /widget/
widget_dir = Path(__file__).resolve().parents[1] / "widget"
if widget_dir.is_dir():
    app.mount("/widget", StaticFiles(directory=str(widget_dir), html=True), name="widget")


@app.get("/")
async def root() -> dict:
    return {
        "service": "scholarly-profile-auditor",
        "widget_url": "/widget/index.html",
        "api_health": "/api/health",
    }
