"""개인정보 보호법: 조 단위 청킹, 제10장 벌칙 제외."""
import re
from app.constants.law import CHAPTER, DOCUMENT_PART, LOCATION, MAIN
from app.chunkers.base_law_chunker import BaseLawChunker


class ActChunker(BaseLawChunker):
    DOCUMENT_TYPE = "act"
    PENALTY_CHAPTER_PATTERN = re.compile(r"^제\s*10\s*장\s+벌칙(?:\s|$)")

    def should_exclude(self, article: dict) -> bool:
        chapter = article[LOCATION].get(CHAPTER) or ""
        return (
            article.get(DOCUMENT_PART, MAIN) == MAIN
            and bool(self.PENALTY_CHAPTER_PATTERN.match(chapter.strip()))
        )
