import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from app.parsers.hwpx_parser import HwpxParser
from app.parsers.law_structure_parser import LawStructureParser
from app.chunkers.law_chunker import LawChunker
from app.embeddings.embedding_text_builder import EmbeddingTextBuilder


class PipelineTests(unittest.TestCase):
    def test_structure_and_exclusions(self):
        paragraphs = [
            '법', '제1장 총칙', '제2조(정의) 본문', '1. 항목',
            '가. 목', '이어지는 문장', '제2조(정의) 다른 본문',
            '[시행일: 2027. 3. 9.] 제2조', '제10장 벌칙',
            '제70조(벌칙) 제외', '부칙', '<제123호, 2026. 1. 1.>',
            '제1조(시행일) 유지',
        ]
        chunks = LawChunker().chunk(LawStructureParser().parse(paragraphs))
        self.assertEqual(len(chunks), 3)
        self.assertEqual(len({x['chunk_id'] for x in chunks}), 3)
        self.assertIn('가. 목\n이어지는 문장', chunks[0]['text'])
        self.assertIn('[시행일: 2027. 3. 9.]', chunks[1]['text'])
        self.assertTrue(chunks[0]['is_effective'])
        self.assertIsNone(chunks[0]['article_effective_date'])
        self.assertFalse(chunks[1]['is_effective'])
        self.assertEqual(chunks[1]['article_effective_date'], '2027-03-09')
        self.assertEqual(chunks[2]['document_part'], 'supplementary')
        self.assertIsNone(chunks[2]['chapter'])
        self.assertEqual(chunks[2]['supplement']['law_number'], '법률 제123호')
        with TemporaryDirectory() as temp:
            path = EmbeddingTextBuilder().save_preview(
                chunks, Path(temp) / 'preview.txt', ['제2조']
            )
            text = path.read_text(encoding='utf-8')
            self.assertIn('확인 대상: 2개 청크', text)
            self.assertIn('document_part: main', text)

    def test_short_article_is_not_split(self):
        paragraphs = ['법', '제1조(목적) 짧은 조문이다.']
        chunks = LawChunker().chunk(LawStructureParser().parse(paragraphs))
        self.assertEqual(chunks[0]['part_index'], 1)
        self.assertEqual(chunks[0]['part_count'], 1)
        self.assertNotIn(':part', chunks[0]['chunk_id'])

    def test_law_effective_date_is_normalized_to_iso(self):
        paragraphs = ['법', '[시행 2026. 9. 11.]', '[법률 제21445호, 2026. 3. 10., 일부개정]', '제1조(목적) 본문.']
        document = LawStructureParser().parse(paragraphs)
        self.assertEqual(document['law']['effective_date'], '2026-09-11')

    def test_penalty_chapter_includes_fines_but_excludes_criminal_articles(self):
        paragraphs = [
            '법', '제10장 벌칙', '제70조(벌칙) 형사처벌 조문.', '제75조(과태료) 과태료 조문.',
        ]
        chunks = LawChunker().chunk(LawStructureParser().parse(paragraphs))
        article_numbers = {c['article_number'] for c in chunks}
        self.assertNotIn('제70조', article_numbers)
        self.assertIn('제75조', article_numbers)

    def test_unknown_article_in_penalty_chapter_raises(self):
        paragraphs = ['법', '제10장 벌칙', '제77조(신설 조문) 아직 분류되지 않은 조문.']
        document = LawStructureParser().parse(paragraphs)
        with self.assertRaises(ValueError):
            LawChunker().chunk(document)

    def test_numeric_section_order(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / 'sample.hwpx'
            with ZipFile(path, 'w') as archive:
                for number in (10, 2, 0):
                    archive.writestr(
                        f'Contents/section{number}.xml',
                        f'<section><p><t>{number}</t></p></section>',
                    )
            self.assertEqual(HwpxParser(str(path)).parse(), ['0', '2', '10'])


class _SmallChunker(LawChunker):
    "분할 로직을 거대한 fixture 없이 검증하기 위한 테스트용 길이 제한."
    MAX_CHUNK_CHARS = 10


class ChunkSplittingTests(unittest.TestCase):
    def test_splits_long_article_at_paragraph_boundaries(self):
        paragraphs = [
            '법', '제1조(목적) 이 법의 목적을 정한다.',
            '① 첫째 항목에 대한 비교적 긴 설명 문장이다.',
            '② 둘째 항목에 대한 비교적 긴 설명 문장이다.',
            '③ 셋째 항목에 대한 비교적 긴 설명 문장이다.',
        ]
        chunks = _SmallChunker().chunk(LawStructureParser().parse(paragraphs))
        self.assertEqual(len(chunks), 3)
        self.assertEqual([c['part_index'] for c in chunks], [1, 2, 3])
        self.assertTrue(all(c['part_count'] == 3 for c in chunks))
        self.assertEqual(len({c['chunk_id'] for c in chunks}), 3)
        for index, chunk in enumerate(chunks, start=1):
            self.assertEqual(chunk['chunk_id'].rsplit(':', 1)[-1], f'part{index}')
            self.assertIn('제1조(목적) 이 법의 목적을 정한다.', chunk['text'])
        self.assertIn('첫째 항목', chunks[0]['text'])
        self.assertIn('둘째 항목', chunks[1]['text'])
        self.assertIn('셋째 항목', chunks[2]['text'])

    def test_splits_long_article_at_item_boundaries_when_no_paragraphs(self):
        paragraphs = [
            '법', '제2조(정의) 이 법에서 사용하는 용어의 뜻은 다음과 같다.',
            '1. 첫째 항목에 대한 비교적 긴 정의 문장이다.',
            '2. 둘째 항목에 대한 비교적 긴 정의 문장이다.',
        ]
        document = LawStructureParser().parse(paragraphs)
        self.assertEqual(document['articles'][0]['paragraphs'], [])
        chunks = _SmallChunker().chunk(document)
        self.assertEqual(len(chunks), 2)
        self.assertIn('첫째 항목', chunks[0]['text'])
        self.assertIn('둘째 항목', chunks[1]['text'])

    def test_subitems_stay_attached_to_their_item(self):
        paragraphs = [
            '법', '제2조(정의) 용어의 뜻은 다음과 같다.',
            '1. 첫째 항목에 대한 비교적 긴 정의 문장이다.',
            '가. 첫째 항목의 세부 내용이다.',
            '나. 첫째 항목의 또 다른 세부 내용이다.',
            '2. 둘째 항목에 대한 비교적 긴 정의 문장이다.',
        ]
        chunks = _SmallChunker().chunk(LawStructureParser().parse(paragraphs))
        self.assertEqual(len(chunks), 2)
        first_part = chunks[0]['text']
        self.assertIn('가. 첫째 항목의 세부 내용이다.', first_part)
        self.assertIn('나. 첫째 항목의 또 다른 세부 내용이다.', first_part)
        self.assertNotIn('가.', chunks[1]['text'])

    def test_single_paragraph_longer_than_limit_is_not_fragmented(self):
        paragraphs = [
            '법', '제1조(목적) 이 법의 목적을 정한다.',
            '① 이 항은 길이 제한보다 훨씬 긴 하나의 문장으로, 중간에 끊이지 않고 '
            '하나의 청크로 온전히 유지되어야 하는 내용을 담고 있다.',
        ]
        chunks = _SmallChunker().chunk(LawStructureParser().parse(paragraphs))
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]['part_count'], 1)
        self.assertIn('중간에 끊이지 않고', chunks[0]['text'])

    def test_max_chunk_chars_can_be_set_per_instance(self):
        paragraphs = [
            '법', '제1조(목적) 이 법의 목적을 정한다.',
            '① 첫째 항목에 대한 비교적 긴 설명 문장이다.',
            '② 둘째 항목에 대한 비교적 긴 설명 문장이다.',
        ]
        document = LawStructureParser().parse(paragraphs)
        self.assertEqual(len(LawChunker(max_chunk_chars=10).chunk(document)), 2)
        self.assertEqual(len(LawChunker(max_chunk_chars=float('inf')).chunk(document)), 1)
        self.assertEqual(LawChunker().MAX_CHUNK_CHARS, 1000)


if __name__ == '__main__':
    unittest.main()
