"시행령: 조 단위 청킹. 모든 조문을 포함한다(2026-10-21: 과태료 제63조 포함 결정)."
from app.chunkers.base_law_chunker import BaseLawChunker


class DecreeChunker(BaseLawChunker):
    DOCUMENT_TYPE = "decree"
