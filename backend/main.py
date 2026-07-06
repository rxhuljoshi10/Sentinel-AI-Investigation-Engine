from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routers import chat, investigate, incidents, investigation, evaluation
from backend.core.config import settings
from backend.core.database import init_db

app = FastAPI(
    title=settings.app_name,
    description="Autonomous Incident Investigation Platform",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    await init_db()
    print("Database initialized")

app.include_router(chat.router)
app.include_router(investigate.router)
app.include_router(incidents.router)
app.include_router(investigation.router)
app.include_router(evaluation.router)

@app.get("/health")
async def health():
    return {"status": "ok", "model": settings.ollama_model}