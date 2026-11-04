import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
BASE_DIR = Path(__file__).resolve().parent.parent.parent
env_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=env_path)

# Disable Ultralytics autoinstall
os.environ["YOLO_AUTOINSTALL"] = "False"



class Settings:
    BASE_DIR: Path = BASE_DIR
    PROJECT_NAME: str = "AI Civic Guardian"
    PROJECT_DESCRIPTION: str = (

        "AI-Powered Multilingual Smart Civic Complaint Detection, "
        "Automatic Department Routing and Secure Complaint Management System"
    )

    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: str = os.getenv("DB_PORT", "5432")
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    DB_NAME: str = os.getenv("DB_NAME", "ai_civic_guardian")

    # Authentication & Security
    JWT_SECRET_KEY: str = os.getenv(
        "JWT_SECRET_KEY", "default_insecure_key_override_in_env_file_minimum_32_bytes"
    )
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

    # Service ports
    FLASK_PORT: int = int(os.getenv("FLASK_PORT", "5000"))
    FASTAPI_PORT: int = int(os.getenv("FASTAPI_PORT", "8000"))

    # Blockchain (Decoupled External Network; Database SHA-256 Audit Trail Preserved)
    BLOCKCHAIN_ENABLED: bool = os.getenv("BLOCKCHAIN_ENABLED", "false").lower() in ("true", "1", "yes")
    BLOCKCHAIN_RPC_URL: str = os.getenv("BLOCKCHAIN_RPC_URL", "http://127.0.0.1:7545")
    BLOCKCHAIN_CHAIN_ID: int = int(os.getenv("BLOCKCHAIN_CHAIN_ID", "1337"))
    BLOCKCHAIN_CONTRACT_ADDRESS: str = os.getenv("BLOCKCHAIN_CONTRACT_ADDRESS", "")
    BLOCKCHAIN_ACCOUNT_ADDRESS: str = os.getenv("BLOCKCHAIN_ACCOUNT_ADDRESS", "")
    BLOCKCHAIN_PRIVATE_KEY: str = os.getenv("BLOCKCHAIN_PRIVATE_KEY", "")
    BLOCKCHAIN_CONFIRMATIONS: int = int(os.getenv("BLOCKCHAIN_CONFIRMATIONS", "1"))

    # Chatbot & RAG Knowledge Base (Steps 11 + 12)
    KNOWLEDGE_BASE_DIR: str = os.getenv("KNOWLEDGE_BASE_DIR", str(Path(__file__).resolve().parent.parent.parent / "knowledge_base"))
    EMBEDDING_MODEL_NAME: str = os.getenv("EMBEDDING_MODEL_NAME", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    EMBEDDING_DIMENSION: int = int(os.getenv("EMBEDDING_DIMENSION", "384"))
    RAG_CHUNK_SIZE: int = int(os.getenv("RAG_CHUNK_SIZE", "500"))
    RAG_CHUNK_OVERLAP: int = int(os.getenv("RAG_CHUNK_OVERLAP", "100"))
    RAG_TOP_K: int = int(os.getenv("RAG_TOP_K", "4"))
    RAG_MIN_SIMILARITY: float = float(os.getenv("RAG_MIN_SIMILARITY", "0.35"))
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    # Experimental Demo Inference Configuration (Local Testing Only - Disabled by default)
    ENABLE_EXPERIMENTAL_DEMO_INFERENCE: bool = os.getenv(
        "ENABLE_EXPERIMENTAL_DEMO_INFERENCE", "false"
    ).lower() in ("true", "1", "yes")
    DEMO_MODEL_WEIGHTS_PATH: str = os.getenv(
        "DEMO_MODEL_WEIGHTS_PATH",
        str(BASE_DIR / "models" / "experimental_baseline_v1" / "weights" / "best.pt"),
    )

    @property
    def IS_BLOCKCHAIN_CONFIGURED(self) -> bool:
        """Check if minimum blockchain configuration is present without checking connectivity."""
        return bool(
            self.BLOCKCHAIN_ENABLED
            and self.BLOCKCHAIN_RPC_URL
            and self.BLOCKCHAIN_CONTRACT_ADDRESS
            and self.BLOCKCHAIN_PRIVATE_KEY
        )

    @property
    def DATABASE_URL(self) -> str:
        url = os.getenv("DATABASE_URL")
        if not url:
            url = f"postgresql+psycopg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        
        # Normalize Render/Heroku postgres:// prefix or raw postgresql:// to use psycopg driver
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)

        # Strict PostgreSQL validation - reject SQLite or non-Postgres URLs
        url_lower = url.lower()
        if not (url_lower.startswith("postgresql://") or url_lower.startswith("postgresql+psycopg://") or url_lower.startswith("postgresql+psycopg2://")):
            raise ValueError(f"Strict PostgreSQL requirement: Invalid database dialect in URL. SQLite is prohibited.")
            
        return url

    @property
    def SAFE_DATABASE_URL(self) -> str:
        """Return database URL with password masked for safe logging and diagnostics."""
        url = self.DATABASE_URL
        if "@" in url and "://" in url:
            prefix, rest = url.split("://", 1)
            user_pass, host_db = rest.split("@", 1)
            user = user_pass.split(":")[0] if ":" in user_pass else user_pass
            return f"{prefix}://{user}:*****@{host_db}"
        return url


settings = Settings()
