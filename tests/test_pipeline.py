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
        self.assertNotIn('article_effective_date', chunks[1])
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


if __name__ == '__main__':
    unittest.main()
