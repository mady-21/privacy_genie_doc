from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI
from pydantic import BaseModel, Field, StringConstraints

from app.constants.embedding import MAX_TEXT_CHARS, MAX_TEXTS_PER_REQUEST
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


@app.get("/health")
def health():
    return {"status": "hello mady"}


@app.post("/embeddings", response_model=EmbeddingResponse)
def create_embeddings(request: EmbeddingRequest, embedder: Embedder = Depends(get_embedder)):
    return EmbeddingResponse(model=embedder.model_name, dimension=embedder.dimension, embeddings=embedder.embed(request.texts))
