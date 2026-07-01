from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.core.config import settings
from backend.routers import chat, investigate

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

app.include_router(chat.router)
app.include_router(investigate.router) 

@app.get("/health")
async def health():
    return {"status": "ok", "model": settings.ollama_model}