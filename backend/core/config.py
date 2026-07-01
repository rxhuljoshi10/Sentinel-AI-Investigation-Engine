from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"
    ollama_embed_model: str = "nomic-embed-text"
    app_name: str = "Sentinel AI"
    debug: bool = True
    chroma_path: str = "./data/chroma"

    class Config:
        env_file = ".env"

settings = Settings()