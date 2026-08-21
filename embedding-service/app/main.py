import hashlib
import logging
import sqlite3
import threading
from array import array
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastembed import TextEmbedding
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embedding_dimension: int = 384
    embedding_threads: int = 1
    embedding_model_cache_dir: Path = Path("/data/model-cache")
    embedding_result_cache_db: Path = Path("/data/result-cache/embeddings.sqlite3")
    embedding_max_batch_size: int = 32
    embedding_max_text_chars: int = 20_000


settings = Settings()


class EmbeddingRequest(BaseModel):
    texts: list[str] = Field(min_length=1)

    @field_validator("texts")
    @classmethod
    def validate_texts(cls, texts: list[str]) -> list[str]:
        if len(texts) > settings.embedding_max_batch_size:
            raise ValueError(f"batch size must not exceed {settings.embedding_max_batch_size}")
        for text in texts:
            if not text.strip():
                raise ValueError("texts must not contain empty strings")
            if len(text) > settings.embedding_max_text_chars:
                raise ValueError(
                    f"each text must not exceed {settings.embedding_max_text_chars} characters"
                )
        return texts


class EmbeddingResponse(BaseModel):
    model: str
    dimension: int
    embeddings: list[list[float]]
    cached: list[bool]


class EmbeddingEngine:
    def __init__(self) -> None:
        settings.embedding_model_cache_dir.mkdir(parents=True, exist_ok=True)
        settings.embedding_result_cache_db.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(settings.embedding_result_cache_db, check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=NORMAL")
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS embeddings (
                cache_key TEXT PRIMARY KEY,
                vector BLOB NOT NULL,
                dimension INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self._db.commit()
        self._lock = threading.Lock()
        logger.info("Loading embedding model %s", settings.embedding_model)
        self._model = TextEmbedding(
            model_name=settings.embedding_model,
            cache_dir=str(settings.embedding_model_cache_dir),
            threads=settings.embedding_threads,
        )
        logger.info("Embedding model is ready")

    @staticmethod
    def _cache_key(text: str) -> str:
        payload = f"{settings.embedding_model}\0{text}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _serialize(vector: list[float]) -> bytes:
        return array("f", vector).tobytes()

    @staticmethod
    def _deserialize(blob: bytes) -> list[float]:
        vector = array("f")
        vector.frombytes(blob)
        return list(vector)

    def embed(self, texts: list[str]) -> tuple[list[list[float]], list[bool]]:
        keys = [self._cache_key(text) for text in texts]
        vectors: list[list[float] | None] = [None] * len(texts)
        cached = [False] * len(texts)

        with self._lock:
            rows = {
                key: (blob, dimension)
                for key, blob, dimension in self._db.execute(
                    f"SELECT cache_key, vector, dimension FROM embeddings "
                    f"WHERE cache_key IN ({','.join('?' for _ in keys)})",
                    keys,
                )
            }

            missing_indexes: list[int] = []
            for index, key in enumerate(keys):
                row = rows.get(key)
                if row and row[1] == settings.embedding_dimension:
                    vectors[index] = self._deserialize(row[0])
                    cached[index] = True
                else:
                    missing_indexes.append(index)

            if missing_indexes:
                missing_texts = [texts[index] for index in missing_indexes]
                generated = self._model.embed(missing_texts)
                inserts: list[tuple[str, bytes, int]] = []
                for index, raw_vector in zip(missing_indexes, generated, strict=True):
                    vector = [float(value) for value in raw_vector]
                    if len(vector) != settings.embedding_dimension:
                        raise RuntimeError(
                            f"model returned dimension {len(vector)}, "
                            f"expected {settings.embedding_dimension}"
                        )
                    vectors[index] = vector
                    inserts.append(
                        (keys[index], self._serialize(vector), settings.embedding_dimension)
                    )
                self._db.executemany(
                    "INSERT OR REPLACE INTO embeddings(cache_key, vector, dimension) VALUES (?, ?, ?)",
                    inserts,
                )
                self._db.commit()

        return [vector for vector in vectors if vector is not None], cached

    def close(self) -> None:
        with self._lock:
            self._db.close()


engine: EmbeddingEngine | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global engine
    engine = EmbeddingEngine()
    yield
    engine.close()
    engine = None


app = FastAPI(title="News Radar Embedding Service", version="1.0.0", lifespan=lifespan)


@app.get("/health/live")
def liveness() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/health/ready")
def readiness() -> dict[str, str]:
    if engine is None:
        raise HTTPException(status_code=503, detail="model is not ready")
    return {"status": "ready", "model": settings.embedding_model}


@app.post("/v1/embeddings", response_model=EmbeddingResponse)
def create_embeddings(request: EmbeddingRequest) -> EmbeddingResponse:
    if engine is None:
        raise HTTPException(status_code=503, detail="model is not ready")
    embeddings, cached = engine.embed(request.texts)
    return EmbeddingResponse(
        model=settings.embedding_model,
        dimension=settings.embedding_dimension,
        embeddings=embeddings,
        cached=cached,
    )
