from pydantic_settings import BaseSettings
from typing import Literal


class Settings(BaseSettings):
    OPENAI_API_KEY: str = ""
    LLM_MODE: Literal["api", "local"] = "api"
    LLM_MODEL_API: str = "gpt-4o-mini"
    LLM_MODEL_LOCAL: str = "llama3"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    CHROMA_PERSIST_DIR: str = "./chroma_db"
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50

    @property
    def llm_model(self) -> str:
        if self.LLM_MODE == "api":
            return self.LLM_MODEL_API
        return self.LLM_MODEL_LOCAL

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
