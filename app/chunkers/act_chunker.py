"개인정보 보호법: 조 단위 청킹. 부칙과 제10장 벌칙 중 형벌 조문은 제외(과태료는 포함, 2026-10-21 결정)."
import re
from app.constants.law import CHAPTER, LOCATION, NUMBER, TITLE
from app.chunkers.base_law_chunker import BaseLawChunker


class ActChunker(BaseLawChunker):
    DOCUMENT_TYPE = "act"
    PENALTY_CHAPTER_PATTERN = re.compile(r"^제\s*10\s*장\s+벌칙(?:\s|$)")
    EXCLUDED_ARTICLES = frozenset({
        ("제70조", "벌칙"),
        ("제71조", "벌칙"),
        ("제72조", "벌칙"),
        ("제73조", "벌칙"),
        ("제74조", "양벌규정"),
        ("제74조의2", "몰수ㆍ추징 등"),
    })
    INCLUDED_PENALTY_ARTICLES = frozenset({
        ("제75조", "과태료"),
        ("제76조", "과태료에 관한 규정 적용의 특례"),
    })

    def should_exclude(self, article: dict) -> bool:
        if super().should_exclude(article):
            return True
        chapter = article[LOCATION].get(CHAPTER) or ""
        if not self.PENALTY_CHAPTER_PATTERN.match(chapter.strip()):
            return False
        key = (article[NUMBER], article[TITLE])
        if key in self.EXCLUDED_ARTICLES:
            return True
        if key in self.INCLUDED_PENALTY_ARTICLES:
            return False
        raise ValueError(
            f"제10장 벌칙에 알 수 없는 조문: {key} — ActChunker의 "
            "EXCLUDED_ARTICLES/INCLUDED_PENALTY_ARTICLES를 갱신하세요."
        )
