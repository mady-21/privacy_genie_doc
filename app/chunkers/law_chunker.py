"""기존 LawChunker import와의 호환성을 유지한다."""
from app.chunkers.act_chunker import ActChunker

LawChunker = ActChunker
