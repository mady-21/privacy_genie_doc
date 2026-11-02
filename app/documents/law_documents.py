"법령 문서 종류별 원본·청커를 정의하고, 미리 만든 청크·벡터를 web 적재용으로 묶는다."
import json
from dataclasses import dataclass
from pathlib import Path

from app.chunkers.act_chunker import ActChunker
from app.chunkers.base_law_chunker import BaseLawChunker
from app.chunkers.decree_chunker import DecreeChunker
from app.constants.embedding import EMBEDDING_DIMENSION, EMBEDDING_MODEL
from app.constants.law import (
    ARTICLE_EFFECTIVE_DATE, ARTICLE_NUMBER, ARTICLE_TITLE, CHAPTER, CHUNK_ID, IS_EFFECTIVE, LAW,
    LAW_EFFECTIVE_DATE, LAW_NAME, LAW_NUMBER, METADATA, NAME, PART_COUNT, PART_INDEX, SECTION, TEXT,
)
from app.constants.paths import ACT_SOURCE_PATH, CHUNKS_FILENAME, DECREE_SOURCE_PATH, EMBEDDINGS_FILENAME, TEXT_ENCODING
from app.embeddings.store import REBUILD_HINT, load_embeddings


@dataclass(frozen=True)
class LawSource:
    path: Path
    chunker_class: type[BaseLawChunker]
    expected_name: str


LAW_SOURCES = {
    'act': LawSource(ACT_SOURCE_PATH, ActChunker, '개인정보 보호법'),
    'decree': LawSource(DECREE_SOURCE_PATH, DecreeChunker, '개인정보 보호법 시행령'),
}


def check_law_name(document_type: str, document: dict) -> None:
    expected = LAW_SOURCES[document_type].expected_name
    if document[LAW][NAME] != expected:
        raise ValueError(f'{document_type} 원문의 제목이 "{expected}"가 아닙니다: {document[LAW][NAME]}')


def load_document_export(document_type: str, processed_dir: Path) -> dict:
    "rebuild_chunks.py가 만든 chunks.json과 embeddings.npz를 읽어 web 적재용으로 묶는다. 임베딩을 다시 계산하지 않는다."
    directory = Path(processed_dir) / document_type
    chunks_path = directory / CHUNKS_FILENAME
    if not chunks_path.exists():
        raise FileNotFoundError(f'{chunks_path}가 없습니다. {REBUILD_HINT}')
    with chunks_path.open(encoding=TEXT_ENCODING) as file:
        chunks = json.load(file)
    if not chunks:
        raise ValueError(f'{chunks_path}에 청크가 없습니다. {REBUILD_HINT}')
    vectors = load_embeddings(directory / EMBEDDINGS_FILENAME, chunks)
    first = chunks[0]
    return {
        'source_key': LAW_SOURCES[document_type].path.stem,
        'document_type': document_type,
        'name': first[LAW_NAME],
        'law_number': first[LAW_NUMBER],
        'law_effective_date': first[LAW_EFFECTIVE_DATE],
        'embedding_model': EMBEDDING_MODEL,
        'embedding_dimension': EMBEDDING_DIMENSION,
        'chunks': [
            {
                CHUNK_ID: chunk[CHUNK_ID],
                'position': position,
                ARTICLE_NUMBER: chunk[ARTICLE_NUMBER],
                ARTICLE_TITLE: chunk[ARTICLE_TITLE],
                CHAPTER: chunk[CHAPTER],
                SECTION: chunk[SECTION],
                TEXT: chunk[TEXT],
                PART_INDEX: chunk[PART_INDEX],
                PART_COUNT: chunk[PART_COUNT],
                IS_EFFECTIVE: chunk[IS_EFFECTIVE],
                ARTICLE_EFFECTIVE_DATE: chunk[ARTICLE_EFFECTIVE_DATE],
                METADATA: chunk[METADATA],
                'embedding': vector,
            }
            for position, (chunk, vector) in enumerate(zip(chunks, vectors.tolist()), start=1)
        ],
    }
