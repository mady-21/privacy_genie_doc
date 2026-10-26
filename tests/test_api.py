import unittest

from fastapi.testclient import TestClient

from app.constants.embedding import MAX_TEXT_CHARS, MAX_TEXTS_PER_REQUEST
from app.embeddings.embedder import get_embedder
from app.main import app


class _FakeEmbedder:
    "실제 모델(2.3GB) 없이 API 계약만 검증하기 위한 가짜 임베더."
    model_name = 'fake/model'
    dimension = 3

    def embed(self, texts):
        return [[float(len(text)), 0.0, 1.0] for text in texts]


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


if __name__ == '__main__':
    unittest.main()
