import os
import unittest

from app.embeddings.embedding_text_builder import EmbeddingTextBuilder


class EmbeddingTextBuilderTests(unittest.TestCase):
    def setUp(self):
        self.builder = EmbeddingTextBuilder()

    def _build(self, text: str) -> str:
        return self.builder.build(document_name='', chunk={'text': text, 'article_number': '테스트'})

    def test_adds_passage_prefix(self):
        result = self._build('제1조(목적) 이 법은 ...')
        self.assertTrue(result.startswith('passage: '))

    def test_strips_amendment_history_annotations(self):
        text = (
            '제1조(목적) 이 법의 목적이다.<개정 2014. 3. 24., 2023. 3. 14.>\n'
            '① 신설된 항이다.<신설 2020. 2. 4.>\n'
            '[본조신설 2013. 8. 6.]\n'
            '[시행일: 2027. 3. 9.]'
        )
        result = self._build(text)
        for noise in ('<개정', '<신설', '[본조신설', '[시행일'):
            self.assertNotIn(noise, result)
        self.assertIn('이 법의 목적이다.', result)
        self.assertIn('신설된 항이다.', result)

    def test_preserves_substantive_square_bracket_content(self):
        "개정이력 키워드로 시작하지 않는 스퀘어브래킷은 실질 조문 내용이라 보존해야 한다."
        text = (
            '가. 자산 [법인의 경우에는 납입자본금(비영리법인의 경우에는 기본재산)을 '
            '말하고, 법인이 아닌 단체의 경우에는 해당 단체가 보유하는 자산의 가액을 '
            '말한다. 이하 이 목에서 같다]을 기준으로 한다.'
        )
        result = self._build(text)
        self.assertIn('[법인의 경우에는 납입자본금', result)

    def test_raises_when_text_missing(self):
        with self.assertRaises(ValueError):
            self.builder.build(document_name='', chunk={'article_number': '테스트'})


@unittest.skipUnless(
    os.getenv("RUN_MODEL_TESTS") == "1",
    "실제 모델 테스트는 RUN_MODEL_TESTS=1로 실행",
)
class EmbeddingModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import numpy as np
        from sentence_transformers import SentenceTransformer

        cls.np = np
        cls.model = SentenceTransformer(
            "intfloat/multilingual-e5-small",
            device="cpu",
        )

        cls.vectors = cls.model.encode(
            [
                "query: 회원이 탈퇴하면 개인정보를 지워야 하나?",
                "passage: 개인정보가 불필요하게 되었을 때에는 "
                "지체 없이 파기하여야 한다.",
            ],
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )

    def test_vector_shape(self):
        "입력 두 개가 각각 384차원 벡터로 변환되는지 확인."
        self.assertEqual(self.vectors.shape, (2, 384))

    def test_vectors_are_finite(self):
        "벡터에 NaN이나 무한대가 없는지 확인."
        self.assertTrue(self.np.isfinite(self.vectors).all())

    def test_vectors_are_normalized(self):
        "각 벡터의 길이가 1로 정규화되었는지 확인."
        norms = self.np.linalg.norm(self.vectors, axis=1)

        self.np.testing.assert_allclose(
            norms,
            self.np.ones(2),
            rtol=1e-5,
            atol=1e-6,
        )


if __name__ == "__main__":
    unittest.main()
