import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from app.constants.embedding import EMBEDDING_DIMENSION, EMBEDDING_MODEL
from app.embeddings.store import load_embeddings, save_embeddings
from app.search.index import SearchIndex


def _chunk(chunk_id: str, text: str) -> dict:
    return {'chunk_id': chunk_id, 'law_name': '법', 'text': text}


def _unit_vectors(count: int, seed: int = 0) -> np.ndarray:
    vectors = np.random.default_rng(seed).normal(size=(count, EMBEDDING_DIMENSION)).astype(np.float32)
    return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)


class EmbeddingStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.path = Path(self.temp.name) / 'embeddings.npz'
        self.chunks = [_chunk('a', '제1조 본문'), _chunk('b', '제2조 본문<개정 2020. 1. 1.>')]
        self.vectors = _unit_vectors(2)
        save_embeddings(self.path, self.chunks, self.vectors, EMBEDDING_MODEL)

    def tearDown(self):
        self.temp.cleanup()

    def test_round_trip(self):
        np.testing.assert_allclose(load_embeddings(self.path, self.chunks), self.vectors)

    def test_rejects_missing_file(self):
        with self.assertRaisesRegex(FileNotFoundError, 'rebuild_chunks.py'):
            load_embeddings(Path(self.temp.name) / 'none.npz', self.chunks)

    def test_rejects_other_model(self):
        with self.assertRaisesRegex(ValueError, '다른/모델'):
            load_embeddings(self.path, self.chunks, model_name='다른/모델')

    def test_rejects_changed_chunk_list(self):
        with self.assertRaisesRegex(ValueError, '청크 목록'):
            load_embeddings(self.path, list(reversed(self.chunks)))

    def test_rejects_changed_text_with_same_chunk_id(self):
        changed = [self.chunks[0], _chunk('b', '제2조 바뀐 본문')]
        with self.assertRaisesRegex(ValueError, '본문이나 임베딩 입력 규칙'):
            load_embeddings(self.path, changed)

    def test_annotation_only_change_does_not_invalidate(self):
        "개정이력 표기는 임베딩 입력에서 빠지므로, 그것만 바뀐 경우 벡터를 다시 만들 필요가 없다."
        changed = [self.chunks[0], _chunk('b', '제2조 본문<개정 2024. 5. 5.>')]
        np.testing.assert_allclose(load_embeddings(self.path, changed), self.vectors)


class SearchIndexTests(unittest.TestCase):
    def test_search_returns_closest_chunks_first(self):
        chunks = [_chunk('a', 'A'), _chunk('b', 'B'), _chunk('c', 'C')]
        vectors = _unit_vectors(3)
        query = vectors[2] * 0.9 + vectors[0] * 0.1
        results = SearchIndex(chunks, vectors).search(query / np.linalg.norm(query), top_k=2)
        self.assertEqual([chunk['chunk_id'] for chunk, _ in results], ['c', 'a'])
        self.assertGreater(results[0][1], results[1][1])

    def test_load_reads_every_document_type(self):
        with TemporaryDirectory() as temp:
            for offset, document_type in enumerate(('act', 'decree')):
                directory = Path(temp) / document_type
                chunks = [_chunk(f'{document_type}-1', '본문 하나'), _chunk(f'{document_type}-2', '본문 둘')]
                directory.mkdir()
                (directory / 'chunks.json').write_text(json.dumps(chunks, ensure_ascii=False), encoding='utf-8')
                save_embeddings(directory / 'embeddings.npz', chunks, _unit_vectors(2, seed=offset), EMBEDDING_MODEL)
            index = SearchIndex.load(temp)
        self.assertEqual([c['chunk_id'] for c in index.chunks], ['act-1', 'act-2', 'decree-1', 'decree-2'])
        self.assertEqual(index.vectors.shape, (4, EMBEDDING_DIMENSION))

    def test_load_fails_clearly_without_files(self):
        with TemporaryDirectory() as temp:
            with self.assertRaisesRegex(FileNotFoundError, 'rebuild_chunks.py'):
                SearchIndex.load(temp)


if __name__ == '__main__':
    unittest.main()
