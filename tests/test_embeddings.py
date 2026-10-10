import os
import unittest


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
