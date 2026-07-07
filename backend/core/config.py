from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"
    ollama_embed_model: str = "nomic-embed-text"
    app_name: str = "Sentinel AI"
    debug: bool = True
    chroma_path: str = "./data/chroma"
    database_url: str = ""
    github_token: str = ""
    github_repo: str = ""
    redis_url: str = "redis://localhost:6379"

    jwt_secret: str = "change-this-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24 hours

    class Config:
        env_file = ".env"

settings = Settings()