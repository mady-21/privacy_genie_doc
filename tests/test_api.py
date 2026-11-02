import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from fastapi.testclient import TestClient

from app.constants.embedding import EMBEDDING_DIMENSION, EMBEDDING_MODEL, MAX_TEXT_CHARS, MAX_TEXTS_PER_REQUEST
from app.embeddings.embedder import get_embedder
from app.embeddings.store import save_embeddings
from app.main import app, get_processed_dir


class _FakeEmbedder:
    "실제 모델(2.3GB) 없이 API 계약만 검증하기 위한 가짜 임베더."
    model_name = 'fake/model'
    dimension = 3

    def embed_array(self, texts):
        return np.array([[float(len(text)), 0.0, 1.0] for text in texts])

    def embed(self, texts):
        return self.embed_array(texts).tolist()


class EmbeddingApiTests(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides[get_embedder] = _FakeEmbedder
        # with 블록 없이 만들면 lifespan(실제 모델 로딩)이 실행되지 않는다.
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_returns_one_vector_per_text_in_order(self):
        response = self.client.post('/embeddings', json={'texts': ['가', '가나다']})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['model'], 'fake/model')
        self.assertEqual(body['dimension'], 3)
        self.assertEqual(body['embeddings'], [[1.0, 0.0, 1.0], [3.0, 0.0, 1.0]])

    def test_rejects_invalid_requests(self):
        cases = {
            '빈 목록': {'texts': []},
            '공백뿐인 텍스트': {'texts': ['   ']},
            '요청당 개수 초과': {'texts': ['질문'] * (MAX_TEXTS_PER_REQUEST + 1)},
            '길이 초과': {'texts': ['가' * (MAX_TEXT_CHARS + 1)]},
            'texts 누락': {},
        }
        for name, payload in cases.items():
            with self.subTest(name):
                self.assertEqual(self.client.post('/embeddings', json=payload).status_code, 422)


def _document_chunk(chunk_id: str, article_number: str, text: str, is_effective: bool = True) -> dict:
    return {
        'chunk_id': chunk_id, 'document_type': 'act', 'document_part': 'main', 'supplement': None,
        'law_name': '개인정보 보호법', 'law_number': '법률 제21445호', 'law_effective_date': '2026-09-11',
        'article_number': article_number, 'article_title': '제목', 'chapter': '제1장 총칙', 'section': None,
        'text': text, 'part_index': 1, 'part_count': 1, 'is_effective': is_effective,
        'article_effective_date': None if is_effective else '2027-07-01', 'metadata': {},
    }


class DocumentApiTests(unittest.TestCase):
    "rebuild_chunks.py가 만든 파일 대신 임시 폴더에 가짜 청크·벡터 파일을 두고 확인한다."

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.act_dir = Path(self.temp.name) / 'act'
        self.act_dir.mkdir()
        self.chunks = [
            _document_chunk('법률 제21445호:main:제1조:1', '제1조', '제1조(목적) 본문.<개정 2014. 3. 24.>'),
            _document_chunk('법률 제21445호:main:제2조:2', '제2조', '제2조(정의) 미시행 본문.', is_effective=False),
        ]
        self._write_chunks(self.chunks)
        rng = np.random.default_rng(0)
        vectors = rng.normal(size=(2, EMBEDDING_DIMENSION)).astype(np.float32)
        self.vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
        save_embeddings(self.act_dir / 'embeddings.npz', self.chunks, self.vectors, EMBEDDING_MODEL)
        app.dependency_overrides[get_processed_dir] = lambda: Path(self.temp.name)
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.temp.cleanup()

    def _write_chunks(self, chunks):
        (self.act_dir / 'chunks.json').write_text(json.dumps(chunks, ensure_ascii=False), encoding='utf-8')

    def test_returns_document_with_saved_vectors(self):
        response = self.client.get('/documents/act')
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['source_key'], 'privacy')
        self.assertEqual(body['document_type'], 'act')
        self.assertEqual(body['name'], '개인정보 보호법')
        self.assertEqual(body['law_number'], '법률 제21445호')
        self.assertEqual(body['law_effective_date'], '2026-09-11')
        self.assertEqual(body['embedding_model'], EMBEDDING_MODEL)
        self.assertEqual(body['embedding_dimension'], EMBEDDING_DIMENSION)
        chunks = body['chunks']
        self.assertEqual([c['chunk_id'] for c in chunks], [c['chunk_id'] for c in self.chunks])
        self.assertEqual([c['position'] for c in chunks], [1, 2])
        np.testing.assert_allclose(np.array([c['embedding'] for c in chunks]), self.vectors, rtol=1e-6)
        self.assertIn('<개정 2014. 3. 24.>', chunks[0]['text'])
        self.assertFalse(chunks[1]['is_effective'])
        self.assertEqual(chunks[1]['article_effective_date'], '2027-07-01')
        self.assertNotIn('supplement', chunks[0])

    def test_missing_files_return_503_with_rebuild_hint(self):
        response = self.client.get('/documents/decree')
        self.assertEqual(response.status_code, 503)
        self.assertIn('rebuild_chunks.py', response.json()['detail'])

    def test_stale_vectors_return_503(self):
        changed = [self.chunks[0], {**self.chunks[1], 'text': '제2조(정의) 바뀐 본문.'}]
        self._write_chunks(changed)
        response = self.client.get('/documents/act')
        self.assertEqual(response.status_code, 503)
        self.assertIn('rebuild_chunks.py', response.json()['detail'])

    def test_unknown_document_type_is_rejected(self):
        self.assertEqual(self.client.get('/documents/guide').status_code, 422)


if __name__ == '__main__':
    unittest.main()
