import unittest
from app.constants.paths import ACT_SOURCE_PATH, DECREE_SOURCE_PATH
from app.parsers.hwpx_parser import HwpxParser
from app.parsers.law_structure_parser import LawStructureParser
from app.chunkers.act_chunker import ActChunker
from app.chunkers.decree_chunker import DecreeChunker


class DocumentTests(unittest.TestCase):
    def test_uploaded_documents(self):
        cases = (
            (ACT_SOURCE_PATH, ActChunker(), "법률 제21445호"),
            (DECREE_SOURCE_PATH, DecreeChunker(), "대통령령 제36671호"),
        )
        for path, chunker, expected_number in cases:
            with self.subTest(source=path.name):
                document = LawStructureParser().parse(HwpxParser(str(path)).parse())
                self.assertEqual(document['law']['law_number'], expected_number)
                chunks = chunker.chunk(document)
                included = [a for a in document['articles'] if not chunker.should_exclude(a)]
                self.assertGreater(len(chunks), 0)
                self.assertEqual(len(chunks), len(included))
                self.assertEqual(len({c['chunk_id'] for c in chunks}), len(chunks))
                for article, chunk in zip(included, chunks):
                    self.assertTrue(chunk['text'].endswith('\n'.join(article['source_lines'])))
                    self.assertNotIn('article_effective_date', chunk)
                    self.assertEqual(chunk['document_type'], chunker.DOCUMENT_TYPE)
                    if chunk['document_part'] == 'supplementary':
                        self.assertIsNone(chunk['chapter'])
                        self.assertEqual(chunk['supplement']['law_number'], expected_number)
                if chunker.DOCUMENT_TYPE == 'act':
                    self.assertFalse(any(c['chapter'] == '제10장 벌칙' for c in chunks))
                else:
                    self.assertTrue(any(c['article_number'] == '제62조' for c in chunks))
                    self.assertFalse(any(c['article_number'] == '제63조' and c['document_part'] == 'main' for c in chunks))
