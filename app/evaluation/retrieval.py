"검색 평가: 정답 판정과 Recall@k·MRR·현행 적중률 계산."
import json
from pathlib import Path

import numpy as np

from app.constants.law import ARTICLE_NUMBER, DOCUMENT_PART, IS_EFFECTIVE, MAIN
from app.constants.paths import RETRIEVAL_EVAL_PATH, TEXT_ENCODING
from app.documents.law_documents import LAW_SOURCES, chunk_law_document


def load_eval_set(path: str | Path = RETRIEVAL_EVAL_PATH) -> dict:
    with Path(path).open(encoding=TEXT_ENCODING) as file:
        return json.load(file)


def build_law_chunks(max_chunk_chars: float | None = None) -> list[dict]:
    "법률·시행령 원문에서 청크를 메모리로 바로 만든다."
    chunks = []
    for document_type in LAW_SOURCES:
        chunks.extend(chunk_law_document(document_type, max_chunk_chars)[1])
    return chunks


def is_answer(chunk: dict, answer: dict) -> bool:
    # 평가셋 정의: chunk_id 앞부분({법령번호}:{범위}:{조번호})이 같으면 적중. occurrence·part는 무시.
    return (
        chunk['document_type'] == answer['document_type']
        and chunk[ARTICLE_NUMBER] == answer['article_number']
        and chunk[DOCUMENT_PART] == MAIN
    )


def first_hit_rank(ranked_chunks: list[dict], answers: list[dict], require_effective: bool = False) -> int | None:
    for rank, chunk in enumerate(ranked_chunks, start=1):
        if require_effective and not chunk[IS_EFFECTIVE]:
            continue
        if any(is_answer(chunk, answer) for answer in answers):
            return rank
    return None


def rank_chunks(query_vectors, passage_vectors) -> np.ndarray:
    "정규화된 벡터의 내적(코사인 유사도)이 큰 순서대로 문서 인덱스를 정렬한다."
    scores = np.asarray(query_vectors) @ np.asarray(passage_vectors).T
    return np.argsort(-scores, axis=1, kind='stable')


def evaluate(questions: list[dict], chunks: list[dict], ranking) -> list[dict]:
    results = []
    for question, order in zip(questions, ranking):
        ranked = [chunks[index] for index in order]
        result = {
            'id': question['id'],
            'category': question['category'],
            'rank': first_hit_rank(ranked, question['answers']),
        }
        if question['require_effective']:
            result['effective_rank'] = first_hit_rank(ranked, question['answers'], require_effective=True)
        results.append(result)
    return results


def hit_at_k(rank: int | None, top_k: int) -> bool:
    return rank is not None and rank <= top_k


def _stats(results: list[dict], top_k: int) -> dict:
    count = len(results)
    return {
        'count': count,
        'recall': sum(hit_at_k(r['rank'], top_k) for r in results) / count,
        'mrr': sum(1 / r['rank'] for r in results if r['rank'] is not None) / count,
    }


def summarize(results: list[dict], top_k: int) -> dict:
    summary = {'overall': _stats(results, top_k)}
    for category in sorted({r['category'] for r in results}):
        summary[category] = _stats([r for r in results if r['category'] == category], top_k)
    effective = [r for r in results if 'effective_rank' in r]
    if effective:
        summary['effective_hit'] = {
            'count': len(effective),
            'recall': sum(hit_at_k(r['effective_rank'], top_k) for r in effective) / len(effective),
        }
    return summary
