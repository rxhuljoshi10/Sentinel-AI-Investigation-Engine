from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"
    app_name: str = "Sentinel AI"
    debug: bool = True

    class Config:
        env_file = ".env"

settings = Settings()