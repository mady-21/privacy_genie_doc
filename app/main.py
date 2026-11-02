from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field, StringConstraints

from app.constants.embedding import MAX_TEXT_CHARS, MAX_TEXTS_PER_REQUEST
from app.constants.paths import EXTRACTED_DIR
from app.documents.law_documents import load_document_export
from app.embeddings.embedder import Embedder, get_embedder


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 첫 요청이 모델 로딩(수 초)을 기다리지 않도록 서버가 뜰 때 미리 불러온다.
    get_embedder()
    yield


app = FastAPI(title="privacy-genie-doc", lifespan=lifespan)

EmbeddingText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_TEXT_CHARS)]


class EmbeddingRequest(BaseModel):
    texts: list[EmbeddingText] = Field(min_length=1, max_length=MAX_TEXTS_PER_REQUEST)


class EmbeddingResponse(BaseModel):
    model: str
    dimension: int
    embeddings: list[list[float]]


class DocumentChunk(BaseModel):
    chunk_id: str
    position: int
    article_number: str
    article_title: str | None
    chapter: str | None
    section: str | None
    text: str
    part_index: int
    part_count: int
    is_effective: bool
    article_effective_date: str | None
    metadata: dict[str, str]
    embedding: list[float]


class DocumentResponse(BaseModel):
    source_key: str
    document_type: str
    name: str
    law_number: str | None
    law_effective_date: str | None
    embedding_model: str
    embedding_dimension: int
    chunks: list[DocumentChunk]


def get_processed_dir() -> Path:
    return EXTRACTED_DIR


@app.get("/health")
def health():
    return {"status": "hello mady"}


@app.post("/embeddings", response_model=EmbeddingResponse)
def create_embeddings(request: EmbeddingRequest, embedder: Embedder = Depends(get_embedder)):
    "질문 등 텍스트를 벡터로 바꾼다. web은 이 벡터로 자기 DB(pgvector)에서 검색한다."
    return EmbeddingResponse(model=embedder.model_name, dimension=embedder.dimension, embeddings=embedder.embed(request.texts))


@app.get("/documents/{document_type}", response_model=DocumentResponse)
def get_document(document_type: Literal["act", "decree"], processed_dir: Path = Depends(get_processed_dir)):
    "web 적재용: rebuild_chunks.py가 미리 만든 청크와 벡터를 돌려준다. 부칙은 포함하지 않는다."
    try:
        return load_document_export(document_type, processed_dir)
    except (FileNotFoundError, ValueError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
