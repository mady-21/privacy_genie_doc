"저장된 문서 벡터를 메모리에 올려 두고, 질문 벡터와 비교해 관련 청크를 찾는다."
import json
from functools import lru_cache
from pathlib import Path

import numpy as np

from app.constants.paths import CHUNKS_FILENAME, EMBEDDINGS_FILENAME, EXTRACTED_DIR, TEXT_ENCODING
from app.documents.law_documents import LAW_SOURCES
from app.embeddings.store import REBUILD_HINT, load_embeddings


class SearchIndex:
    def __init__(self, chunks: list[dict], vectors: np.ndarray):
        self.chunks = chunks
        self.vectors = vectors

    @classmethod
    def load(cls, processed_dir: str | Path = EXTRACTED_DIR) -> 'SearchIndex':
        chunks, vectors = [], []
        for document_type in LAW_SOURCES:
            directory = Path(processed_dir) / document_type
            chunks_path = directory / CHUNKS_FILENAME
            if not chunks_path.exists():
                raise FileNotFoundError(f'{chunks_path}가 없습니다. {REBUILD_HINT}')
            with chunks_path.open(encoding=TEXT_ENCODING) as file:
                document_chunks = json.load(file)
            vectors.append(load_embeddings(directory / EMBEDDINGS_FILENAME, document_chunks))
            chunks.extend(document_chunks)
        return cls(chunks, np.vstack(vectors))

    def search(self, query_vector, top_k: int) -> list[tuple[dict, float]]:
        "벡터는 길이 1로 정규화되어 있어서 내적이 곧 코사인 유사도다."
        scores = self.vectors @ np.asarray(query_vector, dtype=np.float32)
        order = np.argsort(-scores, kind='stable')[:top_k]
        return [(self.chunks[index], float(scores[index])) for index in order]


@lru_cache(maxsize=1)
def get_search_index() -> SearchIndex:
    return SearchIndex.load()
