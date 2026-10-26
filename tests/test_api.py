import unittest

import numpy as np
from fastapi.testclient import TestClient

from app.constants.embedding import MAX_SEARCH_TOP_K, MAX_TEXT_CHARS, MAX_TEXTS_PER_REQUEST
from app.embeddings.embedder import get_embedder
from app.main import app
from app.search.index import SearchIndex, get_search_index


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


def _search_chunk(chunk_id: str, article_number: str, is_effective: bool = True) -> dict:
    return {
        'chunk_id': chunk_id, 'document_type': 'act', 'law_name': '개인정보 보호법', 'law_number': '법률 제1호',
        'article_number': article_number, 'article_title': '제목', 'chapter': None, 'section': None,
        'text': f'{article_number} 본문', 'part_index': 1, 'part_count': 1, 'is_effective': is_effective,
        'article_effective_date': None if is_effective else '2027-07-01', 'metadata': {}, 'supplement': None,
    }


def _fake_index() -> SearchIndex:
    # 가짜 임베더는 질문 길이를 첫 번째 축에 두므로, 질문이 길수록 1번 청크와 가까워진다.
    chunks = [_search_chunk('c1', '제1조'), _search_chunk('c2', '제2조', is_effective=False), _search_chunk('c3', '제3조')]
    vectors = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, 1.0, 0.0]])
    return SearchIndex(chunks, vectors)


class SearchApiTests(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides[get_embedder] = _FakeEmbedder
        app.dependency_overrides[get_search_index] = _fake_index
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_returns_closest_chunks_with_fields(self):
        response = self.client.post('/search', json={'query': '아주 긴 질문입니다', 'top_k': 2})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['model'], 'fake/model')
        self.assertEqual([r['chunk_id'] for r in body['results']], ['c1', 'c2'])
        self.assertGreater(body['results'][0]['score'], body['results'][1]['score'])
        self.assertFalse(body['results'][1]['is_effective'])
        self.assertEqual(body['results'][1]['article_effective_date'], '2027-07-01')
        self.assertNotIn('metadata', body['results'][0])

    def test_default_top_k(self):
        body = self.client.post('/search', json={'query': '질문'}).json()
        self.assertEqual(len(body['results']), 3)

    def test_rejects_invalid_requests(self):
        cases = {
            '빈 질문': {'query': '   '},
            'query 누락': {},
            'top_k 0': {'query': '질문', 'top_k': 0},
            'top_k 초과': {'query': '질문', 'top_k': MAX_SEARCH_TOP_K + 1},
            '길이 초과': {'query': '가' * (MAX_TEXT_CHARS + 1)},
        }
        for name, payload in cases.items():
            with self.subTest(name):
                self.assertEqual(self.client.post('/search', json=payload).status_code, 422)


if __name__ == '__main__':
    unittest.main()
