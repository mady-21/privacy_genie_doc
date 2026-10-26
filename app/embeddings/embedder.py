"임베딩 모델을 한 번만 불러와 텍스트를 정규화된 벡터로 바꾼다."
from functools import lru_cache

import numpy as np

from app.constants.embedding import EMBEDDING_DIMENSION, EMBEDDING_MODEL


class Embedder:
    def __init__(self, model_name: str = EMBEDDING_MODEL):
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self.model = SentenceTransformer(model_name, device='cpu')
        self.dimension = self.model.get_embedding_dimension()
        if self.dimension != EMBEDDING_DIMENSION:
            raise ValueError(
                f'{model_name}의 벡터 차원({self.dimension})이 EMBEDDING_DIMENSION({EMBEDDING_DIMENSION})과 '
                '다릅니다. web의 벡터 컬럼과 맞춰서 함께 바꿔야 합니다.'
            )

    def embed_array(self, texts: list[str]) -> np.ndarray:
        return self.model.encode(texts, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self.embed_array(texts).tolist()


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    return Embedder()
