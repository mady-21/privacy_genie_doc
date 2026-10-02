"""시행령: 조 단위 청킹, 보칙을 보존하고 과태료 조문만 제외."""
from app.constants.law import DOCUMENT_PART, MAIN, NUMBER, TITLE
from app.chunkers.base_law_chunker import BaseLawChunker


class DecreeChunker(BaseLawChunker):
    DOCUMENT_TYPE = "decree"
    EXCLUDED_ARTICLES = frozenset({("제63조", "과태료의 부과기준")})

    def should_exclude(self, article: dict) -> bool:
        return (
            article.get(DOCUMENT_PART, MAIN) == MAIN
            and (article[NUMBER], article[TITLE]) in self.EXCLUDED_ARTICLES
        )
