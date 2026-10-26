import unittest

import numpy as np

from app.evaluation.retrieval import (
    build_law_chunks, evaluate, first_hit_rank, is_answer, load_eval_set, rank_chunks, summarize,
)


def _chunk(document_type='act', article_number='제1조', document_part='main', is_effective=True):
    return {
        'document_type': document_type, 'article_number': article_number,
        'document_part': document_part, 'is_effective': is_effective,
    }


class EvalSetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.questions = load_eval_set()['questions']
        cls.chunks = build_law_chunks()

    def test_composition(self):
        self.assertEqual(len(self.questions), 30)
        self.assertEqual(len({q['id'] for q in self.questions}), 30)
        self.assertEqual(sum(q['category'] == 'general' for q in self.questions), 23)
        self.assertEqual(sum(q['category'] == 'fine' for q in self.questions), 7)
        require_effective = {q['id'] for q in self.questions if q['require_effective']}
        self.assertEqual(require_effective, {'F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'G11', 'G22'})

    def test_every_answer_exists_in_chunks(self):
        "법 개정으로 조문 번호가 바뀌면 평가셋이 조용히 틀어지지 않도록 정답 키를 실제 청크와 대조한다."
        for question in self.questions:
            for answer in question['answers']:
                with self.subTest(question=question['id'], answer=answer):
                    self.assertTrue(any(is_answer(c, answer) for c in self.chunks))

    def test_require_effective_questions_have_effective_answer_chunks(self):
        for question in self.questions:
            if not question['require_effective']:
                continue
            with self.subTest(question=question['id']):
                self.assertTrue(any(
                    c['is_effective'] and is_answer(c, a) for c in self.chunks for a in question['answers']
                ))

    def test_g15_answer_has_only_not_yet_effective_chunks(self):
        g15 = next(q for q in self.questions if q['id'] == 'G15')
        answer_chunks = [c for c in self.chunks if is_answer(c, g15['answers'][0])]
        self.assertTrue(answer_chunks)
        self.assertFalse(any(c['is_effective'] for c in answer_chunks))


class MetricTests(unittest.TestCase):
    def test_is_answer_ignores_part_and_occurrence_but_not_scope(self):
        answer = {'document_type': 'act', 'article_number': '제75조'}
        self.assertTrue(is_answer(_chunk(article_number='제75조'), answer))
        self.assertFalse(is_answer(_chunk(article_number='제75조', document_part='supplementary'), answer))
        self.assertFalse(is_answer(_chunk(document_type='decree', article_number='제75조'), answer))

    def test_first_hit_rank(self):
        answers = [{'document_type': 'act', 'article_number': '제75조'}]
        ranked = [_chunk(article_number='제2조'), _chunk(article_number='제75조', is_effective=False), _chunk(article_number='제75조')]
        self.assertEqual(first_hit_rank(ranked, answers), 2)
        self.assertEqual(first_hit_rank(ranked, answers, require_effective=True), 3)
        self.assertIsNone(first_hit_rank(ranked[:1], answers))

    def test_summarize(self):
        results = [
            {'id': 'G1', 'category': 'general', 'rank': 1},
            {'id': 'G2', 'category': 'general', 'rank': 4},
            {'id': 'G3', 'category': 'general', 'rank': None},
            {'id': 'F1', 'category': 'fine', 'rank': 6, 'effective_rank': 7},
        ]
        summary = summarize(results, top_k=5)
        self.assertAlmostEqual(summary['overall']['recall'], 2 / 4)
        self.assertAlmostEqual(summary['overall']['mrr'], (1 + 1 / 4 + 1 / 6) / 4)
        self.assertAlmostEqual(summary['general']['recall'], 2 / 3)
        self.assertEqual(summary['fine']['count'], 1)
        self.assertEqual(summary['effective_hit'], {'count': 1, 'recall': 0.0})

    def test_rank_chunks_and_evaluate(self):
        chunks = [_chunk(article_number='제1조'), _chunk(article_number='제2조')]
        passages = np.array([[1.0, 0.0], [0.0, 1.0]])
        queries = np.array([[0.1, 0.9]])
        ranking = rank_chunks(queries, passages)
        self.assertEqual(ranking[0].tolist(), [1, 0])
        question = {'id': 'Q', 'category': 'general', 'answers': [{'document_type': 'act', 'article_number': '제1조'}], 'require_effective': True}
        self.assertEqual(evaluate([question], chunks, ranking), [{'id': 'Q', 'category': 'general', 'rank': 2, 'effective_rank': 2}])


if __name__ == '__main__':
    unittest.main()
