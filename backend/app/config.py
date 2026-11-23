from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str

    # API Keys
    GROQ_API_KEY: str
    GROQ_MODEL: str = "qwen/qwen3.8-27b"
    SERPAPI_API_KEY: str
    GITHUB_TOKEN: Optional[str] = None   # Optional — unlocks 5000 req/hr vs 60

    # JWT Auth
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # App
    DEBUG: bool = True

    # CORS — comma-separated list of allowed origins
    # Default covers local Vite dev + deployed Vercel app.
    # On Render/Railway set this env var to include your exact Vercel URL(s).
    ALLOWED_ORIGINS: str = (
        "http://localhost:5173,"
        "http://127.0.0.1:5173,"
        "http://localhost:5174,"
        "http://127.0.0.1:5174,"
        "https://neural-archaeologist.vercel.app"
    )

    # v2 Settings
    CONFIDENCE_THRESHOLD: int = 70          # Minimum confidence to skip web search
    SEMGREP_ENABLED: bool = False           # Enable Semgrep for static analysis (requires semgrep CLI)
    MAX_AST_FILES: int = 800                # Cap file count for AST scanning
    MAX_AST_FILE_SIZE_KB: int = 200         # Skip files larger than this (KB)
    DEFAULT_PERSONA: str = "SOLO_DEV"       # Fallback persona if routing fails

    class Config:
        env_file = ".env"


settings = Settings()