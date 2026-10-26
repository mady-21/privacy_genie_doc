"rebuild 때 계산한 문서 벡터를 파일로 저장하고, 청크와 어긋나지 않았는지 확인하며 불러온다."
import hashlib
from pathlib import Path

import numpy as np

from app.constants.embedding import EMBEDDING_DIMENSION, EMBEDDING_MODEL
from app.constants.law import CHUNK_ID, LAW_NAME
from app.embeddings.embedding_text_builder import EmbeddingTextBuilder

REBUILD_HINT = 'rebuild_chunks.py로 청크와 벡터를 다시 만드세요.'


def embedding_inputs(chunks: list[dict]) -> list[str]:
    "청크를 임베딩 모델에 넣을 텍스트로 바꾼다. 저장할 때와 불러올 때 같은 규칙을 쓰려고 한 곳에 둔다."
    builder = EmbeddingTextBuilder()
    return [builder.build(document_name=chunk[LAW_NAME], chunk=chunk) for chunk in chunks]


def _digest(texts: list[str]) -> str:
    return hashlib.sha256('\x00'.join(texts).encode('utf-8')).hexdigest()


def save_embeddings(path: str | Path, chunks: list[dict], vectors: np.ndarray, model_name: str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        path,
        vectors=np.asarray(vectors, dtype=np.float32),
        chunk_ids=np.array([chunk[CHUNK_ID] for chunk in chunks]),
        inputs_digest=np.array(_digest(embedding_inputs(chunks))),
        model=np.array(model_name),
    )
    return path


def load_embeddings(path: str | Path, chunks: list[dict], model_name: str = EMBEDDING_MODEL) -> np.ndarray:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f'{path}가 없습니다. {REBUILD_HINT}')
    with np.load(path) as data:
        vectors = data['vectors']
        chunk_ids = data['chunk_ids'].tolist()
        inputs_digest = str(data['inputs_digest'])
        saved_model = str(data['model'])
    if saved_model != model_name:
        raise ValueError(f'{path}는 {saved_model}로 만든 벡터인데 지금 모델은 {model_name}입니다. {REBUILD_HINT}')
    if chunk_ids != [chunk[CHUNK_ID] for chunk in chunks]:
        raise ValueError(f'{path}의 청크 목록이 chunks.json과 다릅니다. {REBUILD_HINT}')
    # chunk_id가 같아도 본문이나 정제 규칙이 바뀌었으면 벡터는 낡은 것이다.
    if inputs_digest != _digest(embedding_inputs(chunks)):
        raise ValueError(f'{path}를 만든 뒤 청크 본문이나 임베딩 입력 규칙이 바뀌었습니다. {REBUILD_HINT}')
    if vectors.shape != (len(chunks), EMBEDDING_DIMENSION):
        raise ValueError(f'{path}의 벡터 모양 {vectors.shape}이 ({len(chunks)}, {EMBEDDING_DIMENSION})이 아닙니다.')
    return vectors
