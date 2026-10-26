from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI
from pydantic import BaseModel, Field, StringConstraints

from app.constants.embedding import DEFAULT_SEARCH_TOP_K, MAX_SEARCH_TOP_K, MAX_TEXT_CHARS, MAX_TEXTS_PER_REQUEST
from app.embeddings.embedder import Embedder, get_embedder
from app.search.index import SearchIndex, get_search_index


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 모델(수 초)과 문서 벡터를 서버가 뜰 때 미리 불러온다. 벡터 파일이 없거나 낡았으면 여기서 실패한다.
    get_embedder()
    get_search_index()
    yield


app = FastAPI(title="privacy-genie-doc", lifespan=lifespan)

EmbeddingText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_TEXT_CHARS)]


class EmbeddingRequest(BaseModel):
    texts: list[EmbeddingText] = Field(min_length=1, max_length=MAX_TEXTS_PER_REQUEST)


class EmbeddingResponse(BaseModel):
    model: str
    dimension: int
    embeddings: list[list[float]]


class SearchRequest(BaseModel):
    query: EmbeddingText
    top_k: int = Field(default=DEFAULT_SEARCH_TOP_K, ge=1, le=MAX_SEARCH_TOP_K)


class SearchResult(BaseModel):
    chunk_id: str
    score: float
    document_type: str
    law_name: str
    law_number: str | None
    article_number: str
    article_title: str | None
    chapter: str | None
    section: str | None
    text: str
    part_index: int
    part_count: int
    is_effective: bool
    article_effective_date: str | None


class SearchResponse(BaseModel):
    model: str
    results: list[SearchResult]


@app.get("/health")
def health():
    return {"status": "hello mady"}


@app.post("/embeddings", response_model=EmbeddingResponse)
def create_embeddings(request: EmbeddingRequest, embedder: Embedder = Depends(get_embedder)):
    return EmbeddingResponse(model=embedder.model_name, dimension=embedder.dimension, embeddings=embedder.embed(request.texts))


@app.post("/search", response_model=SearchResponse)
def search(
    request: SearchRequest,
    embedder: Embedder = Depends(get_embedder),
    index: SearchIndex = Depends(get_search_index),
):
    "질문을 임베딩해서 문서 벡터와 비교하고, 가까운 청크부터 돌려준다. 미시행 조문도 is_effective=false로 함께 나온다."
    query_vector = embedder.embed_array([request.query])[0]
    fields = SearchResult.model_fields.keys() - {'score'}
    return SearchResponse(
        model=embedder.model_name,
        results=[
            SearchResult(score=score, **{field: chunk[field] for field in fields})
            for chunk, score in index.search(query_vector, request.top_k)
        ],
    )
