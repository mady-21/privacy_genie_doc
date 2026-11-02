import unittest
from app.constants.paths import ACT_SOURCE_PATH, DECREE_SOURCE_PATH
from app.parsers.hwpx_parser import HwpxParser
from app.parsers.law_structure_parser import LawStructureParser
from app.chunkers.act_chunker import ActChunker
from app.chunkers.decree_chunker import DecreeChunker


def _base_chunk_id(chunk: dict) -> str:
    "분할된 청크의 chunk_id에서 ':partN' suffix를 떼고, 같은 조문의 조각들을 묶기 위한 키."
    segments = chunk['chunk_id'].split(':')
    if segments[-1].startswith('part'):
        segments = segments[:-1]
    return ':'.join(segments)


class DocumentTests(unittest.TestCase):
    def test_uploaded_documents(self):
        # 실측(hwpx 원문)으로 확인한, 원문에 [시행일: ...] 미리보기가 붙어 있는
        # (조번호, occurrence) 목록 — 해당 occurrence만 is_effective=False여야 한다.
        cases = (
            (
                ACT_SOURCE_PATH, ActChunker(), "법률 제21445호", "제64조의2",
                {
                    ('제2조', 2), ('제7조의9', 2), ('제28조의12', 1), ('제28조의13', 1),
                    ('제28조의14', 1), ('제28조의15', 1), ('제32조의2', 2),
                    ('제37조의2', 2), ('제75조', 2),
                },
            ),
            (
                DECREE_SOURCE_PATH, DecreeChunker(), "대통령령 제36671호", "제42조의6",
                {('제42조의2', 1)},
            ),
        )
        for path, chunker, expected_number, long_article_number, not_effective in cases:
            with self.subTest(source=path.name):
                document = LawStructureParser().parse(HwpxParser(str(path)).parse())
                self.assertEqual(document['law']['law_number'], expected_number)
                chunks = chunker.chunk(document)
                included = [a for a in document['articles'] if not chunker.should_exclude(a)]
                self.assertGreater(len(chunks), 0)
                self.assertEqual(len({c['chunk_id'] for c in chunks}), len(chunks))

                # 조문 하나가 여러 청크(분할)로 쪼개질 수 있으므로, chunk_id 기준으로
                # 같은 조문의 조각들을 묶어 조문 개수(len(included))와 1:1 대응시킨다.
                groups: dict[str, list[dict]] = {}
                for chunk in chunks:
                    groups.setdefault(_base_chunk_id(chunk), []).append(chunk)
                self.assertEqual(len(groups), len(included))
                for group in groups.values():
                    group.sort(key=lambda c: c['part_index'])
                    part_count = group[0]['part_count']
                    self.assertEqual([c['part_index'] for c in group], list(range(1, len(group) + 1)))
                    self.assertTrue(all(c['part_count'] == part_count for c in group))
                    self.assertEqual(len(group), part_count)
                    # is_effective/article_effective_date는 조문 전체에 적용되는 값이라
                    # 분할된 모든 part가 같은 값을 가져야 한다.
                    self.assertTrue(all(c['is_effective'] == group[0]['is_effective'] for c in group))
                    self.assertTrue(all(c['article_effective_date'] == group[0]['article_effective_date'] for c in group))
                    self.assertEqual(group[0]['is_effective'], group[0]['article_effective_date'] is None)

                # 부칙은 파싱은 하되 청크에서는 전부 뺀다.
                self.assertGreater(len(document['supplements']), 0)
                self.assertTrue(any(a['document_part'] == 'supplementary' for a in document['articles']))
                for chunk in chunks:
                    self.assertEqual(chunk['document_type'], chunker.DOCUMENT_TYPE)
                    self.assertEqual(chunk['document_part'], 'main')
                    self.assertIsNone(chunk['supplement'])

                # 분할되지 않은(part_count == 1) 조문은 기존처럼 원문(source_lines)을
                # 그대로 유지해야 한다 — 분할 로직 도입으로 짧은 조문의 텍스트가
                # 조금이라도 바뀌면 이 검증이 깨진다.
                found_not_effective = set()
                for article in included:
                    occurrence = article.get('occurrence', 1)
                    base_id = f"{expected_number}:main:{article['number']}:{occurrence}"
                    group = groups[base_id]
                    if len(group) == 1:
                        self.assertTrue(group[0]['text'].endswith('\n'.join(article['source_lines'])))
                    expect_not_effective = (article['number'], occurrence) in not_effective
                    self.assertEqual(group[0]['is_effective'], not expect_not_effective)
                    if expect_not_effective:
                        found_not_effective.add((article['number'], occurrence))
                self.assertEqual(found_not_effective, not_effective)

                short_article_group = groups[f'{expected_number}:main:제1조:1']
                self.assertEqual(len(short_article_group), 1)
                long_article_group = groups.get(f'{expected_number}:main:{long_article_number}:1')
                self.assertIsNotNone(long_article_group)
                self.assertGreater(len(long_article_group), 1)

                if chunker.DOCUMENT_TYPE == 'act':
                    penalty_chunks = [c for c in chunks if c['chapter'] == '제10장 벌칙']
                    penalty_numbers = {c['article_number'] for c in penalty_chunks}
                    self.assertEqual(penalty_numbers, {'제75조', '제76조'})
                    for excluded in ('제70조', '제71조', '제72조', '제73조', '제74조', '제74조의2'):
                        self.assertFalse(any(c['article_number'] == excluded for c in chunks))
                else:
                    self.assertTrue(any(c['article_number'] == '제62조' for c in chunks))
                    self.assertTrue(any(c['article_number'] == '제63조' and c['document_part'] == 'main' for c in chunks))
