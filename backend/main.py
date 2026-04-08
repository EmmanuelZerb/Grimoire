"""Grimoire — FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router as api_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("grimoire")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Grimoire starting up...")
    yield
    logger.info("Grimoire shutting down...")


load_dotenv(Path(__file__).resolve().parent.parent / ".env")

app = FastAPI(
    title="Grimoire",
    description="AI Codebase Intelligence System — analyse, documente, et comprends n'importe quel repo.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.get("/health")
async def health_check():
    return {"status": "alive", "service": "grimoire", "version": "0.1.0"}
